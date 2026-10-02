"""Unit tests for prompts module."""

from src.retrieval.prompts import (
    build_context,
    build_prompt,
    build_submission_chat_prompt,
    NO_DOCUMENTS_INDEXED,
    SUMMARY_NOT_GENERATED,
    SYSTEM_PROMPT,
)

SAMPLE_SUBMISSION = {
    "id": "SUB-123",
    "status": "ASSIGNED",
    "clearance_status": "CLEARED",
    "email": {
        "subject": "Renewal - Property",
        "from": "broker@example.com",
        "to": "uw@example.com",
        "date": "2026-09-26",
        "filename": "renewal.eml",
    },
    "cytora_entries": [
        {"FieldName": "Insured Name", "ExtractedValue": "Acme SA"},
        {"FieldName": "Empty Field", "ExtractedValue": ""},
    ],
    "stitch_worksheet": {"deal_metrics": {"line_of_business": "Property"}},
}


def test_build_context_empty():
    assert build_context([]) == "[No relevant documents found]"


def test_build_context_with_results():
    search_results = [
        {
            "content": "Refunds are processed within 14 days.",
            "metadata": {
                "file_name": "policy.pdf",
                "page_number": 3,
                "section_heading": "Refund Window",
            },
        },
        {
            "content": "Contact support@example.com for requests.",
            "metadata": {
                "file_name": "support.docx",
                "page_number": 1,
                "section_heading": "",
            },
        },
    ]

    context = build_context(search_results)
    assert "**Source 1: policy.pdf (page 3)** — Refund Window" in context
    assert "Refunds are processed within 14 days." in context
    assert "**Source 2: support.docx (page 1)**" in context
    assert "Contact support@example.com for requests." in context
    assert "\n\n---\n\n" in context


def test_build_prompt():
    search_results = [
        {
            "content": "Our SLA guarantee is 99.9%.",
            "metadata": {"file_name": "sla.txt", "page_number": 1},
        }
    ]
    prompt = build_prompt("What is the SLA?", search_results)
    assert "## Context Documents" in prompt
    assert "Our SLA guarantee is 99.9%." in prompt
    assert "## User Question" in prompt
    assert "What is the SLA?" in prompt
    assert "Please answer the question based ONLY on the context documents" in prompt


def test_build_submission_chat_prompt_with_all_sources():
    search_results = [
        {
            "content": "Deductible: USD 250,000 per occurrence.",
            "metadata": {"file_name": "renewal.eml", "page_number": 4, "section_heading": "Slip"},
        }
    ]
    prompt = build_submission_chat_prompt(
        question="What is the deductible?",
        submission=SAMPLE_SUBMISSION,
        summary_text="Insured is Acme SA, property renewal.",
        email_body_text="Please find attached the renewal slip.",
        search_results=search_results,
    )
    assert "ONE specific submission (ID: SUB-123)" in prompt
    assert "- **Status**: ASSIGNED" in prompt
    assert "- Insured Name: Acme SA" in prompt
    assert "Empty Field" not in prompt
    assert "- line_of_business: Property" in prompt
    assert "Insured is Acme SA, property renewal." in prompt
    assert "Please find attached the renewal slip." in prompt
    assert "Deductible: USD 250,000 per occurrence." in prompt
    assert "**Source 1: renewal.eml (page 4)** — Slip" in prompt
    assert "What is the deductible?" in prompt
    assert SUMMARY_NOT_GENERATED not in prompt
    assert NO_DOCUMENTS_INDEXED not in prompt


def test_build_submission_chat_prompt_without_summary_or_chunks():
    prompt = build_submission_chat_prompt(
        question="What is this email about?",
        submission=SAMPLE_SUBMISSION,
        summary_text=None,
        email_body_text="",
        search_results=[],
    )
    assert SUMMARY_NOT_GENERATED in prompt
    assert NO_DOCUMENTS_INDEXED in prompt
    assert "[No email body]" in prompt
