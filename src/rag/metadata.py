"""Construcción de metadatos por fragmento.

Cada chunk arrastra metadatos de catálogo (categoría, archivo, fecha, autor,
ubicación) que luego permiten filtrar y citar las fuentes en la respuesta
(issues #4 y #5).
"""
from __future__ import annotations

import hashlib
from typing import Any


def chunk_id(source_id: str, index: int) -> str:
    """ID estable y único por (documento, posición del fragmento)."""
    digest = hashlib.sha1(f"{source_id}#{index}".encode("utf-8")).hexdigest()[:16]
    return f"{source_id}::{index:04d}::{digest}"


def build_metadata(
    *,
    source_id: str,
    file_name: str,
    category: str,
    location: str,
    fetched_at: str,
    doc_meta: dict[str, Any],
    chunk_index: int,
    chunk_count: int,
) -> dict[str, Any]:
    """Arma el dict de metadatos para un fragmento concreto."""
    return {
        # Identidad del documento de origen (clave del re-indexado incremental).
        "source_id": source_id,
        "file": file_name,
        "category": category,
        "location": location,           # ruta local o URL de origen
        "format": doc_meta.get("format"),
        "author": doc_meta.get("author"),
        "title": doc_meta.get("title"),
        "date": fetched_at,             # fecha de la última ingesta (ISO 8601)
        # Posición del fragmento dentro del documento.
        "chunk_index": chunk_index,
        "chunk_count": chunk_count,
    }
