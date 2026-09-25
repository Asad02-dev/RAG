"""File manager — scans local filesystem for documents and tracks ingestion state."""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt", ".md", ".eml"}
MANIFEST_FILENAME = ".ingestion_manifest.json"


@dataclass
class FileInfo:
    """Metadata about a document file."""

    name: str
    path: str
    extension: str
    size_bytes: int
    modified_at: str
    ingested: bool = False
    ingested_at: Optional[str] = None
    chunk_count: int = 0


class FileManager:
    """Manages document files in the local filesystem and tracks ingestion state."""

    def __init__(self, documents_dir: str | Path):
        self.documents_dir = Path(documents_dir).resolve()
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.documents_dir / MANIFEST_FILENAME
        self._manifest: dict[str, dict] = self._load_manifest()

    def _load_manifest(self) -> dict[str, dict]:
        """Load the ingestion manifest from disk."""
        if self._manifest_path.exists():
            try:
                return json.loads(self._manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_manifest(self) -> None:
        """Persist the ingestion manifest to disk."""
        self._manifest_path.write_text(
            json.dumps(self._manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def scan_documents(self) -> list[FileInfo]:
        """Scan the documents directory and return metadata for all supported files."""
        files: list[FileInfo] = []
        for path in sorted(self.documents_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                stat = path.stat()
                key = str(path.relative_to(self.documents_dir))
                manifest_entry = self._manifest.get(key, {})

                files.append(FileInfo(
                    name=path.name,
                    path=str(path),
                    extension=path.suffix.lower(),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    ingested=manifest_entry.get("ingested", False),
                    ingested_at=manifest_entry.get("ingested_at"),
                    chunk_count=manifest_entry.get("chunk_count", 0),
                ))
        return files

    def get_pending_files(self) -> list[FileInfo]:
        """Return only files that haven't been ingested yet or have been modified."""
        files = []
        for f in self.scan_documents():
            manifest_entry = self._manifest.get(
                str(Path(f.path).relative_to(self.documents_dir)), {}
            )
            # File is pending if never ingested or modified after last ingestion
            if not f.ingested or f.modified_at > manifest_entry.get("modified_at", ""):
                files.append(f)
        return files

    def mark_ingested(self, file_info: FileInfo, chunk_count: int) -> None:
        """Mark a file as successfully ingested."""
        key = str(Path(file_info.path).relative_to(self.documents_dir))
        self._manifest[key] = {
            "ingested": True,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "modified_at": file_info.modified_at,
            "chunk_count": chunk_count,
            "size_bytes": file_info.size_bytes,
        }
        self._save_manifest()

    def remove_file(self, file_path: str) -> bool:
        """Remove a file from the filesystem and manifest."""
        path = Path(file_path)
        if path.exists():
            key = str(path.relative_to(self.documents_dir))
            path.unlink()
            self._manifest.pop(key, None)
            self._save_manifest()
            return True
        return False

    def get_stats(self) -> dict:
        """Return summary statistics about indexed documents."""
        files = self.scan_documents()
        ingested = [f for f in files if f.ingested]
        return {
            "total_files": len(files),
            "ingested_files": len(ingested),
            "pending_files": len(files) - len(ingested),
            "total_chunks": sum(f.chunk_count for f in ingested),
        }
