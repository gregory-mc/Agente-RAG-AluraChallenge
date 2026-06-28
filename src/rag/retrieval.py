"""Capa de recuperación / RAG (issue #4).

Dada una pregunta:
    1. Búsqueda vectorial -> N candidatos cercanos (rápido).
    2. Filtro por metadatos (ej. categoría) -> se aplica en la búsqueda.
    3. Reranking -> reordena por relevancia y se queda con los top_k (calidad).
    4. Armado del contexto final, con la referencia al origen de cada fragmento.

El resultado alimenta al generador del issue #5 (la respuesta en lenguaje natural).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import config
from .chroma_indexer import ChromaIndexer
from .reranking import Reranker, get_reranker


@dataclass
class RetrievedChunk:
    """Un fragmento recuperado, con su puntaje y procedencia."""

    text: str
    metadata: dict[str, Any]
    vector_distance: float | None = None
    rerank_score: float | None = None

    @property
    def source(self) -> str:
        """Referencia legible al origen (archivo o URL)."""
        md = self.metadata
        return md.get("location") or md.get("file") or md.get("source_id") or "desconocido"


@dataclass
class RetrievalResult:
    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    context: str = ""
    sources: list[str] = field(default_factory=list)


class Retriever:
    def __init__(
        self, indexer: ChromaIndexer | None = None, reranker: Reranker | None = None
    ):
        self.indexer = indexer or ChromaIndexer()
        self.reranker = reranker or get_reranker()

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        candidates: int | None = None,
        where: dict[str, Any] | None = None,
        max_chars: int | None = None,
    ) -> RetrievalResult:
        top_k = top_k or config.RETRIEVAL_TOP_K
        candidates = candidates or config.RETRIEVAL_CANDIDATES

        # 1-2. Búsqueda vectorial (con filtro de metadatos) -> candidatos.
        hits = self.indexer.query(query, n_results=candidates, where=where)

        # 3. Reranking -> top_k por relevancia.
        ranked = self.reranker.rerank(query, hits, top_k)

        chunks = [
            RetrievedChunk(
                text=h["text"],
                metadata=h.get("metadata", {}),
                vector_distance=h.get("distance"),
                rerank_score=h.get("rerank_score"),
            )
            for h in ranked
        ]

        # 4. Armado del contexto con citas.
        context, sources = self._build_context(chunks, max_chars or config.CONTEXT_MAX_CHARS)
        return RetrievalResult(query=query, chunks=chunks, context=context, sources=sources)

    @staticmethod
    def _build_context(chunks: list[RetrievedChunk], max_chars: int) -> tuple[str, list[str]]:
        """Concatena los fragmentos numerados con su fuente, hasta `max_chars`."""
        blocks: list[str] = []
        sources: list[str] = []
        used = 0
        for i, chunk in enumerate(chunks, start=1):
            src = chunk.source
            block = f"[{i}] (fuente: {src})\n{chunk.text.strip()}"
            if used + len(block) > max_chars and blocks:
                break  # respeta el presupuesto de contexto
            blocks.append(block)
            sources.append(src)
            used += len(block)
        return "\n\n".join(blocks), sources
