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

    client = genai.Client(api_key=settings.gemini_api_key or "dummy-api-key")
    prompt = f"""
    You are an expert underwriter assistant. Generate a 1-page executive summary based on the following email and Cytora JSON extraction data.
    Return ONLY valid HTML that can be injected into the UI (do not include markdown code block syntax like ```html). 
    The HTML should follow this structure exactly:
    <h4>Executive Summary</h4>
    <p>[A brief paragraph summarizing the submission, the insured name, and line of business based on the data.]</p>
    <hr class="my-3 border-light">
    <h4>Key Risk Factors</h4>
    <ul class="risk-list">
        <li><span class="conf-badge high">High</span> [Risk 1]</li>
        <li><span class="conf-badge review">Medium</span> [Risk 2]</li>
    </ul>
    <hr class="my-3 border-light">
    <h4>Underwriting Recommendation</h4>
    <p>[A paragraph with recommendations based on the risk profile.]</p>

    Email Body:
    {request.email_body}

    Cytora Extraction:
    {request.cytora_json}
    """
    
    # Use fallback if setting not available
    llm_model = getattr(settings, 'gemini_llm_model', "gemini-1.5-pro")
    
    response = client.models.generate_content(
        model=llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2)
    )
    
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
        {request.email_body}
        
        Requested Fields:
        {remaining_fields}
        """
        
        llm_model = getattr(settings, 'gemini_llm_model', "gemini-1.5-pro")
        
        response = client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4096,
                response_mime_type="application/json",
            )
        )
        
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
    
    prompt = f"""
    You are a Technical Assistant (TA) Underwriting Chatbot. Answer the user's question concisely based on the following submission context.
    If you don't know the answer based on the context, say so.
    
    Submission Context:
    {request.submission_context}
    
    User Question:
    {request.message}
    """
    
    llm_model = getattr(settings, 'gemini_llm_model', "gemini-1.5-pro")
    
    try:
        response = client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        reply = response.text
    except Exception as e:
        reply = f"Sorry, I encountered an error: {str(e)}"
        
    return ChatResponse(reply=reply)
