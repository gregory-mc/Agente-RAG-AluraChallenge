"""Caché persistente de embeddings en JSON (disk-based).

Implementación simple usando hash SHA256 del texto como clave primária.
El caché persiste entre reinicios, evitando llamadas repetidas a la API.

Para production cross-process: ver docs/03-indexacion.md section caché.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import typing

CACHE_DIR = pathlib.Path.home() / ".rag" / "embed_cache"

CachePathDict = typing.Dict[str, typing.Tuple[int, bytes]]


def cache_path(path: pathlib.Path | None = None) -> pathlib.Path:
    """Ruta base de caché (home/.rag/embed_cache/)."""
    return path or CACHE_DIR


def cache_file() -> pathlib.Path:
    """Archivo JSON para persistencia de embeddings."""
    p = cache_path() / "embeddings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def cache_key(text: str) -> str:
    """Clave hash SHA256 única para el texto."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cached_embedding(text: str) -> list[float] | None:
    """Carga embedding guardado para el texto, si existe.

    Retorna None si no está en caché o archivo inválido/corrupto.

    Pattern: append-only con reparseo de todo (simple, no necesita LRU).
    """
    pf = cache_file()
    try:
        if not pf.exists():
            return None
        
        for line in pf.open("r", encoding="utf-8"):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                if rec.get("_key") == cache_key(text):
                    return rec["vectors"]
            except json.JSONDecodeError:
                # Saltar lineas corruptas
                continue
        
        # No encontrado
        return None
    except IOError:
        return None


def save_cached_embedding(
    text: str, 
    vectors: list[float], 
    metadata: dict[str, typing.Any] | None = None
) -> bool:
    """Guarda embedding para el texto.

    Pattern: append-only (evitamos sobrescribir). Para reindexar todo,
    ejecutar con --force o reiniciar caché explícitamente.

    Retorna True si éxito; False si error IO.
    """
    pf = cache_file()
    try:
        key = cache_key(text)
        
        record = {
            "_key": key,
            "vectors": vectors,
            "metadata": metadata or {},
            # Timestamp para depuracion
            "_ts": None,  # No usar utcnow si queremos pure storage
        }
        
        with pf.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except (IOError, OSError):
        return False


def clear_cache() -> int:
    """Reinicio de caché. Devuelve numero items cacheados anteriores."""
    try:
        pf = cache_file()
        count = 0
        
        if pf.exists():
            with pf.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line) if line.strip() else None
                        if isinstance(rec, dict) and "_key" in rec:
                            count += 1
                    except (json.JSONDecodeError, TypeError):
                        continue
        
        # Crear archivo vacío
        with pf.open("w", encoding="utf-8"):
            pass
        
        return count
    except IOError:
        return 0


def get_cached_keys() -> typing.List[str]:
    """Devuelve lista de hashes cacheados (para diagnosticado)."""
    try:
        pf = cache_file()
        if not pf.exists():
            return []
        
        keys: list[str] = []
        for line in pf.open("r", encoding="utf-8"):
            if line.strip():
                try:
                    rec = json.loads(line)
                    if isinstance(rec, dict) and "_key" in rec:
                        keys.append(rec["_key"])
                except json.JSONDecodeError:
                    continue
        
        return sorted(keys)
    except IOError:
        return []


__all__ = [
    "cache_path",
    "cache_file", 
    "cache_key",
    "load_cached_embedding",
    "save_cached_embedding",
    "clear_cache",
    "get_cached_keys",
]
