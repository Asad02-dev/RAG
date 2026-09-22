"""Unit tests for Pydantic models."""

from src.api.models import (
    QueryRequest,
    SourceInfo,
    QueryResponse,
    DocumentInfo,
    IngestResponse,
    StatsResponse,
    HealthResponse,
)


def test_query_request():
    req = QueryRequest(question="What is the refund policy?")
    assert req.question == "What is the refund policy?"


def test_source_info():
    src = SourceInfo(
        file_name="doc.pdf",
        page_number=2,
        section_heading="Refunds",
        distance=0.15,
    )
    assert src.file_name == "doc.pdf"
    assert src.page_number == 2
    assert src.distance == 0.15


def test_query_response():
    resp = QueryResponse(
        answer="Refunds are 30 days.",
        sources=[
            SourceInfo(file_name="doc.pdf", page_number=2)
        ],
        query="What is the refund policy?",
        model="gemma-4-26b-a4b-it",
        chunks_retrieved=1,
    )
    assert resp.answer == "Refunds are 30 days."
    assert len(resp.sources) == 1
    assert resp.chunks_retrieved == 1


def test_health_response():
    health = HealthResponse(
        status="ok",
        gemini_model="gemma-4-26b-a4b-it",
        embed_model="gemini-embedding-2",
        documents_dir="./data/documents",
        total_chunks=10,
    )
    assert health.status == "ok"
    assert health.total_chunks == 10
