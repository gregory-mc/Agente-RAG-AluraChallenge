"""Configuración central del pipeline de ingesta (issue #2).

Todos los valores se pueden sobreescribir con variables de entorno para no tocar
código al desplegar (issue #7 — OCI).
"""
from __future__ import annotations

import os
from pathlib import Path

# Raíz del repositorio (…/Agente-RAG-AluraChallenge)
ROOT = Path(__file__).resolve().parents[2]


def _path_env(var: str, default: Path) -> Path:
    return Path(os.environ[var]).expanduser() if os.environ.get(var) else default


# Carpeta única de verdad para documentos locales (ver issue #1).
DOCUMENTS_DIR: Path = _path_env("RAG_DOCUMENTS_DIR", ROOT / "data" / "documents")

# Estado de la ingesta: manifest de cambios + salida del índice (stub issue #3).
STATE_DIR: Path = _path_env("RAG_STATE_DIR", ROOT / "data" / "state")
MANIFEST_PATH: Path = STATE_DIR / "manifest.json"
CHUNKS_PATH: Path = STATE_DIR / "chunks.jsonl"

# Caché local de documentos descargados desde una URL.
REMOTE_CACHE_DIR: Path = STATE_DIR / "remote_cache"

# Parámetros de chunking (en caracteres; el tokenizado real llega en issue #3/#4).
CHUNK_SIZE: int = int(os.environ.get("RAG_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.environ.get("RAG_CHUNK_OVERLAP", "150"))

# Timeout de descarga de documentos online.
HTTP_TIMEOUT: int = int(os.environ.get("RAG_HTTP_TIMEOUT", "30"))


def ensure_state_dirs() -> None:
    """Crea las carpetas de estado si no existen."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REMOTE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
