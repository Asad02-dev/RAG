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


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str
    
# Neo 4J Schema
class Property(BaseModel):
    key: str = Field(description="snake_case property name, e.g. premium_amount")
    value: str = Field(description="Value copied exactly from the JSON")


class Node(BaseModel):
    label: str = Field(description="Ontology label")
    name: str = Field(description="Identifying value exactly as in the JSON, WITHOUT the label as a prefix")
    properties: list[Property]


class Triplet(BaseModel):
    source: Node
    relationship: str = Field(description="Allowed relationship type, e.g. BROKERED_BY")
    relationship_properties: list[Property] = Field(description="Facts about the link itself; usually empty")
    target: Node


class TripletExtractionResult(BaseModel):
    triplets: list[Triplet]
    standalone_nodes: list[Node] = Field(description="Entities with facts but no allowed relationship")


class Neo4jIngestRequest(BaseModel):
    data: dict | list


class Neo4jIngestResponse(BaseModel):
    message: str
    triplets_created: int
    standalone_nodes_created: int