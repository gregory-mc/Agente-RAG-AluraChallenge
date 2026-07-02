"""Unit tests for EmbedCache (disk-based)."""

from pathlib import Path
import sys, tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag.cache import load_cached_embedding, save_cached_embedding


def _clean_dir():
    """Limpiar archivo caché temporal."""
    from rag.cache import clear_cache
    clear_cache()



def test_cache_key_generates_different_hashes():
    from rag.cache import cache_key
    assert cache_key("hello") != cache_key("world")


def test_load_from_empty_returns_none():
    _clean_dir()
    from rag.cache import load_cached_embedding, save_cached_embedding
    assert load_cached_embedding("test") is None
    
    save_cached_embedding("test", [1.0, 2.0])
    assert load_cached_embedding("test") == [1.0, 2.0]


def test_cache_persists_across_operations():
    """Verifica que los embeddings persisten entre múltiples llamadas."""
    _clean_dir()
    
    # Guardar texto y cargar de forma consistente
    text = "test embedding" 
    vectors = [1.0, 2.0, 3.0]
    
    save_cached_embedding(text, vectors)
    loaded = load_cached_embedding(text)
    
    assert loaded == vectors, f"Expected {vectors}, got {loaded}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
