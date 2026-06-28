"""Fuente remota: un documento accesible por URL (HTTP/HTTPS).

Soporta detección de cambios de dos maneras complementarias:
  1. Validadores HTTP (ETag / Last-Modified) vía petición condicional -> 304.
  2. Hash del contenido descargado, como respaldo si el servidor no da validadores.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .. import config
from .base import FetchResult, Source

# Content-Type -> extensión, para elegir el extractor correcto.
_CONTENT_TYPE_EXT = {
    "application/pdf": ".pdf",
    "text/html": ".html",
    "application/xhtml+xml": ".html",
    "text/csv": ".csv",
    "application/json": ".json",
    "text/markdown": ".md",
    "text/plain": ".md",
    "text/csv; charset=utf-8": ".csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(url: str) -> str:
    parsed = urlparse(url)
    base = f"{parsed.netloc}{parsed.path}".strip("/") or parsed.netloc
    return _SAFE.sub("_", base)[:120] or "remote"


def _guess_extension(url: str, content_type: str | None) -> str:
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in _CONTENT_TYPE_EXT:
            return _CONTENT_TYPE_EXT[ct]
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix:
        return suffix
    return ".html"  # por defecto asumimos página web


class UrlSource(Source):
    kind = "url"

    def __init__(self, url: str, category: str = "online", source_id: str | None = None):
        self.url = url
        self.location = url
        self.category = category
        self.source_id = source_id or f"url:{_slug(url)}"

    def fetch(self, known: dict[str, Any] | None = None) -> FetchResult:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Falta dependencia: requests") from exc

        known = known or {}
        prev_validators = known.get("validators", {})
        headers: dict[str, str] = {}
        if prev_validators.get("etag"):
            headers["If-None-Match"] = prev_validators["etag"]
        if prev_validators.get("last_modified"):
            headers["If-Modified-Since"] = prev_validators["last_modified"]

        config.ensure_state_dirs()
        resp = requests.get(
            self.url, headers=headers, timeout=config.HTTP_TIMEOUT, allow_redirects=True
        )

        # El servidor confirma que no cambió: reutilizamos la copia en caché.
        if resp.status_code == 304 and known.get("cache_file"):
            cached = Path(known["cache_file"])
            if cached.exists():
                return FetchResult(
                    path=cached,
                    file_name=cached.name,
                    fingerprint=known.get("fingerprint", ""),
                    changed=False,
                    validators=prev_validators,
                )

        resp.raise_for_status()
        content = resp.content
        fingerprint = hashlib.sha256(content).hexdigest()

        ext = _guess_extension(self.url, resp.headers.get("Content-Type"))
        cache_path = config.REMOTE_CACHE_DIR / f"{_slug(self.url)}{ext}"
        cache_path.write_bytes(content)

        validators = {
            "etag": resp.headers.get("ETag"),
            "last_modified": resp.headers.get("Last-Modified"),
        }
        return FetchResult(
            path=cache_path,
            file_name=cache_path.name,
            fingerprint=fingerprint,
            changed=fingerprint != known.get("fingerprint"),
            validators=validators,
        )
