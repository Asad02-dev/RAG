from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from configs.settings import get_settings
from src.llm_client import get_llm_client, candidate_models

router = APIRouter()

import os
from pathlib import Path

class SummarizeRequest(BaseModel):
    submission_id: str
    email_body: str
    cytora_json: Any
    force_regenerate: bool = False

class SummarizeResponse(BaseModel):
    summary_html: str

@router.post("/summarize", response_model=SummarizeResponse)
def generate_summary(request: SummarizeRequest):
    settings = get_settings()
    
    # Check for existing summary
    summaries_dir = Path("data/summaries")
    summaries_dir.mkdir(parents=True, exist_ok=True)
    
    summary_file = summaries_dir / f"{request.submission_id}.html"
    
    if summary_file.exists() and not request.force_regenerate:
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                return SummarizeResponse(summary_html=f.read().strip())
        except Exception:
            pass # fallback to regenerate

    # Aggressively truncate to stay under the 16k token limit
    email_text = str(request.email_body)[:10000]
    cytora_text = str(request.cytora_json)[:5000]
    
    prompt = f"""
    You are an expert Technical Assistant (TA) and Underwriter Assistant. Generate a comprehensive 1-page executive summary based on the following email and Cytora JSON extraction data. The Underwriter must be able to make a decision based purely on this summary without reading the original email.
    
    Return ONLY valid HTML that can be injected into the UI (do not include markdown code block syntax like ```html).
    The HTML should follow this detailed structure exactly:
    
    <h4>Submission Overview</h4>
    <p><strong>Insured Name:</strong> [Insured Name]</p>
    <p><strong>Broker/Sender:</strong> [Broker Firm and Contact Name]</p>
    <p><strong>Line of Business:</strong> [LOB]</p>
    <p><strong>Effective Date:</strong> [Date]</p>
    <p><strong>Intent/Action Required:</strong> [E.g., New Submission, Follow-up, Missing Information]</p>
    
    <hr class="my-3 border-light">
    <h4>Email Summary & Context</h4>
    <p>[A detailed, multi-paragraph summary of the email's content, capturing all nuances, broker requests, referenced attached documents, and missing information. Do not leave out any operational details.]</p>
    
    <hr class="my-3 border-light">
    <h4>Key Extraction Details</h4>
    <ul>
        <li><strong>Limits Requested:</strong> [Limits]</li>
        <li><strong>Deductibles/Attachments:</strong> [Deductibles]</li>
        <li><strong>Revenues/TIV:</strong> [Revenues/TIV]</li>
    </ul>

    <hr class="my-3 border-light">
    <h4>Key Risk Factors</h4>
    <ul class="risk-list">
        <li><span class="conf-badge high">High</span> [Detailed Risk 1]</li>
        <li><span class="conf-badge review">Review Needed</span> [Detailed Risk 2]</li>
    </ul>
    
    <hr class="my-3 border-light">
    <h4>Underwriting Recommendation</h4>
    <p>[A thorough paragraph with explicit recommendations to the Underwriter (e.g., Proceed to Quote, Decline, Request More Info), based on the risk profile and appetite guidelines.]</p>

    Email Body:
    {email_text}

    Cytora Extraction:
    {cytora_text}
    """
    
    llm = get_llm_client(settings)

    models_to_try = candidate_models(settings.get_llm_model, settings.fallback_models_list)
    html = None
    last_err = None
    for m in models_to_try:
        try:
            html = llm.generate(model=m, prompt=prompt, temperature=0.2)
            break
        except Exception as e:
            last_err = e
            continue

    if html is None:
        raise last_err

    if html.startswith("```html"):
        html = html.split("```html", 1)[1].rsplit("```", 1)[0]
    elif html.startswith("```"):
        html = html.split("```", 1)[1].rsplit("```", 1)[0]
        
    html = html.strip()
    
    # Save it to disk
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(html)
        
    return SummarizeResponse(summary_html=html)

class ExtractFieldsRequest(BaseModel):
    submission_id: str
    email_body: str
    cytora_json: Any
    field_names: list[str]

class ExtractFieldsResponse(BaseModel):
    extracted_data: dict[str, Any]

@router.post("/extract_fields", response_model=ExtractFieldsResponse)
def extract_fields(request: ExtractFieldsRequest):
    settings = get_settings()
    
    extractions_dir = Path("data/extractions")
    extractions_dir.mkdir(parents=True, exist_ok=True)
    cache_file = extractions_dir / f"{request.submission_id}.json"
    
    import json
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return ExtractFieldsResponse(extracted_data=json.load(f))
        except Exception:
            pass
            
    # 1. Map fields already present in Cytora
    cytora_fields = {}
    remaining_fields = []
    
    # Simple mapping logic (adjust based on exact JSON structure)
    if isinstance(request.cytora_json, list):
        for entry in request.cytora_json:
            fname = entry.get("FieldName")
            # For exact match or partial match (like 'Insured Name')
            for req_field in request.field_names:
                if fname and (fname.lower() in req_field.lower() or req_field.lower() in fname.lower()):
                    conf_val = entry.get("ConfidenceIndex", 95)
                    try:
                        conf = int(conf_val) if conf_val != "" and conf_val is not None else 95
                    except (ValueError, TypeError):
                        conf = 95
                        
                    cytora_fields[req_field] = {
                        "value": entry.get("ExtractedValue", "-"),
                        "rationale": "Directly extracted from Cytora payload",
                        "source": "Cytora AI",
                        "confidence": conf
                    }
    
    for f in request.field_names:
        if f not in cytora_fields:
            remaining_fields.append(f)
            
    # 2. Extract remaining fields via Gemini
    llm_fields = {}
    if remaining_fields:
        llm = get_llm_client(settings)

        email_text = str(request.email_body)[:15000] # Aggressively truncate
        
        prompt = f"""
        You are an expert AI underwriting assistant. Extract the exact values for the requested fields based on the provided email.
        If a field's value cannot be found, output "-" for that field. Do not make up information.
        CRITICAL: You MUST return a JSON object containing exactly every single key listed in the 'Requested Fields' list, without missing any. 
        The values must be objects containing:
        - "value": the extracted string (or "-" if not found)
        - "rationale": a short 1-sentence description of how/why this was extracted
        - "source": "Email Body"
        - "confidence": an integer from 0 to 100 representing confidence
        
        Email Body:
        {email_text}
        
        Requested Fields:
        {remaining_fields}
        """
        
        models_to_try = candidate_models(settings.get_llm_model, settings.fallback_models_list)
        response_text = None
        for m in models_to_try:
            try:
                response_text = llm.generate(
                    model=m,
                    prompt=prompt,
                    temperature=0.1,
                    max_output_tokens=4096,
                    json_mode=True,
                )
                break
            except Exception:
                continue

        try:
            data = json.loads(response_text)
            if isinstance(data, list) and len(data) > 0:
                llm_fields = data[0]
            elif isinstance(data, dict):
                llm_fields = data
        except Exception:
            pass

    # 3. Merge and cache
    final_data = {**cytora_fields, **llm_fields}
    
    # Ensure all fields requested are present
    for f in request.field_names:
        if f not in final_data:
            final_data[f] = {"value": "-", "rationale": "Not found", "source": "System", "confidence": 0}
            
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(final_data, f)
        
    return ExtractFieldsResponse(extracted_data=final_data)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TIRSWEB_DATA_PATH = PROJECT_ROOT / "web" / "tirsweb" / "data.json"
SUMMARIES_DIR = PROJECT_ROOT / "data" / "summaries"
MAX_EMAIL_BODY_CHARS = 8000

class ChatRequest(BaseModel):
    message: str
    submission_id: str | None = None

class ChatResponse(BaseModel):
    reply: str
    sources: list[dict] = []
    summary_used: bool = False

def _load_submission(submission_id: str) -> dict | None:
    import json
    if not TIRSWEB_DATA_PATH.exists():
        return None
    with open(TIRSWEB_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return next((s for s in data.get("submissions", []) if s.get("id") == submission_id), None)

@router.post("/chat", response_model=ChatResponse)
def handle_chat(request: ChatRequest):
    """Answer a question about one submission, grounded in its summary, data.json entry and its own ChromaDB chunks.

    With no submission_id, answer from all documents in ChromaDB instead.
    """
    import logging
    from src.api.main import get_search_client
    from src.ingestion.document_processor import DocumentProcessor
    from src.retrieval.prompts import SYSTEM_PROMPT, build_submission_chat_prompt

    logger = logging.getLogger(__name__)

    if not request.submission_id:
        # No submission open: answer from all documents in the vector DB (same as the general /api/query chat)
        from src.api.main import get_query_engine
        result = get_query_engine().query(request.message)
        return ChatResponse(reply=result.answer, sources=result.sources)

    submission = _load_submission(request.submission_id)
    if not submission:
        return ChatResponse(reply=f"Submission '{request.submission_id}' was not found.")

    settings = get_settings()
    llm = get_llm_client(settings)
    if not llm.has_api_key:
        return ChatResponse(reply=f"{llm.key_env_name} is not set. Please add your API key to `.env`.")

    # 1. Saved 1-page summary (optional)
    summary_text = None
    summary_file = SUMMARIES_DIR / f"{request.submission_id}.html"
    if summary_file.exists():
        summary_text = DocumentProcessor._html_to_markdown(summary_file.read_text(encoding="utf-8"))

    # 2. Email body from data.json (stored as HTML)
    email = submission.get("email") or {}
    email_body_text = DocumentProcessor._html_to_markdown(str(email.get("body") or ""))[:MAX_EMAIL_BODY_CHARS]

    # 3. ChromaDB chunks belonging to this email only
    search_results = []
    email_file = email.get("filename")
    if email_file:
        try:
            search_results = get_search_client().search(
                query=request.message,
                top_k=settings.top_k_results,
                filter_metadata={"file_name": email_file},
            )
        except Exception as e:
            logger.warning(f"Chunk search failed for {email_file}: {e}. Answering without document chunks.")

    prompt = build_submission_chat_prompt(
        question=request.message,
        submission=submission,
        summary_text=summary_text,
        email_body_text=email_body_text,
        search_results=search_results,
    )
    full_prompt = f"{SYSTEM_PROMPT}\n\n---\n\n{prompt}"

    models_to_try = candidate_models(settings.get_llm_model, settings.fallback_models_list)
    reply = "Sorry, I encountered an error: All models failed."
    for m in models_to_try:
        try:
            reply = llm.generate(model=m, prompt=full_prompt, temperature=0.3)
            break
        except Exception as e:
            reply = f"Sorry, I encountered an error: {str(e)}"
            continue

    sources = []
    seen = set()
    for r in search_results:
        meta = r.get("metadata", {})
        key = (meta.get("file_name"), meta.get("page_number"), meta.get("section_heading"))
        if key not in seen:
            seen.add(key)
            sources.append({
                "file_name": meta.get("file_name", "unknown"),
                "page_number": meta.get("page_number", 0),
                "section_heading": meta.get("section_heading", ""),
            })

    return ChatResponse(reply=reply, sources=sources, summary_used=summary_text is not None)
