"""Backend web del agente RAG (issue #6) — FastAPI.

Expone el agente como una API HTTP y sirve la interfaz de chat estática:

    GET  /              -> interfaz de chat (index.html)
    POST /api/ask       -> pregunta -> respuesta + fuentes + confianza
    POST /api/feedback  -> 👍/👎 sobre una respuesta
    GET  /api/metrics   -> resumen para mantenimiento
    GET  /api/health    -> healthcheck (para el deploy, issue #7)

El `RagAgent` (Chroma + clientes Cohere) se crea una sola vez y se reutiliza
entre requests. El historial de conversación se guarda en memoria por
`conversation_id`; el frontend además lo persiste en `localStorage`.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import observability
from ..answering import RagAgent

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Agente RAG corporativo", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Agente (lazy singleton): se construye en el primer uso, no al importar. ---
_agent: RagAgent | None = None
_agent_lock = Lock()

# Historial en memoria por conversación: {conversation_id: [ {role, content, ...} ]}
_conversations: dict[str, list[dict]] = {}


def get_agent() -> RagAgent:
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                _agent = RagAgent()
    return _agent


# --- Esquemas ---
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    category: str | None = None
    conversation_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    confidence: float | None
    no_answer: bool
    conversation_id: str
    message_id: str


class FeedbackRequest(BaseModel):
    conversation_id: str | None = None
    message_id: str | None = None
    rating: int = Field(..., description="+1 (👍) o -1 (👎)")
    comment: str | None = None


# --- Endpoints ---
@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="La pregunta está vacía.")

    conversation_id = req.conversation_id or uuid.uuid4().hex
    message_id = uuid.uuid4().hex

    try:
        answer = get_agent().answer(question, category=req.category)
    except Exception as exc:  # noqa: BLE001 — exponer un error legible al cliente
        raise HTTPException(status_code=502, detail=f"Error del agente: {exc}") from exc

    history = _conversations.setdefault(conversation_id, [])
    history.append({"role": "user", "content": question})
    history.append(
        {"role": "assistant", "content": answer.text, "message_id": message_id,
         "sources": answer.sources}
    )

    observability.log_qa(
        question, answer,
        conversation_id=conversation_id, message_id=message_id, category=req.category,
    )

    return AskResponse(
        answer=answer.text,
        sources=answer.sources,
        confidence=answer.confidence,
        no_answer=answer.no_answer,
        conversation_id=conversation_id,
        message_id=message_id,
    )


@app.post("/api/feedback")
def feedback(req: FeedbackRequest) -> dict:
    if req.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="rating debe ser +1 o -1.")
    observability.log_feedback(
        conversation_id=req.conversation_id,
        message_id=req.message_id,
        rating=req.rating,
        comment=req.comment,
    )
    return {"ok": True}


@app.get("/api/metrics")
def metrics() -> dict:
    return observability.metrics()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Recursos estáticos (CSS/JS). Va al final para no tapar las rutas /api.
app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
