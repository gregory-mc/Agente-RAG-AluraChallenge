"""Configuración central del pipeline de ingesta (issue #2).

Todos los valores se pueden sobreescribir con variables de entorno para no tocar
código al desplegar (issue #7 — OCI).
"""
from __future__ import annotations

import os
from pathlib import Path

# Raíz del repositorio (…/Agente-RAG-AluraChallenge)
ROOT = Path(__file__).resolve().parents[2]

# Carga variables desde .env (API keys, etc.) si está disponible.
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # python-dotenv es opcional
    pass


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

# Indexación vectorial (issue #3).
# Backend activo: "chroma" (base vectorial) | "jsonl" (respaldo en disco).
INDEXER_BACKEND: str = os.environ.get("RAG_INDEXER", "chroma")
CHROMA_DIR: Path = _path_env("RAG_CHROMA_DIR", ROOT / "chroma_db")
CHROMA_COLLECTION: str = os.environ.get("RAG_CHROMA_COLLECTION", "documentos")
# Proveedor de embeddings: "cohere" (API, recomendado para VM chica) |
# "sentence-transformers" (local, sin key, pero pesado por torch).
EMBEDDING_PROVIDER: str = os.environ.get("RAG_EMBEDDING_PROVIDER", "cohere")

# Cohere (API): modelo multilingüe y key (la key NUNCA va en el repo, solo en .env/env).
COHERE_MODEL: str = os.environ.get("RAG_COHERE_MODEL", "embed-multilingual-v3.0")
COHERE_API_KEY: str | None = os.environ.get("COHERE_API_KEY")

# Modelo de embeddings local (alternativa sentence-transformers, multiidioma).
EMBEDDING_MODEL: str = os.environ.get(
    "RAG_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
)

# Parámetros de chunking (en caracteres; el tokenizado real llega en issue #3/#4).
CHUNK_SIZE: int = int(os.environ.get("RAG_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.environ.get("RAG_CHUNK_OVERLAP", "150"))

# Timeout de descarga de documentos online.
HTTP_TIMEOUT: int = int(os.environ.get("RAG_HTTP_TIMEOUT", "30"))

# Recuperación (issue #4).
# Proveedor de reranking: "cohere" (API, más preciso) | "none" (sin rerank).
RERANK_PROVIDER: str = os.environ.get("RAG_RERANK_PROVIDER", "cohere")
RERANK_MODEL: str = os.environ.get("RAG_RERANK_MODEL", "rerank-multilingual-v3.0")
# Candidatos que trae la búsqueda vectorial antes de reordenar (velocidad).
RETRIEVAL_CANDIDATES: int = int(os.environ.get("RAG_RETRIEVAL_CANDIDATES", "20"))
# Fragmentos finales que quedan tras el reranking (calidad).
RETRIEVAL_TOP_K: int = int(os.environ.get("RAG_RETRIEVAL_TOP_K", "5"))
# Tamaño máximo del contexto ensamblado (en caracteres).
CONTEXT_MAX_CHARS: int = int(os.environ.get("RAG_CONTEXT_MAX_CHARS", "4000"))


def ensure_state_dirs() -> None:
    """Crea las carpetas de estado si no existen."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REMOTE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
