"""Unit tests for FileManager."""

import json
from pathlib import Path
from src.ingestion.file_manager import FileManager, FileInfo, MANIFEST_FILENAME


def test_scan_empty_directory(tmp_path):
    fm = FileManager(tmp_path)
    files = fm.scan_documents()
    assert files == []
    assert fm.get_stats() == {
        "total_files": 0,
        "ingested_files": 0,
        "pending_files": 0,
        "total_chunks": 0,
    }


def test_scan_supported_documents(tmp_path):
    (tmp_path / "doc1.txt").write_text("Text doc", encoding="utf-8")
    (tmp_path / "doc2.md").write_text("Markdown doc", encoding="utf-8")
    (tmp_path / "doc3.pdf").write_bytes(b"%PDF-1.4 dummy")
    (tmp_path / "ignored.exe").write_bytes(b"MZ dummy")

    fm = FileManager(tmp_path)
    files = fm.scan_documents()
    names = [f.name for f in files]

    assert "doc1.txt" in names
    assert "doc2.md" in names
    assert "doc3.pdf" in names
    assert "ignored.exe" not in names
    assert len(files) == 3


def test_mark_ingested_and_stats(tmp_path):
    fpath = tmp_path / "test.txt"
    fpath.write_text("sample content", encoding="utf-8")

    fm = FileManager(tmp_path)
    pending = fm.get_pending_files()
    assert len(pending) == 1
    assert pending[0].name == "test.txt"

    fm.mark_ingested(pending[0], chunk_count=4)

    stats = fm.get_stats()
    assert stats["total_files"] == 1
    assert stats["ingested_files"] == 1
    assert stats["pending_files"] == 0
    assert stats["total_chunks"] == 4

    # No pending files left
    assert fm.get_pending_files() == []


def test_remove_file(tmp_path):
    fpath = tmp_path / "to_delete.txt"
    fpath.write_text("delete me", encoding="utf-8")

    fm = FileManager(tmp_path)
    files = fm.scan_documents()
    assert len(files) == 1

    fm.mark_ingested(files[0], chunk_count=2)
    assert fm.remove_file(str(fpath)) is True
    assert not fpath.exists()

    stats = fm.get_stats()
    assert stats["total_files"] == 0
    assert stats["total_chunks"] == 0
