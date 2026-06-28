"""Extractores de texto por formato (issue #2)."""
from .base import ExtractionError, Extractor
from .registry import get_extractor, supported_extensions

__all__ = ["Extractor", "ExtractionError", "get_extractor", "supported_extensions"]
