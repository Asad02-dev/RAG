"""Query route — POST /api/query for asking questions."""

from fastapi import APIRouter, Depends

from src.api.models import QueryRequest, QueryResponse, SourceInfo
from src.api.main import get_query_engine

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Ask a question and get a grounded answer from indexed documents."""
    engine = get_query_engine()
    result = engine.query(request.question)

    return QueryResponse(
        answer=result.answer,
        sources=[
            SourceInfo(**s) for s in result.sources
        ],
        query=result.query,
        model=result.model,
        chunks_retrieved=result.chunks_retrieved,
    )
