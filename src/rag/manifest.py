"""Manifest de ingesta: estado conocido de cada documento.

Cumple dos funciones:
  1. Registro de las fuentes URL que hay que vigilar (no viven en disco).
  2. Última huella/validadores conocidos de cada fuente, para detectar cambios
     sin re-procesar lo que no cambió.
"""
from __future__ import annotations

import json
from typing import Any

from . import config


def load() -> dict[str, Any]:
    if config.MANIFEST_PATH.exists():
        return json.loads(config.MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"sources": {}}


def save(manifest: dict[str, Any]) -> None:
    config.ensure_state_dirs()
    config.MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_entry(manifest: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    return manifest.get("sources", {}).get(source_id)


def upsert_entry(manifest: dict[str, Any], source_id: str, data: dict[str, Any]) -> None:
    manifest.setdefault("sources", {})[source_id] = data


def register_url(
    manifest: dict[str, Any], *, source_id: str, url: str, category: str
) -> bool:
    """Da de alta una URL a vigilar. Devuelve True si es nueva."""
    sources = manifest.setdefault("sources", {})
    if source_id in sources:
        return False
    sources[source_id] = {
        "kind": "url",
        "url": url,
        "location": url,
        "category": category,
        "fingerprint": None,
        "validators": {},
        "cache_file": None,
        "chunk_count": 0,
        "last_ingested": None,
    }
    return True


def url_sources(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Entradas de tipo URL registradas (con su source_id incluido)."""
    out = []
    for source_id, entry in manifest.get("sources", {}).items():
        if entry.get("kind") == "url":
            out.append({"source_id": source_id, **entry})
    return out
