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

# Marcador que separa la respuesta de las sugerencias de seguimiento.
FOLLOWUP_MARKER = "###SIGUIENTES###"

# Instrucciones anti-alucinación + tono. El modelo queda "anclado" al contexto.
SYSTEM_PROMPT = (
    "Sos un asistente corporativo cálido y servicial que ayuda a los "
    "colaboradores respondiendo con la información de los documentos internos "
    "que se te entregan como CONTEXTO.\n\n"
    "Tono: amable, cercano y profesional. Saludá brevemente cuando quede natural, "
    "usá un lenguaje claro y positivo, y cerrá ofreciendo seguir ayudando. Sin "
    "exagerar ni inventar.\n\n"
    "Reglas estrictas:\n"
    "1. Respondé solo con datos presentes en el CONTEXTO. No uses conocimiento "
    "externo ni inventes datos, cifras, nombres ni fechas.\n"
    "2. Citá la fuente de cada afirmación con el marcador correspondiente [n], "
    "tal como aparece en el CONTEXTO (por ejemplo: 'El plan Business cuesta 18 "
    "USD [2].').\n"
    "3. Si el CONTEXTO no contiene la información necesaria, respondé con amabilidad "
    "exactamente: '{no_answer}'. No intentes adivinar.\n"
    "4. Sé claro y conciso, y respondé en el mismo idioma de la pregunta.\n"
    "5. Al final, en una línea aparte, escribí exactamente '" + FOLLOWUP_MARKER + "' "
    "y luego hasta 3 preguntas de seguimiento breves y útiles que el colaborador "
    "podría querer hacer, una por línea con guion (-). Deben poder responderse con "
    "los documentos internos. No las cites ni las numeres."
)


@dataclass
class Answer:
    """Respuesta generada, con su procedencia y señales para mantenimiento."""

    text: str
    sources: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
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
        raw = _extract_text(resp).strip()
        text, suggestions = _split_followups(raw)
        latency = int((time.perf_counter() - start) * 1000)
        no_answer = self._looks_like_no_answer(text)
        if no_answer:
            sources = []
        else:
            text, sources = _remap_citations(text, retrieval.sources)
        return Answer(
            text=text,
            sources=sources,
            suggestions=suggestions,
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


_FOLLOWUP_SPLIT = re.compile(r"#{2,3}\s*SIGUIENTES\s*#{0,3}", re.IGNORECASE)


def _split_followups(raw: str) -> tuple[str, list[str]]:
    """Separa la respuesta de las preguntas de seguimiento (marcador FOLLOWUP)."""
    parts = _FOLLOWUP_SPLIT.split(raw, maxsplit=1)
    if len(parts) == 1:
        return raw.strip(), []
    answer = parts[0].strip()
    suggestions: list[str] = []
    for line in parts[1].splitlines():
        line = line.strip().lstrip("-•*0123456789. ").strip()
        if line:
            suggestions.append(line)
    return answer, suggestions[:3]


_CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _remap_citations(text: str, all_sources: list[str]) -> tuple[str, list[str]]:
    """Deja solo las fuentes citadas y renumera para que el texto y la lista coincidan.

    El modelo cita ``[n]`` según el orden del CONTEXTO, pero a la UI solo le
    mostramos las fuentes efectivamente citadas. Para que el ``[n]`` del texto
    apunte a la misma posición de la lista, se renumeran ambos: la primera fuente
    citada pasa a ser [1], la segunda [2], etc. Si el modelo no citó nada, se cae
    a todas las fuentes recuperadas sin tocar el texto.
    """
    order: dict[int, int] = {}          # índice original (0-based) -> nuevo número
    by_source: dict[str, int] = {}      # fuente -> nuevo número (dedup por archivo)
    cited: list[str] = []
    for group in _CITE_RE.findall(text):
        for num in group.split(","):
            idx = int(num.strip()) - 1
            if not (0 <= idx < len(all_sources)) or idx in order:
                continue
            src = all_sources[idx]
            if src not in by_source:            # primera vez que aparece este archivo
                by_source[src] = len(cited) + 1
                cited.append(src)
            order[idx] = by_source[src]
    if not cited:
        return text, list(all_sources)

    def _sub(match: re.Match) -> str:
        nums = sorted({str(order[int(n) - 1]) for n in match.group(1).split(",")
                       if int(n) - 1 in order})
        return "[" + ",".join(nums) + "]" if nums else ""

    return _CITE_RE.sub(_sub, text), cited


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
