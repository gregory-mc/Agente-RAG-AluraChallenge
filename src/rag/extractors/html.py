"""Extractor de HTML (archivos locales o páginas descargadas)."""
from __future__ import annotations

from pathlib import Path

from ..models import ExtractedDoc
from .base import ExtractionError, Extractor


class HtmlExtractor(Extractor):
    extensions = (".html", ".htm")

    def extract(self, path: Path) -> ExtractedDoc:
        raw = path.read_text(encoding="utf-8", errors="replace")
        return self.extract_text(raw)

    @staticmethod
    def extract_text(raw_html: str) -> ExtractedDoc:
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:  # pragma: no cover
            raise ExtractionError("Falta dependencia: beautifulsoup4") from exc

        soup = BeautifulSoup(raw_html, "lxml")

        # Quita ruido que no aporta al conocimiento.
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else None
        text = soup.get_text(separator="\n")

        meta = {"format": "html", "title": title}
        return ExtractedDoc(text=text, meta=meta)
