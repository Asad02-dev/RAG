from typing import Annotated, Dict, List, Optional, Any
from typing_extensions import TypedDict
import operator

class UnderwritingState(TypedDict):
    # Core Identifiers
    tirs_submission_key: str                     # LangGraph Thread ID & TIRS Primary Key
    is_existing_submission: bool                 # True if update to existing deal
    email_id: str
    email_category: str                          # "SUBMISSION" or "FOLLOW_UP"
    
    # Ingestion Payloads
    email_raw: Dict[str, Any]                    # From, To, CC, Subject, Body, Timestamp
    cytora_json: Dict[str, Any]                  # Pre-parsed ingestion payload from Cytora/TRAIT
    raw_attachment_paths: List[str]              # Paths to PDF, XLSX, DOCX attachments
    
    # Extraction & Enrichment
    multimodal_extractions: Dict[str, Any]       # Extracted SOV tables, loss runs, slip terms
    company_research: Dict[str, Any]             # Employees, market cap, legal/sanction status
    stitch_worksheet: Dict[str, Any]             # Merged analysis sheet & 1-page summary
    
    # Clearance & ElasticSearch
    clearance_status: str                        # "CLEARED", "CONFLICT", "AMBIGUOUS", "TA_REVIEW"
    clearance_confidence: float                  # 0.0 to 1.0 (Threshold: 0.95)
    matched_submission_keys: List[str]
    
    # RAG & Auto-Quote
    underwriting_appetite_fit: Dict[str, Any]    # ChromaDB query result (rules, class appetite)
    quote_layers: List[Dict[str, Any]]           # Attachment, Limit, Deductible, Premium
    quote_letter_content: str                    # Markdown/HTML rendered formal quote letter
    auto_quote_approved: bool                    # Flag indicating zero-touch quote execution
    
    # Execution & UI Automation
    assigned_queue: str                          # Mapped UW/TA queue
    ta_actions_pending: List[str]                # ["ATTACH_DMS", "CREATE_SUBMISSION", "AUTO_QUOTE"]
    ta_actions_completed: List[Dict[str, Any]]   # Execution receipts and UI logs
    ta_assist_chat_log: List[Dict[str, str]]     # TA Assist interaction logs
    uw_assist_chat_log: List[Dict[str, str]]     # UW Assist interaction logs
    
    # Field-Level Explainability & Provenance (UI Tooltip / AI Hover)
    field_provenance: Dict[str, Dict[str, Any]]  # Maps field_id -> {value, action, rationale, source_doc, snippet, confidence}

    # Auditing & Traceability
    audit_trail: Annotated[List[str], operator.add]
    error_messages: Annotated[List[str], operator.add]
