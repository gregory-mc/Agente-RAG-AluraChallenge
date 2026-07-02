"""Unit tests for web document endpoints."""

import sys
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

# Override config directories BEFORE importing app
from rag import config
temp_docs_dir = tempfile.TemporaryDirectory()
config.DOCUMENTS_DIR = Path(temp_docs_dir.name)

from rag.web.app import app

client = TestClient(app)


def test_list_documents_empty():
    res = client.get("/api/documents")
    assert res.status_code == 200
    assert res.json() == []


@patch("rag.web.app.ingest_all")
def test_upload_and_delete_document(mock_ingest_all):
    # Mock ingest_all to return a fake result
    mock_result = MagicMock()
    mock_result.source_id = "test_doc.md"
    mock_result.status = "indexed"
    mock_result.chunks = 3
    mock_ingest_all.return_value = [mock_result]

    # 1. Upload document
    file_content = b"Contenido de prueba."
    response = client.post(
        "/api/documents/upload",
        files={"file": ("test_doc.md", file_content, "text/markdown")}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["filename"] == "test_doc.md"
    assert response.json()["chunks_added"] == 3

    # Check that file exists on disk
    target_file = config.DOCUMENTS_DIR / "test_doc.md"
    assert target_file.exists()
    assert target_file.read_bytes() == file_content

    # 2. List documents
    res_list = client.get("/api/documents")
    assert res_list.status_code == 200
    docs = res_list.json()
    assert len(docs) == 1
    assert docs[0]["filename"] == "test_doc.md"
    assert docs[0]["size_bytes"] == len(file_content)

    # 3. Delete document
    with patch("rag.web.app.get_agent") as mock_get_agent:
        mock_agent = MagicMock()
        mock_agent.indexer.delete_document.return_value = 3
        mock_get_agent.return_value = mock_agent

        del_res = client.delete("/api/documents/test_doc.md")
        assert del_res.status_code == 200
        assert del_res.json()["ok"] is True
        assert del_res.json()["deleted_from_disk"] is True
        assert del_res.json()["chunks_deleted"] == 3

    # Check file is deleted from disk
    assert not target_file.exists()


@patch("rag.web.app.ingest_all")
def test_reindex_documents(mock_ingest_all):
    mock_result = MagicMock()
    mock_result.source_id = "another_doc.pdf"
    mock_result.status = "indexed"
    mock_result.detail = ""
    mock_ingest_all.return_value = [mock_result]

    res = client.post("/api/documents/reindex?force=true")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "another_doc.pdf" in data["indexed"]
    mock_ingest_all.assert_called_once_with(force=True)
