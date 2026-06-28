"""Limpieza de texto: quita el ruido antes de chunkear."""
from __future__ import annotations

import re
import unicodedata

_MULTISPACE = re.compile(r"[ \t\f\v]+")
_MULTINEWLINE = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+\n")


def clean_text(text: str) -> str:
    """Normaliza espacios, saltos de línea y caracteres invisibles."""
    if not text:
        return ""

    # Normalización Unicode + quita caracteres de control salvo \n y \t.
    text = unicodedata.normalize("NFKC", text)
    text = "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C"
    )

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_WS.sub("\n", text)
    text = _MULTISPACE.sub(" ", text)
    text = _MULTINEWLINE.sub("\n\n", text)  # como máximo una línea en blanco
    return text.strip()
