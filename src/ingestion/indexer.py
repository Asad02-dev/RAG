"""Indexer — stores document chunks and their embeddings in ChromaDB."""

import logging
from pathlib import Path

import chromadb

from src.ingestion.chunker import Chunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "rag_documents"


class Indexer:
    """Manage the ChromaDB vector store for document chunks.

    Provides add, search, delete, and stats operations. Designed so this
    class can be swapped with an Azure AI Search implementation.
    """

    def __init__(self, chroma_db_dir: str | Path):
        self.chroma_db_dir = Path(chroma_db_dir).resolve()
        self.chroma_db_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(self.chroma_db_dir))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )
        logger.info(
            f"ChromaDB initialized at {self.chroma_db_dir} "
            f"({self.collection.count()} existing chunks)"
        )

    def add_chunks(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> int:
        """Add chunks with their embeddings to the collection.

        Args:
            chunks: List of Chunk objects with content and metadata.
            embeddings: Corresponding embedding vectors.

        Returns:
            Number of chunks successfully added.
        """
        if not chunks:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(chunks)} chunks but {len(embeddings)} embeddings"
            )

        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "source_file": c.source_file,
                "file_name": c.file_name,
                "document_type": c.document_type,
                "page_number": c.page_number,
                "section_heading": c.section_heading,
                "chunk_index": c.chunk_index,
                "token_count": c.token_count,
            }
            for c in chunks
        ]

        # ChromaDB upsert (add or update)
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(f"Indexed {len(chunks)} chunks into ChromaDB")
        return len(chunks)

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """Search for similar chunks using a query embedding.

        Args:
            query_embedding: The embedded query vector.
            n_results: Number of results to return.
            filter_metadata: Optional ChromaDB metadata filter.

        Returns:
            List of result dicts with 'content', 'metadata', and 'distance'.
        """
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, self.collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if filter_metadata:
            kwargs["where"] = filter_metadata

        if self.collection.count() == 0:
            return []

        results = self.collection.query(**kwargs)

        # Flatten ChromaDB's nested result format
        hits = []
        for i in range(len(results["ids"][0])):
            hits.append({
                "chunk_id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })

        return hits

    def delete_by_source(self, source_file: str) -> int:
        """Delete all chunks from a specific source file.

        Returns:
            Number of chunks deleted.
        """
        # Query to find all chunk IDs from this source
        results = self.collection.get(
            where={"source_file": source_file},
            include=[],
        )

        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for {source_file}")
            return len(results["ids"])

        return 0

    def get_chunk_ids_by_source(self, source_file: str) -> list[str]:
        """Get all chunk IDs for a specific source file."""
        results = self.collection.get(
            where={"source_file": source_file},
            include=[],
        )
        return results["ids"]

    def get_stats(self) -> dict:
        """Return collection statistics."""
        count = self.collection.count()

        # Get unique source files
        source_files = set()
        if count > 0:
            all_metadata = self.collection.get(include=["metadatas"])
            for meta in all_metadata["metadatas"]:
                source_files.add(meta.get("file_name", "unknown"))

        return {
            "total_chunks": count,
            "unique_documents": len(source_files),
            "source_files": sorted(source_files),
        }

    def clear(self) -> None:
        """Delete all data from the collection."""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection cleared")
