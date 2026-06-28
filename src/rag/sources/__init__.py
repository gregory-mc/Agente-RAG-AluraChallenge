"""Fuentes de documentos: local y remota (URL)."""
from .base import FetchResult, Source
from .local import LocalSource
from .url import UrlSource

__all__ = ["Source", "FetchResult", "LocalSource", "UrlSource"]
