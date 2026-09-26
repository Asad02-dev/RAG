from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from google import genai
from google.genai import types
from src.api.main import get_settings_dep

router = APIRouter()

class SummarizeRequest(BaseModel):
    email_body: str
    cytora_json: Any

class SummarizeResponse(BaseModel):
    summary_html: str

@router.post("/summarize", response_model=SummarizeResponse)
def generate_summary(request: SummarizeRequest):
    settings = get_settings_dep()
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
    <button class="btn primary btn-sm mt-4">Generate Final Document</button>

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
        
    return SummarizeResponse(summary_html=html.strip())

class ExtractFieldsRequest(BaseModel):
    email_body: str
    cytora_json: Any
    field_names: list[str]

class ExtractFieldsResponse(BaseModel):
    extracted_data: dict[str, Any]

@router.post("/extract_fields", response_model=ExtractFieldsResponse)
def extract_fields(request: ExtractFieldsRequest):
    settings = get_settings_dep()
    client = genai.Client(api_key=settings.gemini_api_key or "dummy-api-key")
    prompt = f"""
    You are an expert AI underwriting assistant. Extract the exact values for the requested fields based on the provided email and Cytora AI extraction data.
    If a field's value cannot be found in the email or cytora data, output an empty string or "-" for that field. Do not make up information.
    CRITICAL: You MUST return a JSON object containing exactly every single key listed in the 'Requested Fields' list, without missing any. 
    The values must be objects containing:
    - "value": the extracted string (or "-" if not found)
    - "rationale": a short 1-sentence description of how/why this was extracted
    - "source": the source of extraction (e.g., "Email Body", "Email Subject", "Cytora AI")
    - "confidence": an integer from 0 to 100 representing confidence
    
    Email Body:
    {request.email_body}

    Cytora Extraction:
    {request.cytora_json}
    
    Requested Fields:
    {request.field_names}
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
    
    import json
    try:
        data = json.loads(response.text)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
    except Exception:
        data = {}
        
    return ExtractFieldsResponse(extracted_data=data)
