"""Unit tests for the IngestionPipeline using mock embedder."""

from unittest.mock import MagicMock
from pathlib import Path
import pytest

from src.ingestion.file_manager import FileManager
from src.ingestion.document_processor import DocumentProcessor
from src.ingestion.chunker import Chunker
from src.ingestion.indexer import Indexer
from src.ingestion.pipeline import IngestionPipeline


class MockEmbedder:
    """Mock embedder returning dummy embedding vectors."""

    def __init__(self, dim: int = 4):
        self.dim = dim

    def embed_document_chunks_batch(self, chunks: list[dict]) -> list[list[float]]:
        return [[0.1] * self.dim for _ in chunks]

    def embed_query(self, query: str) -> list[float]:
        return [0.1] * self.dim


def test_pipeline_ingest_all(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    chroma_dir = tmp_path / "chroma"

    # Create sample document
    sample_file = docs_dir / "sample.md"
    sample_file.write_text(
        "# Title\nThis is a sample document for pipeline testing.\n\n## Section A\nMore details here.",
        encoding="utf-8",
    )

    file_manager = FileManager(docs_dir)
    processor = DocumentProcessor()
    chunker = Chunker(max_tokens=100)
    embedder = MockEmbedder()
    indexer = Indexer(chroma_dir)

    pipeline = IngestionPipeline(
        file_manager=file_manager,
        processor=processor,
        chunker=chunker,
        embedder=embedder,
        indexer=indexer,
    )

    # Ingest all
    summary = pipeline.ingest_all()

    assert summary["processed"] == 1
    assert summary["chunks"] > 0
    assert len(summary["errors"]) == 0

    # Verify indexed in ChromaDB
    stats = indexer.get_stats()
    assert stats["total_chunks"] == summary["chunks"]
    assert "sample.md" in stats["source_files"]

    # Verify manifest updated
    assert len(file_manager.get_pending_files()) == 0

    # Second run should skip already ingested files
    second_summary = pipeline.ingest_all()
    assert second_summary["processed"] == 0
