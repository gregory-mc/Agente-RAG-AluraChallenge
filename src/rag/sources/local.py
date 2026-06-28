"""Fuente local: un archivo dentro de data/documents/."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .. import config
from .base import FetchResult, Source


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


class LocalSource(Source):
    kind = "local"

    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        # source_id relativo a la carpeta de documentos (estable y legible).
        try:
            rel = self.path.relative_to(config.DOCUMENTS_DIR.resolve())
        except ValueError:
            rel = Path(self.path.name)
        self.source_id = rel.as_posix()
        self.location = str(self.path)
        # La categoría es la primera subcarpeta dentro de data/documents/.
        self.category = rel.parts[0] if len(rel.parts) > 1 else "general"

    def fetch(self, known: dict[str, Any] | None = None) -> FetchResult:
        fingerprint = _sha256_file(self.path)
        prev = (known or {}).get("fingerprint")
        return FetchResult(
            path=self.path,
            file_name=self.path.name,
            fingerprint=fingerprint,
            changed=fingerprint != prev,
        )
