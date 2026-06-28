"""Registro de extractores por extensión de archivo."""
from __future__ import annotations

from pathlib import Path

from .base import ExtractionError, Extractor
from .csv_ext import CsvExtractor
from .docx import DocxExtractor
from .html import HtmlExtractor
from .json_ext import JsonExtractor
from .markdown import MarkdownExtractor
from .pdf import PdfExtractor
from .pptx import PptxExtractor
from .xlsx import XlsxExtractor

_EXTRACTORS: list[Extractor] = [
    PdfExtractor(),
    DocxExtractor(),
    XlsxExtractor(),
    PptxExtractor(),
    MarkdownExtractor(),
    CsvExtractor(),
    JsonExtractor(),
    HtmlExtractor(),
]

# extensión -> extractor
_BY_EXT: dict[str, Extractor] = {
    ext: extractor for extractor in _EXTRACTORS for ext in extractor.extensions
}


def supported_extensions() -> tuple[str, ...]:
    return tuple(sorted(_BY_EXT))


def get_extractor(path: Path) -> Extractor:
    """Devuelve el extractor para la extensión de `path` o lanza ExtractionError."""
    ext = path.suffix.lower()
    extractor = _BY_EXT.get(ext)
    if extractor is None:
        raise ExtractionError(
            f"Formato no soportado: {ext!r}. Soportados: {', '.join(supported_extensions())}"
        )
    return extractor
