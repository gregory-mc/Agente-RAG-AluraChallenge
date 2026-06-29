"""Orquestador end-to-end del agente RAG (issue #5).

Une las piezas ya existentes en un único punto de entrada:

    pregunta ──> recuperación (#4) ──> umbral de confianza ──> generación (#5)

`RagAgent.answer()` es lo que consumen tanto el CLI (`rag ask`) como la interfaz
web (issue #6).
"""
from __future__ import annotations

from typing import Any

from . import config
from .generation import Answer, Generator, get_generator
from .retrieval import RetrievalResult, Retriever


def _confidence(retrieval: RetrievalResult) -> float | None:
    """Confianza = mejor similitud vectorial entre los fragmentos recuperados.

    Se usa la similitud coseno (``1 - distancia``) y NO el ``rerank_score``: el
    score del reranker no está calibrado a un rango fijo (solo sirve para ordenar,
    ver docs/04), mientras que la similitud vectorial sí es comparable contra un
    umbral. Devuelve None si no hay señal disponible (no se aplica el umbral).
    """
    sims = [
        1.0 - float(c.vector_distance)
        for c in retrieval.chunks
        if c.vector_distance is not None
    ]
    return max(sims) if sims else None


class RagAgent:
    def __init__(
        self, retriever: Retriever | None = None, generator: Generator | None = None
    ):
        self.retriever = retriever or Retriever()
        self.generator = generator or get_generator()

    def answer(self, question: str, *, category: str | None = None) -> Answer:
        where: dict[str, Any] | None = {"category": category} if category else None
        retrieval = self.retriever.retrieve(question, where=where)
        confidence = _confidence(retrieval)

        # Umbral de confianza: si no recuperamos nada relevante, no llamamos al
        # LLM y devolvemos "no sé" (issue #5: evitar alucinaciones).
        below_threshold = confidence is not None and confidence < config.CONFIDENCE_MIN
        if not retrieval.chunks or below_threshold:
            return Answer(
                text=config.NO_ANSWER_MESSAGE,
                sources=[],
                confidence=confidence,
                no_answer=True,
                model=self.generator.name,
            )

        ans = self.generator.generate(question, retrieval)
        ans.confidence = confidence
        return ans
