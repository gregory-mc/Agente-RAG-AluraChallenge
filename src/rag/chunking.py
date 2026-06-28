"""División del texto en fragmentos (chunks) con superposición.

Estrategia: cortar respetando límites naturales (párrafo > oración > palabra)
para no partir ideas a la mitad, manteniendo un solapamiento configurable entre
fragmentos consecutivos para no perder contexto en los bordes.
"""
from __future__ import annotations

import re

from . import config

# Separadores ordenados de "más fuerte" a "más débil".
_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _split_units(text: str) -> list[str]:
    """Parte el texto en unidades pequeñas (oraciones dentro de párrafos)."""
    units: list[str] = []
    for paragraph in _PARAGRAPH.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for sentence in _SENTENCE.split(paragraph):
            sentence = sentence.strip()
            if sentence:
                units.append(sentence)
    return units


def _hard_split(unit: str, size: int) -> list[str]:
    """Trocea una unidad más larga que `size` por palabras."""
    words = unit.split(" ")
    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > size and current:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def chunk_text(
    text: str,
    size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> list[str]:
    """Divide `text` en fragmentos de ~`size` caracteres con `overlap` de solape."""
    if not text:
        return []
    if overlap >= size:
        raise ValueError("overlap debe ser menor que size")

    # Unidades atómicas; las que exceden el tamaño se trocean por palabras.
    units: list[str] = []
    for unit in _split_units(text):
        units.extend(_hard_split(unit, size) if len(unit) > size else [unit])

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n{unit}".strip() if current else unit
        if len(candidate) > size and current:
            chunks.append(current)
            # Arranca el siguiente chunk con la cola del anterior (solapamiento).
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n{unit}".strip() if tail else unit
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks
