"""Embedder — generates vector embeddings via the Gemini API."""

import logging
import time
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Rate limiting constants for Gemini free tier
DEFAULT_BATCH_SIZE = 50
DEFAULT_DELAY_SECONDS = 1.0


class Embedder:
    """Generate embeddings using Gemini embedding-2 model.

    Uses task-type prefixing as recommended by Gemini docs for optimal
    retrieval quality in asymmetric search (queries ≠ documents).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-2",
        batch_size: int = DEFAULT_BATCH_SIZE,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
    ):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key or "dummy-api-key")
        self.model = model
        self.batch_size = batch_size
        self.delay_seconds = delay_seconds

    def embed_document_chunk(
        self, text: str, title: str = "none"
    ) -> list[float]:
        """Embed a single document chunk with document task prefix.

        Per Gemini docs, document embeddings use:
            title: {title} | text: {content}
        """
        prefixed = f"title: {title} | text: {text}"
        return self._embed_single(prefixed)

    def embed_query(self, query: str) -> list[float]:
        """Embed a user query with question-answering task prefix.

        Per Gemini docs, query embeddings use:
            task: question answering | query: {content}
        """
        prefixed = f"task: question answering | query: {query}"
        return self._embed_single(prefixed)

    def embed_document_chunks_batch(
        self, chunks: list[dict[str, str]]
    ) -> list[list[float]]:
        """Embed multiple document chunks in rate-limited batches.

        Args:
            chunks: List of dicts with 'text' and optional 'title' keys.

        Returns:
            List of embedding vectors (same order as input).
        """
        all_embeddings: list[list[float]] = []

        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]

            batch_texts = []
            for chunk in batch:
                title = chunk.get("title", "none")
                text = chunk["text"]
                prefixed = f"title: {title} | text: {text}"
                batch_texts.append(prefixed)

            batch_embs = self._embed_batch(batch_texts)
            all_embeddings.extend(batch_embs)

            # Rate limiting between batches
            if i + self.batch_size < len(chunks):
                logger.debug(
                    f"Embedded {min(i + self.batch_size, len(chunks))}/{len(chunks)} chunks, "
                    f"waiting {self.delay_seconds}s..."
                )
                time.sleep(self.delay_seconds)

        logger.info(f"Embedded {len(all_embeddings)} chunks total")
        return all_embeddings

    def _embed_single(self, text: str, max_retries: int = 6) -> list[float]:
        """Embed a single text string with retry logic."""
        if not self.api_key or self.api_key == "dummy-api-key":
            raise ValueError(
                "GEMINI_API_KEY is not configured. Please set your Gemini API key in the .env file."
            )

        for attempt in range(max_retries):
            try:
                result = self.client.models.embed_content(
                    model=self.model,
                    contents=text,
                )
                return result.embeddings[0].values
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        f"Embedding failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    logger.error(f"Embedding failed after {max_retries} attempts: {e}")
                    raise

    def _embed_batch(self, texts: list[str], max_retries: int = 6) -> list[list[float]]:
        """Embed a list of text strings with retry logic."""
        if not self.api_key or self.api_key == "dummy-api-key":
            raise ValueError(
                "GEMINI_API_KEY is not configured. Please set your Gemini API key in the .env file."
            )
            
        content_objects = [
            types.Content(parts=[types.Part.from_text(text=t)]) 
            for t in texts
        ]

        for attempt in range(max_retries):
            try:
                result = self.client.models.embed_content(
                    model=self.model,
                    contents=content_objects,
                )
                return [emb.values for emb in result.embeddings]
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        f"Embedding failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    logger.error(f"Embedding failed after {max_retries} attempts: {e}")
                    raise
