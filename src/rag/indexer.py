"""Hook de indexado.

El issue #2 produce los chunks; el issue #3 generará embeddings y los guardará en
una base vectorial (ChromaDB). Para no acoplar las dos etapas, la ingesta habla
contra esta interfaz `Indexer`. Hoy existe un `JsonlIndexer` que persiste a disco
para poder verificar el pipeline; el issue #3 aportará un `ChromaIndexer` con la
misma interfaz.

El re-indexado incremental se apoya en `delete_document(source_id)`: al cambiar un
documento se borran sus chunks viejos (por su metadato `source_id`) y se insertan
los nuevos.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Iterable

from . import config
from .models import Chunk


class Indexer(ABC):
    @abstractmethod
    def delete_document(self, source_id: str) -> int:
        """Borra todos los chunks de un documento. Devuelve cuántos borró."""

    @abstractmethod
    def add_chunks(self, chunks: Iterable[Chunk]) -> int:
        """Agrega chunks al índice. Devuelve cuántos agregó."""


class JsonlIndexer(Indexer):
    """Índice de respaldo en un archivo JSONL (un chunk por línea)."""

    def __init__(self, path=None):
        self.path = path or config.CHUNKS_PATH
        config.ensure_state_dirs()

    def _read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def _write_all(self, records: list[dict]) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def delete_document(self, source_id: str) -> int:
        records = self._read_all()
        kept = [r for r in records if r.get("metadata", {}).get("source_id") != source_id]
        removed = len(records) - len(kept)
        if removed:
            self._write_all(kept)
        return removed

    def add_chunks(self, chunks: Iterable[Chunk]) -> int:
        chunks = list(chunks)
        if not chunks:
            return 0
        with self.path.open("a", encoding="utf-8") as fh:
            for chunk in chunks:
                fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
        return len(chunks)
