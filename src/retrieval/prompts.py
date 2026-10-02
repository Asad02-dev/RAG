"""Prompt templates for the RAG query engine."""

SYSTEM_PROMPT = """You are an AI Native Intelligent Underwriting Agent (TAR Underwriter). Your sole role is to analyze insurance and underwriting submissions and provide comprehensive, professional underwriting responses based strictly on the provided documents.

You must only focus on underwriting and TA-related (Technical Assistant/Underwriting Assistant) activities. You are not a generic chatbot. Reject any requests that fall outside the scope of underwriting.

## Inputs You Will Receive in Context
You will be provided with various documents as context, which may include:
- Email correspondence containing submission details.
- Broker and ceding/sitting company information (country, state).
- NICS codes and policy limits.
- Author letters, bind letters, and codes.
- Underwriting rationale and analysis documents.

## Your Task
1. **Analyze the Submission**: Extract and synthesize key details (Broker, Ceding Company, Country, State, NICS, Policy Limits, etc.).
2. **Evaluate**: Review the submission against the provided underwriting rationale and analysis documents.
3. **Draft a Proper Response**: Provide a structured underwriting assessment or decision based on the gathered facts.

## Rules
1. **Scope Restriction**: Only answer questions or perform analysis related to the underwriting submission. If asked about unrelated topics, politely decline.
2. **Context Dependency**: Base your analysis ONLY on the provided context documents. Do not invent details.
3. **Cite Sources**: Cite your sources for every claim using the format: [filename, page X] or [Email from X].
4. **Professional Tone**: Maintain a highly professional, objective, and analytical tone typical of a senior TAR underwriter.
5. **No Hallucinations**: Never fabricate NICS codes, policy limits, or any submission details that are not in the context."""

QUERY_TEMPLATE = """## Submission Documents & Context

{context}

---

## Underwriting Task / Question

{question}

---

Please complete the task or answer the question based ONLY on the submission documents and context above. Remember to cite your sources and act strictly as a TAR Underwriter."""


def build_context(search_results: list[dict]) -> str:
    """Format search results into a context string for the LLM prompt."""
    if not search_results:
        return "[No relevant documents found]"

    context_parts = []
    for i, result in enumerate(search_results, 1):
        meta = result.get("metadata", {})
        file_name = meta.get("file_name", "unknown")
        page = meta.get("page_number", "?")
        section = meta.get("section_heading", "")

        header = f"**Source {i}: {file_name} (page {page})**"
        if section:
            header += f" — {section}"

        context_parts.append(f"{header}\n{result['content']}")

    return "\n\n---\n\n".join(context_parts)


def build_prompt(question: str, search_results: list[dict]) -> str:
    """Build the full prompt with context and question."""
    context = build_context(search_results)
    return QUERY_TEMPLATE.format(context=context, question=question)


SUBMISSION_CHAT_TEMPLATE = """You are answering questions about ONE specific submission (ID: {submission_id}).
Use ONLY the sections below, which all belong to this submission. If the answer is not in them,
say that it is not available in this submission's documents. Never use knowledge of other submissions.

## Submission Record

{record}

## 1-Page Summary

{summary}

## Email Body

{email_body}

## Retrieved Documents (email and attachments)

{documents}

---

## Question

{question}

---

Answer concisely and cite your sources, e.g. [filename, page X], [1-Page Summary] or [Submission Record]."""

SUMMARY_NOT_GENERATED = "[The 1-page summary has not been generated yet for this submission.]"
NO_DOCUMENTS_INDEXED = "[This email has not been ingested into the vector database yet, so no document chunks are available.]"


def build_submission_record(submission: dict) -> str:
    """Format a TIRSWeb data.json submission entry (headers, status, Cytora, worksheet) as text."""
    email = submission.get("email") or {}
    lines = [
        f"- **Submission ID**: {submission.get('id', '')}",
        f"- **Status**: {submission.get('status', 'Unknown')}",
        f"- **Clearance Status**: {submission.get('clearance_status', 'Unknown')}",
        f"- **Subject**: {email.get('subject', '')}",
        f"- **From**: {email.get('from', '')}",
        f"- **To**: {email.get('to', '')}",
    ]
    if email.get("cc"):
        lines.append(f"- **Cc**: {email['cc']}")
    lines.append(f"- **Date**: {email.get('date', '')}")
    lines.append(f"- **Email File**: {email.get('filename', '')}")

    cytora = [
        e for e in (submission.get("cytora_entries") or [])
        if isinstance(e, dict) and e.get("ExtractedValue")
    ]
    if cytora:
        lines.append("\n**Cytora Extracted Fields**:")
        lines.extend(f"- {e.get('FieldName', 'Field')}: {e['ExtractedValue']}" for e in cytora)

    worksheet = submission.get("stitch_worksheet") or {}
    for section, fields in worksheet.items():
        if isinstance(fields, dict) and fields:
            lines.append(f"\n**Stitch Worksheet — {section}**:")
            lines.extend(f"- {k}: {v}" for k, v in fields.items())

    return "\n".join(lines)


def build_submission_chat_prompt(
    question: str,
    submission: dict,
    summary_text: str | None,
    email_body_text: str,
    search_results: list[dict],
) -> str:
    """Build a prompt scoped to a single submission: record, summary, email body and its own chunks."""
    return SUBMISSION_CHAT_TEMPLATE.format(
        submission_id=submission.get("id", ""),
        record=build_submission_record(submission),
        summary=summary_text.strip() if summary_text and summary_text.strip() else SUMMARY_NOT_GENERATED,
        email_body=email_body_text.strip() or "[No email body]",
        documents=build_context(search_results) if search_results else NO_DOCUMENTS_INDEXED,
        question=question,
    )
