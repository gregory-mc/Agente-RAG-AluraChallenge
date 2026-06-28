"""Extractor de CSV."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from ..models import ExtractedDoc
from .base import Extractor


class CsvExtractor(Extractor):
    extensions = (".csv",)

    def extract(self, path: Path) -> ExtractedDoc:
        raw = path.read_text(encoding="utf-8", errors="replace")

        # Detecta el delimitador (coma, punto y coma, tab) sobre una muestra.
        try:
            dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(io.StringIO(raw), dialect)
        rows = list(reader)
        header = rows[0] if rows else []

        lines: list[str] = []
        if header:
            # Cada fila como "col: valor" para que cada registro sea legible/buscable.
            for row in rows[1:]:
                pairs = [
                    f"{h.strip()}: {v.strip()}"
                    for h, v in zip(header, row)
                    if v and v.strip()
                ]
                if pairs:
                    lines.append("; ".join(pairs))

        meta = {"format": "csv", "columns": [h.strip() for h in header], "rows": max(len(rows) - 1, 0)}
        return ExtractedDoc(text="\n".join(lines), meta=meta)
