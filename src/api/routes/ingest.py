"""Ingest route — POST /api/ingest for uploading and processing documents."""

import shutil
from pathlib import Path
import json
import uuid
import email
from email import policy
import os
import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException

from src.api.models import IngestResponse, DocumentInfo, StatsResponse
from src.api.main import get_pipeline, get_file_manager, get_indexer
from configs.settings import get_settings
from src.llm_client import get_llm_client

try:
    from typesafe_sdk import TypeSafeClient, Choice
except ImportError:
    TypeSafeClient = None
    Choice = None

router = APIRouter()


def _run_classification_and_routing(file_name: str, target_path: str, pipeline):
    # Ensure logs folder exists
    logs_dir = Path("data/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{file_name}.log"
    
    def log_step(step, msg):
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] {step}: {msg}\n")
            
    log_step("INGESTION_START", f"Started processing {file_name}")
    log_step("VECTOR_DB_SUCCESS", "Successfully stored in Vector DB")

    try:
        subject = file_name
        body = "Document content"
        extracted_data = {}
        
        processor = pipeline.processor
        try:
            doc = processor.process(target_path)
            body = doc.content_markdown[:5000] # Truncate for LLM payload
        except Exception as e:
            log_step("PROCESSOR_ERROR", f"Error extracting document text: {e}")
            
        if target_path.endswith('.eml'):
            try:
                with open(target_path, 'rb') as f:
                    msg = email.message_from_binary_file(f, policy=policy.default)
                subject = msg.get('subject', 'No Subject')
            except Exception as e:
                log_step("EMAIL_PARSE_ERROR", f"Failed to parse email subject: {e}")

        # Classification via Jev
        log_step("CLASSIFICATION", "Starting classification using Jev (TypeSafe)")
        llm_label = "Other"
        llm_confidence = 0.0
        
        if TypeSafeClient:
            settings = get_settings()
            ts_client = TypeSafeClient(api_key=settings.typesafe_api_key or os.getenv("TYPESAFE_API_KEY", "mock"))
            LLM_CATEGORIES = {
                "Submission": "Request for terms, quote, or renewal terms. Contains submission pack. Not a reply inside an existing thread.",
                "Update": "Supplying info or docs for an existing risk (reply, loss runs, clarification, quote feedback). No new request for terms.",
                "Policy_Review": "Issued policy, binder, endorsement, or dec page attached for review.",
                "Declination": "Deal is explicitly declined, not proceeding, withdrawn, placed elsewhere.",
                "Other": "Any other intent, noise, or unclassified."
            }
            try:
                response = ts_client.system_one(
                    state=f"Subject: {subject}\nBody: {body}",
                    questions={
                        "intent": Choice(
                            instructions="Pick the label that fits the sender's main purpose.",
                            criteria=LLM_CATEGORIES
                        )
                    }
                )
                llm_label = response.choices["intent"].choice
                llm_confidence = response.choices["intent"].confidence
                log_step("JEV_RAW_RESPONSE", str(response))
                log_step("CLASSIFICATION_SUCCESS", f"Jev Classification: {llm_label} (Confidence: {llm_confidence})")
            except Exception as e:
                log_step("CLASSIFICATION_ERROR", f"Jev API Error: {e}")
        else:
            log_step("CLASSIFICATION_ERROR", "TypeSafeClient not available")

        # Extraction (fallback if Cytora not provided)
        log_step("EXTRACTION", "Extracting key fields using LLM")
        try:
            settings = get_settings()
            llm = get_llm_client(settings)
            extraction_prompt = f"""
            Extract the following key fields from this document:
            - Insured Name
            - Limits Requested
            - Deductibles
            - Line of Business
            Return a JSON object with these keys and their string values (or "-" if not found).
            Document:
            {body}
            """
            from src.llm_client import candidate_models
            models_to_try = candidate_models(settings.get_llm_model, settings.fallback_models_list)
            response_text = None
            for m in models_to_try:
                try:
                    response_text = llm.generate(
                        model=m,
                        prompt=extraction_prompt,
                        temperature=0.1,
                        max_output_tokens=1024,
                        json_mode=True,
                    )
                    break
                except Exception:
                    continue
                    
            if response_text:
                extracted_data = json.loads(response_text)
                log_step("EXTRACTION_SUCCESS", f"Extracted: {json.dumps(extracted_data)}")
            else:
                log_step("EXTRACTION_WARNING", "Failed to extract fields")
        except Exception as e:
            log_step("EXTRACTION_ERROR", f"Error during extraction: {e}")

        # Determine Routing Action and Assignment
        log_step("ROUTING", f"Determining queue and action based on label '{llm_label}'")
        status = "ASSIGNED"
        ta_assigned = "Ringwood, John (Auto)"
        uw_assigned = "Vonserlime, Rylkki (Auto)"
        
        if llm_label == "Submission":
            queue_assigned = "UW_QUEUE_1"
            action_details = "Proceed to clearance and generate quote"
            clearance_status = "CLEARED"
        elif llm_label == "Update":
            queue_assigned = "ASSIGNED_TA"
            action_details = "Attach update to DMS"
            clearance_status = "N/A"
        elif llm_label == "Policy_Review":
            queue_assigned = "ASSIGNED_TA"
            action_details = "Perform policy review"
            clearance_status = "N/A"
        elif llm_label == "Declination":
            queue_assigned = "ASSIGNED_TA"
            action_details = "Notify UW of declination"
            clearance_status = "N/A"
        else:
            status = "UNASSIGNED"
            ta_assigned = "Unassigned"
            uw_assigned = "Unassigned"
            queue_assigned = "UNASSIGNED_QUEUE"
            action_details = "Manual review required"
            clearance_status = "N/A"
            
        log_step("ROUTING_SUCCESS", f"Assigned to {status} ({queue_assigned}) with action: {action_details}")

        # Load TIRSWeb data.json and append this submission
        data_json_path = Path(__file__).parent.parent.parent.parent / "web" / "tirsweb" / "data.json"
        if data_json_path.exists():
            with open(data_json_path, 'r', encoding='utf-8') as f:
                tirs_data = json.load(f)
            
            insured_name = extracted_data.get("Insured Name", "Extracted from RAG")
            if not isinstance(insured_name, str):
                insured_name = "Extracted from RAG"
            
            new_sub = {
                "id": f"SUB-{uuid.uuid4().hex[:8]}",
                "status": status,
                "clearance_status": clearance_status,
                "email": {
                    "subject": subject,
                    "from": "Unknown Sender",
                    "to": "",
                    "cc": "",
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "filename": file_name,
                    "body": f"Indexed content from RAG pipeline."
                },
                "stitch_worksheet": {
                    "account_overview": {
                        "insured_name": insured_name
                    },
                    "deal_metrics": {
                        "limits_requested": str(extracted_data.get("Limits Requested", "-")),
                        "deductibles": str(extracted_data.get("Deductibles", "-")),
                        "line_of_business": str(extracted_data.get("Line of Business", "-"))
                    },
                    "underwriting_evaluation": {
                        "assigned_ta": ta_assigned,
                        "assigned_uw": uw_assigned,
                        "suggested_action": action_details,
                        "queue": queue_assigned,
                        "intent_label": llm_label,
                        "confidence": llm_confidence
                    }
                }
            }
            
            tirs_data.setdefault("submissions", []).insert(0, new_sub)
            
            with open(data_json_path, 'w', encoding='utf-8') as f:
                json.dump(tirs_data, f, indent=2)
                
            log_step("QUEUE_UPDATE", f"Successfully appended document to {status} queue in data.json")
            
    except Exception as e:
        log_step("PIPELINE_ERROR", f"Pipeline encountered an error: {e}")
        print(f"Failed to process in pipeline: {e}")

    log_step("INGESTION_END", "Pipeline processing completed")


@router.post("/ingest", response_model=IngestResponse)
def ingest_documents(files: list[UploadFile] = File(None)):
    """Upload and process documents, or process all pending files in data/documents/."""
    pipeline = get_pipeline()
    file_manager = get_file_manager()

    if files and files[0].filename:
        # Save uploaded files to documents directory
        for upload_file in files:
            dest = file_manager.documents_dir / upload_file.filename
            with open(dest, "wb") as f:
                shutil.copyfileobj(upload_file.file, f)

    # Get pending files before processing
    pending_files = file_manager.get_pending_files()

    # Process all pending files
    result = pipeline.ingest_all()

    # Run routing logic for each file that was successfully processed
    for f in pending_files:
        if not any(err['file'] == f.name for err in result.get("errors", [])):
            _run_classification_and_routing(f.name, f.path, pipeline)

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
        
    _run_classification_and_routing(file_name, target.path, pipeline)
        
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
