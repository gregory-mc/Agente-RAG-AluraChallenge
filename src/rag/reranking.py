"""Rerankers: reordenan los candidatos de la búsqueda vectorial por relevancia.

La búsqueda vectorial es rápida pero aproximada. Un modelo de reranking compara
la consulta contra cada candidato de forma más precisa (cross-encoder) y los
reordena. El issue #4 busca ese equilibrio: traer muchos candidatos rápido por
vectores y quedarse con los mejores por calidad.

Dos implementaciones intercambiables:
  - CohereReranker: API `rerank-multilingual-v3.0` (multiidioma).
  - PassthroughReranker: mantiene el orden vectorial (sin costo de API).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from . import config

_COHERE_RERANK_MAX = 1000  # máximo de documentos por llamada al endpoint de rerank


class Reranker(ABC):
    name: str

    @abstractmethod
    def rerank(
        self, query: str, candidates: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]:
        """Devuelve los `top_k` candidatos más relevantes, reordenados.

        Cada candidato es un dict con al menos "text" y "metadata". El resultado
        agrega "rerank_score" (cuando aplica) y conserva el resto de los campos.
        """


class CohereReranker(Reranker):
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
        self.model = model or config.RERANK_MODEL
        self.name = f"cohere:{self.model}"
        self._client = cohere.ClientV2(api_key=api_key)

    def rerank(
        self, query: str, candidates: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        docs = [c["text"] for c in candidates[:_COHERE_RERANK_MAX]]
        resp = self._client.rerank(
            model=self.model, query=query, documents=docs, top_n=top_k
        )
        ranked: list[dict[str, Any]] = []
        for item in resp.results:
            candidate = dict(candidates[item.index])
            candidate["rerank_score"] = item.relevance_score
            ranked.append(candidate)
        return ranked


class PassthroughReranker(Reranker):
    """No reordena: conserva el orden de la búsqueda vectorial (fallback sin API)."""

    name = "passthrough"

    def rerank(
        self, query: str, candidates: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]:
        return candidates[:top_k]


def get_reranker(provider: str | None = None) -> Reranker:
    provider = (provider or config.RERANK_PROVIDER).lower()
    if provider == "cohere":
        return CohereReranker()
    if provider in ("none", "passthrough", "off"):
        return PassthroughReranker()
    raise ValueError(
        f"Proveedor de reranking desconocido: {provider!r} (usá 'cohere' o 'none')"
    )
