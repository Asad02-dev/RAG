from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from google import genai
from google.genai import types
from configs.settings import get_settings

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

    # Ensure we strictly use the Gemma model
    llm_model = getattr(settings, 'gemini_llm_model', "gemma-4-26b-a4b-it")
    
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
    
    client = genai.Client(api_key=settings.gemini_api_key or "dummy-api-key")
    
    models_to_try = [llm_model] + getattr(settings, 'fallback_models_list', [])
    response = None
    last_err = None
    for m in models_to_try:
        try:
            response = client.models.generate_content(
                model=m,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2)
            )
            break
        except Exception as e:
            last_err = e
            continue
            
    if not response:
        raise last_err
    
    
    html = response.text
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
        client = genai.Client(api_key=settings.gemini_api_key or "dummy-api-key")
        
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
        
        llm_model = getattr(settings, 'gemini_llm_model', "gemma-4-26b-a4b-it")
        
        models_to_try = [llm_model] + getattr(settings, 'fallback_models_list', [])
        response = None
        for m in models_to_try:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=4096,
                        response_mime_type="application/json",
                    )
                )
                break
            except Exception:
                continue
        
        try:
            data = json.loads(response.text)
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

class ChatRequest(BaseModel):
    message: str
    submission_context: str

class ChatResponse(BaseModel):
    reply: str

@router.post("/chat", response_model=ChatResponse)
def handle_chat(request: ChatRequest):
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key or "dummy-api-key")
    
    import re
    
    # Clean up the context to avoid 500 errors from massive HTML/Base64 payloads
    clean_context = re.sub(r'<[^>]+>', ' ', request.submission_context) # strip HTML tags
    clean_context = clean_context[:15000] # Truncate heavily for Gemma 16k limit

    prompt = f"""
    You are a Technical Assistant (TA) Underwriting Chatbot. Answer the user's question concisely based on the following submission context.
    If you don't know the answer based on the context, say so.
    
    Submission Context:
    {clean_context}
    
    User Question:
    {request.message}
    """
    
    llm_model = getattr(settings, 'gemini_llm_model', "gemma-4-26b-a4b-it")
    
    models_to_try = [llm_model] + getattr(settings, 'fallback_models_list', [])
    reply = "Sorry, I encountered an error: All models failed."
    for m in models_to_try:
        try:
            response = client.models.generate_content(
                model=m,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            reply = response.text
            break
        except Exception as e:
            reply = f"Sorry, I encountered an error: {str(e)}"
            continue
        
    return ChatResponse(reply=reply)
