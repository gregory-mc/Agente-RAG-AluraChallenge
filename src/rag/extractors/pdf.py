"""Extractor de PDF."""
from __future__ import annotations

from pathlib import Path

from ..models import ExtractedDoc
from .base import ExtractionError, Extractor


class PdfExtractor(Extractor):
    extensions = (".pdf",)

    def extract(self, path: Path) -> ExtractedDoc:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
            raise ExtractionError("Falta dependencia: pypdf") from exc

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages)

        info = reader.metadata or {}
        meta = {
            "format": "pdf",
            "pages": len(reader.pages),
            "author": getattr(info, "author", None),
            "title": getattr(info, "title", None),
        }
        return ExtractedDoc(text=text, meta=meta)
