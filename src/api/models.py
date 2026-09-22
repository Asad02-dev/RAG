"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request body for the /api/query endpoint."""

    question: str = Field(..., min_length=1, description="The user's question")


class SourceInfo(BaseModel):
    """A single source citation."""

    file_name: str
    page_number: int
    section_heading: str = ""
    distance: float = 0.0


class QueryResponse(BaseModel):
    """Response body for the /api/query endpoint."""

    answer: str
    sources: list[SourceInfo]
    query: str
    model: str
    chunks_retrieved: int


class DocumentInfo(BaseModel):
    """Information about an indexed document."""

    name: str
    path: str
    extension: str
    size_bytes: int
    modified_at: str
    ingested: bool = False
    ingested_at: str | None = None
    chunk_count: int = 0


class IngestResponse(BaseModel):
    """Response body for the /api/ingest endpoint."""

    processed: int
    chunks: int
    errors: list[dict] = []


class StatsResponse(BaseModel):
    """Response body for the /api/stats endpoint."""

    total_files: int
    ingested_files: int
    pending_files: int
    total_chunks: int


class HealthResponse(BaseModel):
    """Response body for the /api/health endpoint."""

    status: str = "ok"
    gemini_model: str
    embed_model: str
    documents_dir: str
    total_chunks: int
