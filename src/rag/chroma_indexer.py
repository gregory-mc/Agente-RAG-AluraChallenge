"""ChromaIndexer — implementación de `Indexer` sobre ChromaDB (issue #3).

Guarda cada chunk como un embedding en una colección persistente de ChromaDB.
Chroma indexa los vectores con HNSW (búsqueda aproximada por vecinos más
cercanos) e indexa los metadatos aparte, lo que permite filtrar por categoría,
archivo, etc.

Los embeddings los calcula un `Embedder` (Cohere por API o sentence-transformers
local) y se pasan explícitamente a Chroma. Esto permite usar el `input_type`
correcto de Cohere ("search_document" al indexar, "search_query" al consultar).
"""
from __future__ import annotations

from typing import Any, Iterable

from . import config
from .embeddings import Embedder, get_embedder
from .indexer import Indexer
from .models import Chunk

# Tipos escalares que ChromaDB acepta en metadatos (no admite None ni listas).
_SCALAR = (str, int, float, bool)


def _sanitize(metadata: dict[str, Any]) -> dict[str, Any]:
    """Deja solo valores escalares no nulos (requisito de ChromaDB)."""
    return {k: v for k, v in metadata.items() if isinstance(v, _SCALAR) and v is not None}


class ChromaIndexer(Indexer):
    def __init__(self, *, persist_dir=None, collection=None, embedder: Embedder | None = None):
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Falta dependencia: chromadb") from exc

        persist_dir = persist_dir or config.CHROMA_DIR
        persist_dir.mkdir(parents=True, exist_ok=True)
        collection_name = collection or config.CHROMA_COLLECTION

        self.embedder = embedder or get_embedder()
        self._client = chromadb.PersistentClient(path=str(persist_dir))

        # Si la colección existe pero fue creada con OTRO embedder, los vectores
        # tienen otra dimensión y son incompatibles: se recrea desde cero.
        existing = self._get_collection_if_exists(collection_name)
        if existing is not None and existing.metadata.get("embedder") != self.embedder.name:
            print(
                f"⚠ La colección '{collection_name}' fue creada con "
                f"'{existing.metadata.get('embedder')}' y ahora se usa "
                f"'{self.embedder.name}'. Se recrea (hay que reindexar con --force)."
            )
            self._client.delete_collection(collection_name)
            existing = None

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "embedder": self.embedder.name},
        )

    def _get_collection_if_exists(self, name: str):
        try:
            return self._client.get_collection(name)
        except Exception:
            return None

    def delete_document(self, source_id: str) -> int:
        existing = self._collection.get(where={"source_id": source_id})
        ids = existing.get("ids", [])
        if ids:
            self._collection.delete(where={"source_id": source_id})
        return len(ids)

    def add_chunks(self, chunks: Iterable[Chunk]) -> int:
        chunks = list(chunks)
        if not chunks:
            return 0
        embeddings = self.embedder.embed_documents([c.text for c in chunks])
        self._collection.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[_sanitize(c.metadata) for c in chunks],
        )
        return len(chunks)

    # --- utilidades de verificación / soporte a la capa de recuperación (issue #4) ---

    def count(self) -> int:
        return self._collection.count()

    def query(
        self, text: str, n_results: int = 5, where: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Devuelve los chunks más cercanos a la consulta, con distancia y metadatos."""
        query_embedding = self.embedder.embed_query(text)
        res = self._collection.query(
            query_embeddings=[query_embedding], n_results=n_results, where=where or None
        )
        hits: list[dict[str, Any]] = []
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            hits.append({"text": doc, "metadata": meta, "distance": dist})
        return hits
