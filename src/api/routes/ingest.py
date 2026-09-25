"""Ingest route — POST /api/ingest for uploading and processing documents."""

import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from src.api.models import IngestResponse, DocumentInfo, StatsResponse
from src.api.main import get_pipeline, get_file_manager, get_indexer

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest_documents(files: list[UploadFile] = File(None)):
    """Upload and process documents, or process all pending files in data/documents/.

    If files are uploaded, saves them to data/documents/ first, then processes.
    If no files are uploaded, processes all pending (un-ingested) files.
    """
    pipeline = get_pipeline()
    file_manager = get_file_manager()

    if files and files[0].filename:
        # Save uploaded files to documents directory
        for upload_file in files:
            dest = file_manager.documents_dir / upload_file.filename
            with open(dest, "wb") as f:
                shutil.copyfileobj(upload_file.file, f)

    # Process all pending files
    result = pipeline.ingest_all()

    return IngestResponse(
        processed=result["processed"],
        chunks=result["chunks"],
        errors=result["errors"],
    )


@router.get("/documents", response_model=list[DocumentInfo])
def list_documents():
    """List all documents and their ingestion status."""
    file_manager = get_file_manager()
    files = file_manager.scan_documents()

    return [
        DocumentInfo(
            name=f.name,
            path=f.path,
            extension=f.extension,
            size_bytes=f.size_bytes,
            modified_at=f.modified_at,
            ingested=f.ingested,
            ingested_at=f.ingested_at,
            chunk_count=f.chunk_count,
        )
        for f in files
    ]


@router.delete("/documents/{file_name}")
def delete_document(file_name: str):
    """Delete a document and its indexed chunks."""
    file_manager = get_file_manager()
    indexer = get_indexer()

    # Find the file
    files = file_manager.scan_documents()
    target = next((f for f in files if f.name == file_name), None)

    if not target:
        raise HTTPException(status_code=404, detail=f"Document '{file_name}' not found")

    # Delete chunks from ChromaDB
    deleted_chunks = indexer.delete_by_source(target.path)

    # Delete the file from filesystem
    file_manager.remove_file(target.path)

    return {
        "message": f"Deleted '{file_name}'",
        "chunks_removed": deleted_chunks,
    }


@router.get("/stats", response_model=StatsResponse)
def get_stats():
    """Get system statistics."""
    file_manager = get_file_manager()
    stats = file_manager.get_stats()
    return StatsResponse(**stats)
