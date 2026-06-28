"""Estructuras de datos compartidas por el pipeline de ingesta."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedDoc:
    """Texto plano extraído de un documento, más metadatos propios del archivo.

    `meta` lleva lo que el extractor pudo deducir del formato (autor, título,
    número de páginas/hojas, etc.). El orquestador lo completa con los metadatos
    de catálogo (categoría, ruta, fecha, fuente).
    """

    text: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """Fragmento de texto listo para embeddizar (issue #3)."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "metadata": self.metadata}
