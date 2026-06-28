"""Extractor de Markdown (.md)."""
from __future__ import annotations

import re
from pathlib import Path

from ..models import ExtractedDoc
from .base import Extractor

_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_IMG = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_EMPHASIS = re.compile(r"(\*\*|__|\*|_)")


class MarkdownExtractor(Extractor):
    extensions = (".md", ".markdown")

    def extract(self, path: Path) -> ExtractedDoc:
        raw = path.read_text(encoding="utf-8", errors="replace")

        # El título suele ser el primer encabezado de nivel 1.
        title = None
        m = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
        if m:
            title = m.group(1).strip()

        text = _IMG.sub("", raw)
        text = _CODE_FENCE.sub("", text)
        text = _LINK.sub(r"\1", text)       # conserva el texto del enlace
        text = _INLINE_CODE.sub(r"\1", text)
        text = _HEADING.sub("", text)       # quita los '#', deja el título
        text = _EMPHASIS.sub("", text)

        meta = {"format": "markdown", "title": title}
        return ExtractedDoc(text=text, meta=meta)
