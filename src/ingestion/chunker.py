"""Chunker — splits documents into semantic, layout-aware chunks for embedding."""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A single chunk of text with metadata, ready for embedding."""

    chunk_id: str
    content: str
    source_file: str
    file_name: str
    document_type: str
    page_number: int
    section_heading: str
    chunk_index: int
    token_count: int = 0


class Chunker:
    """Split processed documents into retrieval-optimized chunks.

    Three-tier strategy:
    1. Layout-Aware: Split on Markdown headings (natural section boundaries)
    2. Semantic: Use RecursiveCharacterTextSplitter within large sections
    3. Token-Limited: Ensure no chunk exceeds max_tokens
    """

    def __init__(self, max_tokens: int = 500, overlap_tokens: int = 50):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self._tokenizer = None

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken (cl100k_base encoding) or character approximation."""
        if self._tokenizer is None:
            try:
                import tiktoken
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._tokenizer = False
        if self._tokenizer:
            try:
                return len(self._tokenizer.encode(text))
            except Exception:
                pass
        return max(1, len(text) // 4)

    def chunk_document(
        self,
        content_markdown: str,
        source_file: str,
        file_name: str,
        document_type: str,
    ) -> list[Chunk]:
        """Split a Markdown document into retrieval-optimized chunks."""
        if not content_markdown.strip():
            return []

        # Step 1: Split by Markdown headings (layout-aware)
        sections = self._split_by_headings(content_markdown)

        # Step 2 & 3: For each section, apply recursive splitting + token limits
        chunks: list[Chunk] = []
        chunk_index = 0

        for section in sections:
            heading = section["heading"]
            text = section["content"]
            page = section.get("page", 1)

            token_count = self._count_tokens(text)

            if token_count <= self.max_tokens:
                # Section fits in one chunk — add context heading
                enriched = self._enrich_chunk(heading, text)
                chunks.append(Chunk(
                    chunk_id=f"{file_name}::chunk_{chunk_index}",
                    content=enriched,
                    source_file=source_file,
                    file_name=file_name,
                    document_type=document_type,
                    page_number=page,
                    section_heading=heading,
                    chunk_index=chunk_index,
                    token_count=self._count_tokens(enriched),
                ))
                chunk_index += 1
            else:
                # Section too large — apply recursive splitting
                sub_chunks = self._recursive_split(text)
                for sub_text in sub_chunks:
                    enriched = self._enrich_chunk(heading, sub_text)
                    chunks.append(Chunk(
                        chunk_id=f"{file_name}::chunk_{chunk_index}",
                        content=enriched,
                        source_file=source_file,
                        file_name=file_name,
                        document_type=document_type,
                        page_number=page,
                        section_heading=heading,
                        chunk_index=chunk_index,
                        token_count=self._count_tokens(enriched),
                    ))
                    chunk_index += 1

        logger.info(
            f"Chunked {file_name}: {len(chunks)} chunks "
            f"(avg {sum(c.token_count for c in chunks) // max(len(chunks), 1)} tokens)"
        )
        return chunks

    def _split_by_headings(self, markdown: str) -> list[dict]:
        """Split Markdown content by heading boundaries."""
        try:
            from langchain_text_splitters import MarkdownHeaderTextSplitter

            splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=[
                    ("#", "heading_1"),
                    ("##", "heading_2"),
                    ("###", "heading_3"),
                ],
                strip_headers=False,
            )

            splits = splitter.split_text(markdown)
            sections = []

            for split in splits:
                content = split.page_content.strip()
                if not content:
                    continue

                heading = (
                    split.metadata.get("heading_3")
                    or split.metadata.get("heading_2")
                    or split.metadata.get("heading_1")
                    or "Untitled Section"
                )

                page = 1
                if "heading_2" in split.metadata:
                    h2 = split.metadata["heading_2"]
                    if h2.lower().startswith("page "):
                        try:
                            page = int(h2.split()[-1])
                        except ValueError:
                            pass

                sections.append({
                    "heading": heading,
                    "content": content,
                    "page": page,
                })

            if sections:
                return sections
        except ImportError:
            pass

        # Native fallback splitting by Markdown headings
        import re
        sections = []
        pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(markdown))

        if not matches:
            return [{"heading": "Document", "content": markdown.strip(), "page": 1}]

        # Preamble before first heading
        if matches[0].start() > 0:
            preamble = markdown[: matches[0].start()].strip()
            if preamble:
                sections.append({"heading": "Document", "content": preamble, "page": 1})

        for idx, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
            content = markdown[start:end].strip()

            page = 1
            if heading.lower().startswith("page "):
                try:
                    page = int(heading.split()[-1])
                except ValueError:
                    pass

            if content:
                sections.append({"heading": heading, "content": content, "page": page})

        return sections or [{"heading": "Document", "content": markdown.strip(), "page": 1}]

    def _recursive_split(self, text: str) -> list[str]:
        """Split long text recursively by paragraphs and sentences."""
        max_chars = self.max_tokens * 4
        overlap_chars = self.overlap_tokens * 4

        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=max_chars,
                chunk_overlap=overlap_chars,
                separators=["\n\n", "\n", ". ", " ", ""],
                keep_separator=True,
            )

            return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]
        except ImportError:
            # Native fallback splitting by paragraph
            paragraphs = text.split("\n\n")
            chunks = []
            current = ""
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                if len(current) + len(p) + 2 <= max_chars:
                    current = f"{current}\n\n{p}" if current else p
                else:
                    if current:
                        chunks.append(current)
                    current = p
            if current:
                chunks.append(current)
            return chunks or [text.strip()]

    @staticmethod
    def _enrich_chunk(heading: str, content: str) -> str:
        """Prepend section heading to chunk for retrieval context."""
        if heading and heading != "Document" and heading not in content[:200]:
            return f"[Section: {heading}]\n\n{content}"
        return content
