"""Generación de respuestas (issue #5).

Toma la pregunta y el contexto recuperado (issue #4) y produce la respuesta en
lenguaje natural. El foco del issue es **reducir alucinaciones**:

  - El modelo responde **solo** con el contexto entregado.
  - **Cita** las fuentes con marcadores ``[n]`` que mapean a `RetrievalResult.sources`.
  - Si la respuesta no está en el contexto, lo **dice** en vez de inventar.

Dos implementaciones intercambiables, mismo patrón que `embeddings`/`reranking`:
  - `CohereGenerator`: API `chat` de Cohere (Command-R), misma key que el resto.
  - `EchoGenerator`: sin API, arma una respuesta a partir del contexto (dev/tests).
"""
from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from . import config
from .retrieval import RetrievalResult

# Instrucciones anti-alucinación. El modelo queda "anclado" al contexto.
SYSTEM_PROMPT = (
    "Sos un asistente corporativo que responde preguntas de los colaboradores "
    "usando EXCLUSIVAMENTE la información de los documentos internos que se te "
    "entregan como CONTEXTO.\n\n"
    "Reglas estrictas:\n"
    "1. Respondé solo con datos presentes en el CONTEXTO. No uses conocimiento "
    "externo ni inventes datos, cifras, nombres ni fechas.\n"
    "2. Citá la fuente de cada afirmación con el marcador correspondiente [n], "
    "tal como aparece en el CONTEXTO (por ejemplo: 'El plan Business cuesta 18 "
    "USD [2].').\n"
    "3. Si el CONTEXTO no contiene la información necesaria para responder, "
    "respondé textualmente: '{no_answer}'. No intentes adivinar.\n"
    "4. Sé claro y conciso, y respondé en el mismo idioma de la pregunta."
)


@dataclass
class Answer:
    """Respuesta generada, con su procedencia y señales para mantenimiento."""

    text: str
    sources: list[str] = field(default_factory=list)
    confidence: float | None = None
    no_answer: bool = False
    model: str = ""
    latency_ms: int = 0


class Generator(ABC):
    name: str

    @abstractmethod
    def generate(self, question: str, retrieval: RetrievalResult) -> Answer:
        """Genera la respuesta a partir de la pregunta y el contexto recuperado."""

    def _no_answer_text(self) -> str:
        return config.NO_ANSWER_MESSAGE


class CohereGenerator(Generator):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        try:
            import cohere
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Falta dependencia: cohere") from exc

        api_key = api_key or config.COHERE_API_KEY
        if not api_key:
            raise RuntimeError(
                "Falta COHERE_API_KEY. Definila en .env o como variable de entorno."
            )
        self.model = model or config.GEN_MODEL
        self.name = f"cohere:{self.model}"
        self._client = cohere.ClientV2(api_key=api_key)

    def generate(self, question: str, retrieval: RetrievalResult) -> Answer:
        start = time.perf_counter()
        system = SYSTEM_PROMPT.format(no_answer=self._no_answer_text())
        user = (
            f"CONTEXTO:\n{retrieval.context}\n\n"
            f"PREGUNTA: {question}\n\n"
            "Respondé siguiendo las reglas, citando las fuentes con [n]."
        )
        resp = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=config.GEN_TEMPERATURE,
        )
        text = _extract_text(resp).strip()
        latency = int((time.perf_counter() - start) * 1000)
        no_answer = self._looks_like_no_answer(text)
        sources = [] if no_answer else _cited_sources(text, retrieval.sources)
        return Answer(
            text=text,
            sources=sources,
            no_answer=no_answer,
            model=self.name,
            latency_ms=latency,
        )

    def _looks_like_no_answer(self, text: str) -> bool:
        marker = self._no_answer_text().lower()[:30]
        return marker in text.lower()


class EchoGenerator(Generator):
    """Sin LLM: arma una respuesta determinista desde el contexto (dev/tests)."""

    name = "echo"

    def generate(self, question: str, retrieval: RetrievalResult) -> Answer:
        if not retrieval.context.strip():
            return Answer(text=self._no_answer_text(), no_answer=True, model=self.name)
        text = (
            "(modo echo, sin LLM) Según los documentos recuperados:\n\n"
            f"{retrieval.context}"
        )
        return Answer(text=text, sources=list(retrieval.sources), model=self.name)


_CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _cited_sources(text: str, all_sources: list[str]) -> list[str]:
    """Devuelve solo las fuentes efectivamente citadas con [n] en la respuesta.

    Mapea cada marcador ``[n]`` (admite ``[1,2]``) a `all_sources[n-1]`,
    conservando el orden de aparición y sin repetir. Si el modelo no citó nada,
    cae a todas las fuentes recuperadas (mejor mostrar de más que de menos).
    """
    cited: list[str] = []
    for group in _CITE_RE.findall(text):
        for num in group.split(","):
            idx = int(num.strip()) - 1
            if 0 <= idx < len(all_sources) and all_sources[idx] not in cited:
                cited.append(all_sources[idx])
    return cited or list(all_sources)


def _extract_text(resp) -> str:
    """Extrae el texto de la respuesta de `chat` (lista de bloques de contenido)."""
    msg = getattr(resp, "message", None)
    if msg is None:
        return str(resp)
    content = getattr(msg, "content", None) or []
    return "".join(getattr(block, "text", "") or "" for block in content)


def get_generator(provider: str | None = None) -> Generator:
    """Crea el generador según el proveedor configurado."""
    provider = (provider or config.GENERATION_PROVIDER).lower()
    if provider == "cohere":
        return CohereGenerator()
    if provider in ("echo", "none", "off"):
        return EchoGenerator()
    raise ValueError(
        f"Proveedor de generación desconocido: {provider!r} (usá 'cohere' o 'echo')"
    )
