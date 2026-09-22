"""Search client — handles similarity search against ChromaDB."""

import logging

from src.ingestion.embedder import Embedder
from src.ingestion.indexer import Indexer

logger = logging.getLogger(__name__)


class SearchClient:
    """Perform semantic search by embedding queries and searching ChromaDB.

    Designed so this class can be swapped with an Azure AI Search client
    that adds hybrid search (vector + BM25) and semantic reranking.
    """

    def __init__(self, embedder: Embedder, indexer: Indexer):
        self.embedder = embedder
        self.indexer = indexer

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """Search for documents relevant to the query.

        Args:
            query: The user's natural language question.
            top_k: Number of results to return.
            filter_metadata: Optional metadata filter (e.g., by source file).

        Returns:
            List of result dicts with 'content', 'metadata', and 'distance'.
        """
        # Embed the query with question-answering task prefix
        query_embedding = self.embedder.embed_query(query)

        # Search ChromaDB
        results = self.indexer.search(
            query_embedding=query_embedding,
            n_results=top_k,
            filter_metadata=filter_metadata,
        )

        logger.info(
            f"Search for '{query[:50]}...' returned {len(results)} results"
        )
        return results
