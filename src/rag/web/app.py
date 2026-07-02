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

import time
import uuid
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import config, generation, observability
from ..answering import RagAgent
from ..extractors import supported_extensions
from ..ingest import ingest_all

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Techie - Asistente", version=config.APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Traza cada request a la API (latencia + status) para la nube (issue #8)."""
    start = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        observability.log_request(
            request.method, request.url.path, response.status_code,
            int((time.perf_counter() - start) * 1000),
        )
    return response

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
    suggestions: list[str]
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
        observability.log_error("ask", exc, conversation_id=conversation_id)
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
        suggestions=answer.suggestions,
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
@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """Sube un documento permitido (máx 20MB) y gatilla el re-indexado incremental."""
    # 1. Validar extensión
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido.")
    
    suffix = Path(file.filename).suffix.lower()
    allowed = supported_extensions()
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Soportados: {', '.join(allowed)}",
        )

    # Asegurar que el directorio de documentos existe
    config.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = config.DOCUMENTS_DIR / file.filename

    # 2. Guardar y verificar tamaño en streaming (máx. 20MB)
    max_size = 20 * 1024 * 1024  # 20 MB
    size = 0
    try:
        with open(target_path, "wb") as f:
            while chunk := await file.read(65536):
                size += len(chunk)
                if size > max_size:
                    f.close()
                    if target_path.exists():
                        target_path.unlink()
                    raise HTTPException(
                        status_code=413,
                        detail="El archivo supera el tamaño máximo permitido de 20 MB.",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=500, detail=f"Error al guardar el archivo: {exc}"
        ) from exc

    # 3. Disparar re-indexado
    try:
        results = ingest_all()
        # Buscar el resultado para este archivo en específico
        file_result = next((r for r in results if r.source_id == file.filename), None)
        
        # Si se produjo un error al indexar ESTE archivo
        if file_result and file_result.status == "error":
            raise Exception(file_result.detail)
            
        chunks_added = file_result.chunks if file_result else 0
        status = file_result.status if file_result else "indexed"
        
        return {
            "ok": True,
            "filename": file.filename,
            "size_bytes": size,
            "chunks_added": chunks_added,
            "status": status
        }
    except Exception as exc:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=500, detail=f"Error al indexar el documento: {exc}"
        ) from exc


@app.get("/api/documents")
def list_documents() -> list[dict]:
    """Lista todos los documentos locales y su estado en el índice."""
    import datetime
    
    try:
        from .. import manifest as manifest_mod
        manifest = manifest_mod.load()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error cargando manifest: {exc}")
    
    docs_dir = config.DOCUMENTS_DIR
    files = []
    if docs_dir.exists():
        for p in sorted(docs_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in supported_extensions():
                try:
                    rel = p.relative_to(docs_dir)
                    source_id = rel.as_posix()
                except ValueError:
                    source_id = p.name
                    
                stat = p.stat()
                size_bytes = stat.st_size
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc).isoformat()
                
                entry = manifest.get("sources", {}).get(source_id, {})
                
                files.append({
                    "filename": source_id,
                    "size_bytes": size_bytes,
                    "last_modified": mtime,
                    "chunks": entry.get("chunk_count", 0),
                    "last_ingested": entry.get("last_ingested"),
                    "status": "indexed" if source_id in manifest.get("sources", {}) else "not_indexed"
                })
    return files


@app.delete("/api/documents/{filename:path}")
def delete_document(filename: str) -> dict:
    """Elimina un documento del disco y del índice."""
    # Evitar path traversal
    try:
        resolved_path = (config.DOCUMENTS_DIR / filename).resolve()
        if not resolved_path.is_relative_to(config.DOCUMENTS_DIR.resolve()):
            raise ValueError("Acceso no autorizado.")
    except Exception:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido.")

    # 1. Eliminar archivo físico
    deleted_from_disk = False
    if resolved_path.exists():
        try:
            resolved_path.unlink()
            deleted_from_disk = True
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"No se pudo eliminar el archivo del disco: {exc}")
            
    # 2. Eliminar del índice vectorial (Chroma)
    try:
        chunks_deleted = get_agent().indexer.delete_document(filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al eliminar del índice vectorial: {exc}")
        
    # 3. Eliminar de manifest
    try:
        from .. import manifest as manifest_mod
        manifest = manifest_mod.load()
        if filename in manifest.get("sources", {}):
            manifest["sources"].pop(filename)
            manifest_mod.save(manifest)
    except Exception as exc:
         raise HTTPException(status_code=500, detail=f"Error al guardar manifest actualizado: {exc}")

    return {
        "ok": True,
        "filename": filename,
        "deleted_from_disk": deleted_from_disk,
        "chunks_deleted": chunks_deleted
    }


@app.post("/api/documents/reindex")
def reindex_documents(force: bool = False) -> dict:
    """Gatilla un re-indexado general de todos los documentos."""
    try:
        results = ingest_all(force=force)
        indexed = [r.source_id for r in results if r.status == "indexed"]
        unchanged = [r.source_id for r in results if r.status == "unchanged"]
        errors = [{"source_id": r.source_id, "detail": r.detail} for r in results if r.status == "error"]
        
        return {
            "ok": True,
            "indexed": indexed,
            "unchanged": unchanged,
            "errors": errors
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error durante el reindexado: {exc}")



@app.get("/api/metrics")
def metrics() -> dict:
    return observability.metrics()


@app.get("/api/version")
def version() -> dict:
    """Qué está corriendo: versión, commit, modelos y versión de prompt (issue #8)."""
    return {
        "app_version": config.APP_VERSION,
        "git_sha": config.GIT_SHA,
        "models": {
            "embedding": f"{config.EMBEDDING_PROVIDER}:{config.COHERE_MODEL}",
            "rerank": f"{config.RERANK_PROVIDER}:{config.RERANK_MODEL}",
            "generation": f"{config.GENERATION_PROVIDER}:{config.GEN_MODEL}",
        },
        "prompt_version": generation.PROMPT_VERSION,
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/panel")
def panel() -> FileResponse:
    """Panel de observabilidad (métricas en vivo)."""
    return FileResponse(STATIC_DIR / "panel.html")


# Recursos estáticos (CSS/JS). Va al final para no tapar las rutas /api.
app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
