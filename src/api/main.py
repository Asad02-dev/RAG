"""FastAPI application — serves both the REST API and the Web UI."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from configs.settings import get_settings, Settings
from src.llm_client import get_llm_client
from src.ingestion.file_manager import FileManager
from src.ingestion.document_processor import DocumentProcessor
from src.ingestion.chunker import Chunker
from src.ingestion.embedder import Embedder
from src.ingestion.indexer import Indexer
from src.ingestion.pipeline import IngestionPipeline
from src.retrieval.search_client import SearchClient
from src.retrieval.query_engine import QueryEngine
from src.api.models import HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Global component instances (initialized on startup) ──
_settings: Settings | None = None
_file_manager: FileManager | None = None
_pipeline: IngestionPipeline | None = None
_query_engine: QueryEngine | None = None
_indexer: Indexer | None = None


def _initialize_components():
    """Initialize all pipeline components from settings."""
    global _settings, _file_manager, _pipeline, _query_engine, _indexer

    _settings = get_settings()

    _file_manager = FileManager(_settings.documents_dir)
    processor = DocumentProcessor()
    chunker = Chunker(
        max_tokens=_settings.max_chunk_tokens,
        overlap_tokens=_settings.chunk_overlap_tokens,
    )
    llm_client = get_llm_client(_settings)
    embedder = Embedder(
        llm_client=llm_client,
        model=_settings.get_embed_model,
    )
    _indexer = Indexer(_settings.chroma_db_dir)

    _pipeline = IngestionPipeline(
        file_manager=_file_manager,
        processor=processor,
        chunker=chunker,
        embedder=embedder,
        indexer=_indexer,
    )

    search_client = SearchClient(embedder=embedder, indexer=_indexer)
    _query_engine = QueryEngine(
        search_client=search_client,
        llm_client=llm_client,
        llm_model=_settings.get_llm_model,
        fallback_models=_settings.fallback_models_list,
        temperature=_settings.temperature,
        max_output_tokens=_settings.max_output_tokens,
        thinking_budget=_settings.thinking_budget,
        top_k=_settings.top_k_results,
    )

    logger.info(
        f"All components initialized successfully (provider: {llm_client.provider.value}, "
        f"llm: {_settings.get_llm_model}, embed: {_settings.get_embed_model}, "
        f"api key set: {llm_client.has_api_key})"
    )


# ── Dependency accessors ──


def get_settings_dep() -> Settings:
    return _settings


def get_file_manager() -> FileManager:
    return _file_manager


def get_pipeline() -> IngestionPipeline:
    return _pipeline


def get_query_engine() -> QueryEngine:
    return _query_engine


def get_indexer() -> Indexer:
    return _indexer


def get_search_client() -> SearchClient:
    return _query_engine.search_client


# ── App lifecycle ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup."""
    _initialize_components()
    logger.info("🔍 RAG System POC — Ready")
    yield
    logger.info("Shutting down...")


# ── FastAPI App ──

app = FastAPI(
    title="RAG System POC",
    description="Gemini-powered document intelligence & retrieval",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Mount API routes ──

from src.api.routes import query as query_routes
from src.api.routes import ingest as ingest_routes
from src.api.routes import tirsweb as tirsweb_routes
from src.api.routes import agent_query as agent_query_routes
from src.api.routes import neo4j_ingest as neo4j_ingest_routes

app.include_router(query_routes.router, prefix="/api", tags=["Query"])
app.include_router(ingest_routes.router, prefix="/api", tags=["Documents"])
app.include_router(tirsweb_routes.router, prefix="/api/tirsweb", tags=["TIRSWeb"])
app.include_router(agent_query_routes.router, prefix="/api", tags=["Agent"])
app.include_router(neo4j_ingest_routes.router, prefix="/api", tags=["Neo4j"])


# ── Mount Web UI static files ──

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


# ── HTML page routes ──


@app.get("/", include_in_schema=False)
async def serve_chat_page():
    """Serve the main chat interface."""
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Web UI not found. Place index.html in the web/ directory."}


@app.get("/documents", include_in_schema=False)
async def serve_documents_page():
    """Serve the document management page."""
    docs_path = WEB_DIR / "documents.html"
    if docs_path.exists():
        return FileResponse(str(docs_path))
    return {"message": "Documents page not found."}


@app.get("/agent", include_in_schema=False)
async def serve_agent_page():
    """Serve the Graph Agent POC page."""
    agent_path = WEB_DIR / "agent.html"
    if agent_path.exists():
        return FileResponse(str(agent_path))
    return {"message": "Agent page not found."}


@app.get("/tirsweb", include_in_schema=False)
async def serve_tirsweb_page():
    """Serve the TIRSWeb UI page."""
    tirsweb_path = WEB_DIR / "tirsweb" / "index.html"
    if tirsweb_path.exists():
        return FileResponse(str(tirsweb_path))
    return {"message": "TIRSWeb page not found."}


# ── API routes ──


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Check system health and configuration."""
    idx_stats = _indexer.get_stats() if _indexer else {"total_chunks": 0}
    return HealthResponse(
        status="ok",
        gemini_model=_settings.get_llm_model,
        embed_model=_settings.get_embed_model,
        documents_dir=str(_settings.documents_path),
        total_chunks=idx_stats["total_chunks"],
    )
