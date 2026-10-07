from fastapi import APIRouter, HTTPException

from src.api.models import (
    Neo4jIngestRequest,
    Neo4jIngestResponse,
)

from src.services.triplet_service import (
    extract_triplets,
)

from src.services.neo4j_service import (
    ingest_triplets,
    ingest_standalone_nodes,
)


router = APIRouter()


@router.post(
    "/neo4j/ingest",
    response_model=Neo4jIngestResponse,
)
async def ingest_into_neo4j(
    request: Neo4jIngestRequest,
):

    result = await extract_triplets(
        request.data
    )

    if not result.triplets and not result.standalone_nodes:
        raise HTTPException(
            status_code=400,
            detail="No valid triplets could be extracted.",
        )

    triplets_count = ingest_triplets(
        result.triplets
    )

    standalone_count = ingest_standalone_nodes(
        result.standalone_nodes
    )

    return Neo4jIngestResponse(
        message="Data successfully ingested into Neo4j.",
        triplets_created=triplets_count,
        standalone_nodes_created=standalone_count,
    )
