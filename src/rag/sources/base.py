"""Interfaz de fuentes de documentos (local o remota)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FetchResult:
    """Resultado de resolver una fuente a un archivo local extraíble."""

    path: Path                       # archivo en disco listo para el extractor
    file_name: str                   # nombre lógico del documento
    fingerprint: str                 # huella del contenido (para detectar cambios)
    changed: bool                    # ¿cambió respecto del estado conocido?
    validators: dict[str, Any] = field(default_factory=dict)  # etag / last-modified


class Source(ABC):
    """Algo de lo que se puede obtener un documento para ingestar."""

    #: identificador estable del documento (clave del re-indexado incremental)
    source_id: str
    #: categoría de negocio (ver issue #1)
    category: str
    #: ubicación legible: ruta local o URL
    location: str
    #: "local" | "url"
    kind: str

    @abstractmethod
    def fetch(self, known: dict[str, Any] | None = None) -> FetchResult:
        """Resuelve la fuente. `known` es la entrada previa del manifest, si existe."""
        ...
