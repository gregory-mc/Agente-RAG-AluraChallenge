"""Embedders: convierten texto en vectores.

Dos implementaciones intercambiables (issue #3):
  - CohereEmbedder: API multilingüe (embed-multilingual-v3.0). Liviano en la VM
    porque el cómputo ocurre en la nube de Cohere — ideal para el deploy en una
    instancia chica de OCI (issue #7).
  - SentenceTransformerEmbedder: modelo local, sin API key, pero pesado (torch).

Cohere v3 distingue el `input_type`: los documentos se embeben como
"search_document" y las consultas como "search_query", lo que mejora la
recuperación. Por eso el `Embedder` separa `embed_documents` de `embed_query`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from . import config

# Cohere acepta como máximo 96 textos por llamada al endpoint de embeddings.
_COHERE_BATCH = 96


class Embedder(ABC):
    #: nombre estable (proveedor:modelo) — se guarda junto a la colección
    name: str

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Vectoriza fragmentos de documentos para indexar."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Vectoriza la consulta del usuario para buscar."""


class CohereEmbedder(Embedder):
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
        self.model = model or config.COHERE_MODEL
        self.name = f"cohere:{self.model}"
        self._client = cohere.ClientV2(api_key=api_key)

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _COHERE_BATCH):
            batch = texts[i : i + _COHERE_BATCH]
            resp = self._client.embed(
                texts=batch,
                model=self.model,
                input_type=input_type,
                embedding_types=["float"],
            )
            emb = resp.embeddings
            # El SDK expone los vectores float según versión: .float o .float_.
            floats = getattr(emb, "float", None) or getattr(emb, "float_", None) or emb
            vectors.extend(list(floats))
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "search_document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "search_query")[0]


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str | None = None):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Falta dependencia: sentence-transformers") from exc

        model_name = model_name or config.EMBEDDING_MODEL
        self.name = f"st:{model_name}"
        self._model = SentenceTransformer(model_name)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]


def get_embedder(provider: str | None = None) -> Embedder:
    """Crea el embedder según el proveedor configurado."""
    provider = (provider or config.EMBEDDING_PROVIDER).lower()
    if provider == "cohere":
        return CohereEmbedder()
    if provider in ("sentence-transformers", "st", "local"):
        return SentenceTransformerEmbedder()
    raise ValueError(
        f"Proveedor de embeddings desconocido: {provider!r} "
        "(usá 'cohere' o 'sentence-transformers')"
    )
