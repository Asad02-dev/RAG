"""Unit tests for ChromaDB Indexer."""

import pytest
from src.ingestion.chunker import Chunk
from src.ingestion.indexer import Indexer


@pytest.fixture
def indexer(tmp_path):
    return Indexer(chroma_db_dir=tmp_path / "chroma_test")


def test_indexer_initialization(indexer):
    stats = indexer.get_stats()
    assert stats["total_chunks"] == 0
    assert stats["unique_documents"] == 0


def test_add_chunks_and_search(indexer):
    chunks = [
        Chunk(
            chunk_id="doc1::chunk_0",
            content="This is an article about artificial intelligence and neural networks.",
            source_file="ai.txt",
            file_name="ai.txt",
            document_type="text",
            page_number=1,
            section_heading="AI Overview",
            chunk_index=0,
            token_count=12,
        ),
        Chunk(
            chunk_id="doc2::chunk_0",
            content="Baking a cake requires flour, sugar, eggs, and butter.",
            source_file="recipe.txt",
            file_name="recipe.txt",
            document_type="text",
            page_number=1,
            section_heading="Recipe",
            chunk_index=0,
            token_count=11,
        ),
    ]

    # Create dummy 4-dimensional embeddings
    embeddings = [
        [0.9, 0.1, 0.0, 0.0],
        [0.0, 0.0, 0.9, 0.1],
    ]

    added = indexer.add_chunks(chunks, embeddings)
    assert added == 2

    stats = indexer.get_stats()
    assert stats["total_chunks"] == 2
    assert stats["unique_documents"] == 2
    assert "ai.txt" in stats["source_files"]

    # Search with a vector close to AI
    results = indexer.search(query_embedding=[0.85, 0.15, 0.0, 0.0], n_results=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "doc1::chunk_0"
    assert "artificial intelligence" in results[0]["content"]


def test_delete_by_source(indexer):
    chunks = [
        Chunk(
            chunk_id="doc1::chunk_0",
            content="Content 1",
            source_file="doc1.txt",
            file_name="doc1.txt",
            document_type="text",
            page_number=1,
            section_heading="Head",
            chunk_index=0,
        )
    ]
    indexer.add_chunks(chunks, [[0.5, 0.5]])
    assert indexer.get_stats()["total_chunks"] == 1

    deleted = indexer.delete_by_source("doc1.txt")
    assert deleted == 1
    assert indexer.get_stats()["total_chunks"] == 0
