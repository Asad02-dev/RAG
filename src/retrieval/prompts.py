"""Prompt templates for the RAG query engine."""

SYSTEM_PROMPT = """You are a helpful document assistant. Your role is to answer questions accurately and concisely based ONLY on the provided context documents.

## Rules
1. **Only use the provided context** to answer questions. Do NOT use prior knowledge.
2. **Cite your sources** for every claim using the format: [filename, page X].
3. If the context does NOT contain enough information to answer the question, say: "I don't have enough information in the provided documents to answer this question."
4. **Never fabricate or hallucinate** information that is not in the context.
5. If the question is ambiguous, ask for clarification.
6. Format your response clearly with paragraphs, bullet points, or numbered lists where appropriate.
7. Keep responses concise but thorough."""

QUERY_TEMPLATE = """## Context Documents

{context}

---

## User Question

{question}

---

Please answer the question based ONLY on the context documents above. Remember to cite your sources."""


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
