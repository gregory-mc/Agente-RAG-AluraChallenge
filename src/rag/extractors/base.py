"""Interfaz común de los extractores por formato."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import ExtractedDoc


class Extractor(ABC):
    """Convierte un archivo de un formato concreto en texto plano + metadatos."""

    #: extensiones (en minúscula, con punto) que maneja este extractor
    extensions: tuple[str, ...] = ()

    @abstractmethod
    def extract(self, path: Path) -> ExtractedDoc:  # pragma: no cover - interfaz
        ...


class ExtractionError(RuntimeError):
    """Se lanza cuando un documento no se puede extraer."""
