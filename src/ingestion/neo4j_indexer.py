"""Neo4j indexer — stores document chunks and their embeddings in Neo4j (replaces ChromaDB).

Has the same methods as the ChromaDB Indexer, so the pipeline and search client work unchanged.
"""

import logging

from configs.settings import NEO4J_DATABASE
from src.ingestion.chunker import Chunk
from src.services.neo4j_service import driver

logger = logging.getLogger(__name__)

INDEX_NAME = "rag_documents"


class Neo4jIndexer:
    """Store, search and delete document chunks as (:Chunk) nodes with a vector index."""

    def __init__(self, dimensions: int = 1536):
        # dimensions must match the embedding model (text-embedding-3-small = 1536)
        driver.execute_query(
            f"""
            CREATE VECTOR INDEX {INDEX_NAME} IF NOT EXISTS
            FOR (c:Chunk) ON c.embedding
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: {dimensions},
                `vector.similarity_function`: 'cosine'
            }}}}
            """,
            database_=NEO4J_DATABASE,
        )
        logger.info(f"Neo4j vector index '{INDEX_NAME}' ready ({self.get_stats()['total_chunks']} existing chunks)")

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        """Add chunks with their embeddings (or update them if the chunk id already exists)."""
        if not chunks:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: {len(chunks)} chunks but {len(embeddings)} embeddings")

        rows = [
            {
                "id": chunk.chunk_id,
                "content": chunk.content,
                "embedding": embedding,
                "source_file": chunk.source_file,
                "file_name": chunk.file_name,
                "document_type": chunk.document_type,
                "page_number": chunk.page_number,
                "section_heading": chunk.section_heading,
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]

        # Each chunk is linked to a Document node named after its file. If the submission graph
        # already has that Document (Submission -HAS_DOCUMENT-> Document), the chunk joins it.
        driver.execute_query(
            """
            UNWIND $rows AS row
            MERGE (c:Chunk {id: row.id})
            SET c += row
            MERGE (d:Document {name: row.file_name})
            MERGE (c)-[:PART_OF]->(d)
            """,
            rows=rows,
            database_=NEO4J_DATABASE,
        )

        logger.info(f"Indexed {len(rows)} chunks into Neo4j")
        return len(rows)

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """Return the most similar chunks, as dicts with 'chunk_id', 'content', 'metadata' and 'distance'."""

        # With a filter (e.g. {"file_name": "..."}), take extra candidates first, then keep the matching ones
        candidates = n_results * 10 if filter_metadata else n_results

        records, _, _ = driver.execute_query(
            f"""
            CALL db.index.vector.queryNodes('{INDEX_NAME}', $candidates, $embedding)
            YIELD node, score
            WHERE all(key IN keys($filter) WHERE node[key] = $filter[key])
            RETURN node, score
            ORDER BY score DESC
            LIMIT $limit
            """,
            candidates=candidates,
            embedding=query_embedding,
            filter=filter_metadata or {},
            limit=n_results,
            database_=NEO4J_DATABASE,
        )

        hits = []
        for record in records:
            node = dict(record["node"])
            node.pop("embedding", None)
            hits.append({
                "chunk_id": node.pop("id"),
                "content": node.pop("content"),
                "metadata": node,
                # Chroma returned a distance (lower = closer); Neo4j returns a score (higher = closer)
                "distance": 1 - record["score"],
            })

        return hits

    def delete_by_source(self, source_file: str) -> int:
        """Delete all chunks of one source file. Returns how many were deleted."""
        # Also delete the file's Document node, but only if nothing else is linked to it
        # (a Document that belongs to a submission is kept)
        records, _, _ = driver.execute_query(
            """
            MATCH (c:Chunk {source_file: $source})
            OPTIONAL MATCH (c)-[:PART_OF]->(d:Document)
            DETACH DELETE c
            WITH count(c) AS total, collect(DISTINCT d) AS documents
            FOREACH (d IN [doc IN documents WHERE NOT (doc)--()] | DELETE d)
            RETURN total
            """,
            source=source_file,
            database_=NEO4J_DATABASE,
        )

        total = records[0]["total"] if records else 0
        if total:
            logger.info(f"Deleted {total} chunks for {source_file}")
        return total

    def get_chunk_ids_by_source(self, source_file: str) -> list[str]:
        """Return the chunk ids of one source file."""
        records, _, _ = driver.execute_query(
            "MATCH (c:Chunk {source_file: $source}) RETURN c.id AS id",
            source=source_file,
            database_=NEO4J_DATABASE,
        )
        return [record["id"] for record in records]

    def get_stats(self) -> dict:
        """Return the number of chunks and the list of indexed files."""
        records, _, _ = driver.execute_query(
            "MATCH (c:Chunk) RETURN count(c) AS total, collect(DISTINCT c.file_name) AS files",
            database_=NEO4J_DATABASE,
        )
        files = sorted(records[0]["files"])
        return {
            "total_chunks": records[0]["total"],
            "unique_documents": len(files),
            "source_files": files,
        }

    def clear(self) -> None:
        """Delete all chunks, and Document nodes left with no links (the vector index itself stays)."""
        driver.execute_query("MATCH (c:Chunk) DETACH DELETE c", database_=NEO4J_DATABASE)
        driver.execute_query("MATCH (d:Document) WHERE NOT (d)--() DELETE d", database_=NEO4J_DATABASE)
        logger.info("All chunks deleted from Neo4j")
