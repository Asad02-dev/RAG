"""Unit tests for EML email processing, attachment extraction, and chunking."""

import email
from email.message import EmailMessage
from email.policy import default
from pathlib import Path
import pytest

from src.ingestion.document_processor import DocumentProcessor, ProcessedDocument
from src.ingestion.chunker import Chunker
from src.ingestion.file_manager import FileManager


def test_process_plain_text_eml(tmp_path):
    """Test processing a basic plain text email without attachments."""
    msg = EmailMessage()
    msg["Subject"] = "Quarterly Business Review"
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    msg["Date"] = "Mon, 15 Jan 2026 10:00:00 +0000"
    msg.set_content("Hi Bob,\n\nPlease find the review schedule attached.\nBest regards,\nAlice")

    eml_file = tmp_path / "email_simple.eml"
    eml_file.write_bytes(msg.as_bytes())

    processor = DocumentProcessor()
    doc = processor.process(eml_file)

    assert isinstance(doc, ProcessedDocument)
    assert doc.document_type == "eml"
    assert doc.file_name == "email_simple.eml"
    assert "Quarterly Business Review" in doc.content_markdown
    assert "alice@example.com" in doc.content_markdown
    assert "Please find the review schedule attached." in doc.content_markdown
    assert doc.metadata["subject"] == "Quarterly Business Review"
    assert doc.metadata["from"] == "alice@example.com"
    assert doc.metadata["attachment_count"] == 0


def test_process_html_only_eml(tmp_path):
    """Test processing an email that only contains HTML body."""
    msg = EmailMessage()
    msg["Subject"] = "HTML Newsletter"
    msg["From"] = "news@example.com"
    msg["To"] = "subscriber@example.com"
    msg.add_header("Content-Type", "text/html")
    msg.set_payload(
        "<html><body>"
        "<h1>Weekly Digest</h1>"
        "<p>Welcome to our weekly updates:</p>"
        "<ul><li>Feature A released</li><li>Bug B fixed</li></ul>"
        "</body></html>"
    )

    eml_file = tmp_path / "email_html.eml"
    eml_file.write_bytes(msg.as_bytes())

    processor = DocumentProcessor()
    doc = processor.process(eml_file)

    assert doc.document_type == "eml"
    assert "Weekly Digest" in doc.content_markdown
    assert "Feature A released" in doc.content_markdown
    assert "Bug B fixed" in doc.content_markdown


def test_process_eml_with_text_and_unsupported_attachments(tmp_path):
    """Test processing an email with text attachment and binary unsupported attachment."""
    msg = EmailMessage()
    msg["Subject"] = "Project Deliverables"
    msg["From"] = "lead@example.com"
    msg["To"] = "team@example.com"
    msg.set_content("Please inspect the attached documentation and data archive.")

    # 1. Text attachment
    msg.add_attachment(
        "Project Notes:\n1. Complete user testing.\n2. Review security compliance.\n".encode("utf-8"),
        maintype="text",
        subtype="plain",
        filename="project_notes.txt",
    )

    # 2. Binary attachment (e.g. zip)
    msg.add_attachment(
        b"PK\x03\x04\x00\x00dummyzipcontent",
        maintype="application",
        subtype="zip",
        filename="data_backup.zip",
    )

    eml_file = tmp_path / "deliverables.eml"
    eml_file.write_bytes(msg.as_bytes())

    processor = DocumentProcessor()
    doc = processor.process(eml_file)

    assert doc.document_type == "eml"
    assert doc.metadata["attachment_count"] == 2
    assert "project_notes.txt" in doc.metadata["attachments"]
    assert "data_backup.zip" in doc.metadata["attachments"]

    # Verify Attachments Summary section
    assert "## Attachments Summary" in doc.content_markdown
    assert "project_notes.txt" in doc.content_markdown
    assert "data_backup.zip" in doc.content_markdown

    # Verify text attachment content was extracted
    assert "## Attachment: project_notes.txt" in doc.content_markdown
    assert "Complete user testing." in doc.content_markdown

    # Verify unsupported binary attachment has notice
    assert "## Attachment: data_backup.zip" in doc.content_markdown
    assert "content extraction not supported" in doc.content_markdown


def test_chunking_eml_document():
    """Test that Chunker generates distinct chunks for email subject, body, and attachments."""
    sample_markdown = """# Email: Project Status Update

## Email Details
- **Subject**: Project Status Update
- **From**: manager@company.com
- **To**: client@partner.com
- **Date**: Tue, 10 Feb 2026 14:00:00 +0000
- **Attachments Count**: 1

## Email Body
Hello Client Team,
Everything is tracking on schedule for the Q1 milestone.

## Attachments Summary
- **Attachment 1**: `report.pdf` (application/pdf, 1.2 MB)

## Attachment: report.pdf
**File**: `report.pdf` | **Type**: application/pdf | **Size**: 1.2 MB

### Attachment: report.pdf - Page 1
Executive Summary: All deliverables are in progress.

### Attachment: report.pdf - Page 2
Financial Overview: Budget variance remains under 2%.
"""

    chunker = Chunker(max_tokens=200)
    chunks = chunker.chunk_document(
        content_markdown=sample_markdown,
        source_file="sample.eml",
        file_name="sample.eml",
        document_type="eml",
    )

    headings = [c.section_heading for c in chunks]
    pages = [c.page_number for c in chunks]

    # Verify email metadata chunk
    assert any("Email Details" in h for h in headings)

    # Verify email body chunk
    assert any("Email Body" in h for h in headings)

    # Verify attachments summary chunk
    assert any("Attachments Summary" in h for h in headings)

    # Verify attachment content chunks with proper headings & page numbers
    assert any("Attachment: report.pdf - Page 1" in h for h in headings)
    assert any("Attachment: report.pdf - Page 2" in h for h in headings)

    # Verify page number extracted from Page 2
    page_2_chunk = next(c for c in chunks if "Page 2" in c.section_heading)
    assert page_2_chunk.page_number == 2


def test_file_manager_includes_eml(tmp_path):
    """Test that FileManager scans and recognizes .eml files."""
    eml_file = tmp_path / "email.eml"
    eml_file.write_text("Subject: Test\n\nHello", encoding="utf-8")

    fm = FileManager(tmp_path)
    files = fm.scan_documents()
    eml_files = [f for f in files if f.extension == ".eml"]

    assert len(eml_files) == 1
    assert eml_files[0].name == "email.eml"


def test_process_sample_eml_file():
    """Integration test processing the real sample .eml file in data/documents."""
    sample_path = Path("data/documents/RERANDSTADNORTHAMERICAINCTransReCert910326009DocumentRequestNo_Profliability_ 32075.eml")
    if not sample_path.exists():
        pytest.skip("Sample .eml file not found")

    processor = DocumentProcessor()
    doc = processor.process(sample_path)

    assert doc.document_type == "eml"
    assert "RANDSTAD NORTH AMERICA" in doc.content_markdown
    assert doc.metadata["attachment_count"] >= 1
    assert any(att.endswith(".pdf") for att in doc.metadata["attachments"])

    # Chunk the real sample document
    chunker = Chunker()
    chunks = chunker.chunk_document(
        content_markdown=doc.content_markdown,
        source_file=doc.source_file,
        file_name=doc.file_name,
        document_type=doc.document_type,
    )

    assert len(chunks) > 10
    # Ensure chunks from email body exist
    assert any(c.section_heading == "Email Body" for c in chunks)
    # Ensure chunks from the PDF attachment exist
    assert any("Attachment:" in c.section_heading and "Page" in c.section_heading for c in chunks)
