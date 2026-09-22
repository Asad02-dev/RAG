"""Unit tests for prompts module."""

from src.retrieval.prompts import build_context, build_prompt, SYSTEM_PROMPT


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
