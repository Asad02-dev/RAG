"""Ingest route — POST /api/ingest for uploading and processing documents."""

import shutil
from pathlib import Path
import json
import uuid
import email
from email import policy
import os

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


@router.post("/ingest/{file_name}")
def ingest_single_document(file_name: str):
    """Process a single document."""
    pipeline = get_pipeline()
    file_manager = get_file_manager()
    
    files = file_manager.scan_documents()
    target = next((f for f in files if f.name == file_name), None)
    
    if not target:
        raise HTTPException(status_code=404, detail=f"Document '{file_name}' not found")
        
    result = pipeline.ingest_file(target.path)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
    # NEW LOGIC: Classification and routing to TIRSWeb Assigned Queue
    if target.path.endswith('.eml'):
        try:
            with open(target.path, 'rb') as f:
                msg = email.message_from_binary_file(f, policy=policy.default)
                
            eml_subject = msg.get('subject', 'No Subject').lower()
            eml_to = msg.get('to', '').lower()
            eml_cc = msg.get('cc', '').lower()
            
            is_follow_up = "follow up" in eml_subject or "fwd" in eml_subject or "re:" in eml_subject
            
            status = "UNASSIGNED"
            ta_assigned = ""
            uw_assigned = ""
            
            if not is_follow_up:
                # New/Renewal business -> assign based on TO/CC
                status = "ASSIGNED"
                if "tirsweb" in eml_to or "team" in eml_cc:
                    ta_assigned = "Ringwood, John (Auto)"
                    uw_assigned = "Vonserlime, Rylkki (Auto)"
                else:
                    ta_assigned = "Default TA (Auto)"
                    uw_assigned = "Default UW (Auto)"
                    
            # Load TIRSWeb data.json and append this submission
            data_json_path = Path(__file__).parent.parent.parent.parent / "web" / "tirsweb" / "data.json"
            if data_json_path.exists():
                with open(data_json_path, 'r', encoding='utf-8') as f:
                    tirs_data = json.load(f)
                
                new_sub = {
                    "id": f"SUB-{uuid.uuid4().hex[:8]}",
                    "status": status,
                    "clearance_status": "CLEARED",
                    "email": {
                        "subject": msg.get('subject', 'No Subject'),
                        "from": msg.get('from', 'Unknown Sender'),
                        "to": msg.get('to', ''),
                        "cc": msg.get('cc', ''),
                        "date": msg.get('date', ''),
                        "filename": file_name,
                        "body": "Indexed content from RAG pipeline."
                    },
                    "stitch_worksheet": {
                        "account_overview": {
                            "insured_name": "Extracted from RAG"
                        },
                        "deal_metrics": {},
                        "underwriting_evaluation": {
                            "assigned_ta": ta_assigned,
                            "assigned_uw": uw_assigned
                        }
                    }
                }
                
                tirs_data.setdefault("submissions", []).insert(0, new_sub)
                
                with open(data_json_path, 'w', encoding='utf-8') as f:
                    json.dump(tirs_data, f, indent=2)
                    
        except Exception as e:
            print(f"Failed to update TIRSWeb data.json: {e}")
        
    return result


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
