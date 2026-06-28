"""Extractor de JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import ExtractedDoc
from .base import ExtractionError, Extractor


def _flatten(obj: Any, prefix: str = "") -> list[str]:
    """Aplana un JSON anidado a líneas 'ruta.de.clave: valor'."""
    lines: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_flatten(value, path))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            path = f"{prefix}[{i}]"
            lines.extend(_flatten(value, path))
    else:
        lines.append(f"{prefix}: {obj}")
    return lines


class JsonExtractor(Extractor):
    extensions = (".json",)

    def extract(self, path: Path) -> ExtractedDoc:
        raw = path.read_text(encoding="utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"JSON inválido en {path.name}: {exc}") from exc

        text = "\n".join(_flatten(data))
        meta = {"format": "json"}
        return ExtractedDoc(text=text, meta=meta)
