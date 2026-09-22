"""Ingestion pipeline — orchestrates the full document processing workflow."""

import logging
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from src.ingestion.file_manager import FileManager, FileInfo
from src.ingestion.document_processor import DocumentProcessor
from src.ingestion.chunker import Chunker
from src.ingestion.embedder import Embedder
from src.ingestion.indexer import Indexer

logger = logging.getLogger(__name__)
console = Console()


class IngestionPipeline:
    """End-to-end ingestion: Scan → Extract → Chunk → Embed → Index.

    Orchestrates all ingestion components and provides progress tracking.
    """

    def __init__(
        self,
        file_manager: FileManager,
        processor: DocumentProcessor,
        chunker: Chunker,
        embedder: Embedder,
        indexer: Indexer,
    ):
        self.file_manager = file_manager
        self.processor = processor
        self.chunker = chunker
        self.embedder = embedder
        self.indexer = indexer

    def ingest_all(self, force: bool = False) -> dict:
        """Process all pending documents in the documents directory.

        Args:
            force: If True, re-process all documents (ignore manifest).

        Returns:
            Summary dict with counts and any errors.
        """
        files = (
            self.file_manager.scan_documents()
            if force
            else self.file_manager.get_pending_files()
        )

        if not files:
            console.print("[green]✓ All documents are already indexed.[/green]")
            return {"processed": 0, "chunks": 0, "errors": []}

        console.print(f"\n[bold]📥 Processing {len(files)} document(s)...[/bold]\n")

        total_chunks = 0
        errors: list[dict] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Ingesting documents", total=len(files))

            for file_info in files:
                try:
                    chunk_count = self._ingest_single(file_info, progress, task)
                    total_chunks += chunk_count
                except Exception as e:
                    error_msg = f"Failed to process {file_info.name}: {e}"
                    logger.error(error_msg, exc_info=True)
                    errors.append({"file": file_info.name, "error": str(e)})
                    progress.update(task, advance=1)

        summary = {
            "processed": len(files) - len(errors),
            "chunks": total_chunks,
            "errors": errors,
        }

        # Print summary
        console.print(f"\n[bold green]✓ Done![/bold green]")
        console.print(f"  Processed: {summary['processed']} document(s)")
        console.print(f"  Chunks created: {summary['chunks']}")
        if errors:
            console.print(f"  [red]Errors: {len(errors)}[/red]")
            for err in errors:
                console.print(f"    • {err['file']}: {err['error']}")

        return summary

    def ingest_file(self, file_path: str | Path) -> dict:
        """Process a single file.

        Returns:
            Summary dict with chunk count or error.
        """
        path = Path(file_path)
        file_info = FileInfo(
            name=path.name,
            path=str(path),
            extension=path.suffix.lower(),
            size_bytes=path.stat().st_size,
            modified_at="",
        )

        try:
            chunk_count = self._ingest_single(file_info)
            return {"file": file_info.name, "chunks": chunk_count, "status": "success"}
        except Exception as e:
            logger.error(f"Failed to process {file_info.name}: {e}", exc_info=True)
            return {"file": file_info.name, "error": str(e), "status": "error"}

    def _ingest_single(
        self, file_info: FileInfo, progress=None, task=None
    ) -> int:
        """Process a single document through the full pipeline."""
        desc = f"Processing {file_info.name}"
        if progress and task is not None:
            progress.update(task, description=desc)

        # Step 1: Extract text
        doc = self.processor.process(file_info.path)

        if not doc.content_markdown.strip():
            logger.warning(f"No content extracted from {file_info.name}, skipping.")
            if progress and task is not None:
                progress.update(task, advance=1)
            return 0

        # Step 2: Chunk
        chunks = self.chunker.chunk_document(
            content_markdown=doc.content_markdown,
            source_file=doc.source_file,
            file_name=doc.file_name,
            document_type=doc.document_type,
        )

        if not chunks:
            logger.warning(f"No chunks generated from {file_info.name}, skipping.")
            if progress and task is not None:
                progress.update(task, advance=1)
            return 0

        # Step 3: Embed
        embed_inputs = [
            {"text": c.content, "title": c.section_heading}
            for c in chunks
        ]
        embeddings = self.embedder.embed_document_chunks_batch(embed_inputs)

        # Step 4: Index
        # Delete existing chunks for this file (for re-ingestion)
        self.indexer.delete_by_source(doc.source_file)
        chunk_count = self.indexer.add_chunks(chunks, embeddings)

        # Step 5: Update manifest
        self.file_manager.mark_ingested(file_info, chunk_count)

        if progress and task is not None:
            progress.update(task, advance=1)

        return chunk_count
