"""Unit tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_serve_chat_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Document Q&A" in response.text


def test_serve_documents_page(client):
    response = client.get("/documents")
    assert response.status_code == 200
    assert "Document Management" in response.text


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "gemini_model" in data
    assert "embed_model" in data


def test_list_documents(client):
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_stats(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_files" in data
    assert "ingested_files" in data
    assert "total_chunks" in data
