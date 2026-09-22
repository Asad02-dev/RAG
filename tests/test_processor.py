"""Unit tests for DocumentProcessor."""

import pytest
from pathlib import Path
from src.ingestion.document_processor import DocumentProcessor, ProcessedDocument


def test_table_to_markdown():
    rows = [
        ["Header 1", "Header 2", "Header 3"],
        ["Val 1", "Val 2", "Val 3"],
        ["A", "B", "C"],
    ]
    md = DocumentProcessor._table_to_markdown(rows)
    assert "| Header 1 | Header 2 | Header 3 |" in md
    assert "| --- | --- | --- |" in md
    assert "| Val 1 | Val 2 | Val 3 |" in md
    assert "| A | B | C |" in md


def test_table_to_markdown_empty():
    assert DocumentProcessor._table_to_markdown([]) == ""


def test_process_text_file(tmp_path):
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text("Hello world, this is a test document.", encoding="utf-8")

    processor = DocumentProcessor()
    doc = processor.process(txt_file)

    assert isinstance(doc, ProcessedDocument)
    assert doc.file_name == "sample.txt"
    assert doc.document_type == "text"
    assert doc.content_markdown == "Hello world, this is a test document."


def test_process_markdown_file(tmp_path):
    md_file = tmp_path / "sample.md"
    md_file.write_text("# Heading 1\n\nSome paragraph text.", encoding="utf-8")

    processor = DocumentProcessor()
    doc = processor.process(md_file)

    assert doc.file_name == "sample.md"
    assert doc.document_type == "text"
    assert "# Heading 1" in doc.content_markdown


def test_process_nonexistent_file():
    processor = DocumentProcessor()
    with pytest.raises(FileNotFoundError):
        processor.process("nonexistent_file.pdf")


def test_process_unsupported_format(tmp_path):
    bad_file = tmp_path / "archive.zip"
    bad_file.write_bytes(b"PK00")

    processor = DocumentProcessor()
    with pytest.raises(ValueError, match="Unsupported file format"):
        processor.process(bad_file)
