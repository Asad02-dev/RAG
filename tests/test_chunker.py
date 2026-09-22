"""Unit tests for Chunker."""

from src.ingestion.chunker import Chunker, Chunk


def test_chunk_empty_document():
    chunker = Chunker()
    chunks = chunker.chunk_document(
        content_markdown="",
        source_file="empty.md",
        file_name="empty.md",
        document_type="text",
    )
    assert chunks == []


def test_chunk_document_with_headings():
    markdown = """# Introduction
This is the intro section with some useful context.

## Section 1: Billing
Billing is processed on the 1st of each month.

## Section 2: Support
Support is available 24/7 via ticket and email.
"""
    chunker = Chunker(max_tokens=200)
    chunks = chunker.chunk_document(
        content_markdown=markdown,
        source_file="doc.md",
        file_name="doc.md",
        document_type="text",
    )

    assert len(chunks) >= 3
    headings = [c.section_heading for c in chunks]
    assert any("Introduction" in h for h in headings)
    assert any("Billing" in h for h in headings)
    assert any("Support" in h for h in headings)

    for c in chunks:
        assert isinstance(c, Chunk)
        assert c.source_file == "doc.md"
        assert c.file_name == "doc.md"
        assert c.document_type == "text"
        assert c.token_count > 0


def test_chunk_large_section_splits():
    # Generate long text that exceeds max_tokens
    long_paragraph = "The quick brown fox jumps over the lazy dog. " * 50
    markdown = f"## Big Section\n\n{long_paragraph}"

    chunker = Chunker(max_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_document(
        content_markdown=markdown,
        source_file="large.md",
        file_name="large.md",
        document_type="text",
    )

    # Should split into multiple chunks
    assert len(chunks) > 1
    for c in chunks:
        assert c.section_heading == "Big Section"
        assert c.token_count > 0


def test_enrich_chunk():
    enriched = Chunker._enrich_chunk("Policy", "All users must follow guidelines.")
    assert "[Section: Policy]" in enriched
    assert "All users must follow guidelines." in enriched

    # Should not duplicate if already in content
    no_dup = Chunker._enrich_chunk("Policy", "Policy details are here.")
    assert no_dup == "Policy details are here."
