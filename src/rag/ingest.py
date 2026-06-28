"""Orquestador de ingesta (issue #2).

Flujo por documento:
    fuente -> fetch (detecta cambios) -> extraer -> limpiar -> chunkear
           -> metadatos -> re-indexado incremental (delete + add)

Solo se re-procesan los documentos que cambiaron desde la última ingesta.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config, manifest as manifest_mod, metadata as meta_mod
from .chunking import chunk_text
from .cleaning import clean_text
from .extractors import ExtractionError, get_extractor, supported_extensions
from .indexer import Indexer, JsonlIndexer
from .models import Chunk
from .sources import LocalSource, Source, UrlSource


@dataclass
class IngestResult:
    source_id: str
    status: str            # "indexed" | "unchanged" | "error"
    chunks: int = 0
    detail: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def discover_local_sources() -> list[LocalSource]:
    """Encuentra todos los documentos soportados dentro de data/documents/."""
    exts = set(supported_extensions())
    docs_dir = config.DOCUMENTS_DIR
    if not docs_dir.exists():
        return []
    sources = [
        LocalSource(p)
        for p in sorted(docs_dir.rglob("*"))
        if p.is_file() and p.suffix.lower() in exts
    ]
    return sources


def _build_chunks(source: Source, fetch, fetched_at: str) -> list[Chunk]:
    extractor = get_extractor(fetch.path)
    doc = extractor.extract(fetch.path)
    text = clean_text(doc.text)
    pieces = chunk_text(text)

    chunks: list[Chunk] = []
    for i, piece in enumerate(pieces):
        md = meta_mod.build_metadata(
            source_id=source.source_id,
            file_name=fetch.file_name,
            category=source.category,
            location=source.location,
            fetched_at=fetched_at,
            doc_meta=doc.meta,
            chunk_index=i,
            chunk_count=len(pieces),
        )
        chunks.append(Chunk(id=meta_mod.chunk_id(source.source_id, i), text=piece, metadata=md))
    return chunks


def ingest_source(
    source: Source,
    manifest: dict[str, Any],
    indexer: Indexer,
    *,
    force: bool = False,
) -> IngestResult:
    """Ingesta un único documento si cambió (o si force=True)."""
    known = manifest_mod.get_entry(manifest, source.source_id)
    try:
        fetch = source.fetch(known)
    except Exception as exc:  # red, 404, etc.
        return IngestResult(source.source_id, "error", detail=f"fetch: {exc}")

    if not force and known is not None and not fetch.changed:
        return IngestResult(source.source_id, "unchanged")

    fetched_at = _now_iso()
    try:
        chunks = _build_chunks(source, fetch, fetched_at)
    except ExtractionError as exc:
        return IngestResult(source.source_id, "error", detail=str(exc))

    # Re-indexado incremental: fuera los chunks viejos de este documento, dentro los nuevos.
    indexer.delete_document(source.source_id)
    added = indexer.add_chunks(chunks)

    manifest_mod.upsert_entry(
        manifest,
        source.source_id,
        {
            "kind": source.kind,
            "location": source.location,
            "category": source.category,
            "url": getattr(source, "url", None),
            "fingerprint": fetch.fingerprint,
            "validators": fetch.validators,
            "cache_file": str(fetch.path) if source.kind == "url" else None,
            "chunk_count": added,
            "last_ingested": fetched_at,
        },
    )
    return IngestResult(source.source_id, "indexed", chunks=added)


def ingest_all(*, indexer: Indexer | None = None, force: bool = False) -> list[IngestResult]:
    """Ingesta todas las fuentes (locales descubiertas + URLs registradas)."""
    indexer = indexer or JsonlIndexer()
    manifest = manifest_mod.load()

    sources: list[Source] = list(discover_local_sources())
    for entry in manifest_mod.url_sources(manifest):
        sources.append(
            UrlSource(entry["url"], category=entry.get("category", "online"),
                      source_id=entry["source_id"])
        )

    results = [ingest_source(s, manifest, indexer, force=force) for s in sources]
    manifest_mod.save(manifest)
    return results
