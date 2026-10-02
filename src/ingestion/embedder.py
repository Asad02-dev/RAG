"""Embedder — generates vector embeddings via the configured LLM provider (OpenAI or Gemini)."""

import logging
import time

from src.llm_client import LLMClient

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50
DEFAULT_DELAY_SECONDS = 1.0
RATE_LIMIT_RETRIES = 6
RATE_LIMIT_WAIT_SECONDS = 30


def _is_rate_limit(e: Exception) -> bool:
    err = str(e)
    # OpenAI reports an unpaid/empty account as a 429 too; waiting won't fix that.
    if "insufficient_quota" in err:
        return False
    return "429" in err or "RESOURCE_EXHAUSTED" in err


class Embedder:
    """Generate embeddings with a single model.

    On a rate limit (429) it waits and retries the same model, so every vector in
    ChromaDB keeps the same dimensions.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "text-embedding-3-small",
        batch_size: int = DEFAULT_BATCH_SIZE,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
    ):
        self.llm = llm_client
        self.model = model
        self.batch_size = batch_size
        self.delay_seconds = delay_seconds

    def embed_document_chunk(
        self, text: str, title: str = "none"
    ) -> list[float]:
        prefixed = f"title: {title} | text: {text}"
        return self._embed_batch([prefixed])[0]

    def embed_query(self, query: str) -> list[float]:
        prefixed = f"task: question answering | query: {query}"
        return self._embed_batch([prefixed])[0]

    def embed_document_chunks_batch(
        self, chunks: list[dict[str, str]]
    ) -> list[list[float]]:
        all_embeddings: list[list[float]] = []

        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]

            batch_texts = []
            for chunk in batch:
                title = chunk.get("title", "none")
                text = chunk["text"]
                prefixed = f"title: {title} | text: {text}"
                batch_texts.append(prefixed)

            try:
                batch_embs = self._embed_batch(batch_texts)
            except Exception as e:
                logger.error(f"Batch embedding failed (model: {self.model}): {e}")
                raise
            all_embeddings.extend(batch_embs)

            if i + self.batch_size < len(chunks):
                logger.debug(f"Embedded {min(i + self.batch_size, len(chunks))}/{len(chunks)} chunks, waiting {self.delay_seconds}s...")
                time.sleep(self.delay_seconds)

        logger.info(f"Embedded {len(all_embeddings)} chunks total")
        return all_embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not self.llm.has_api_key:
            raise ValueError(f"{self.llm.key_env_name} is not configured.")

        # Retry transient errors with exponential backoff; on rate limits wait longer
        # and retry the same model so embedding dimensions stay consistent.
        max_retries = 3
        rate_limit_hits = 0
        attempt = 0
        while True:
            try:
                return self.llm.embed(self.model, texts)
            except Exception as e:
                if _is_rate_limit(e):
                    rate_limit_hits += 1
                    if rate_limit_hits >= RATE_LIMIT_RETRIES:
                        raise
                    logger.warning(f"Rate limited (model: {self.model}, {rate_limit_hits}/{RATE_LIMIT_RETRIES}). Waiting {RATE_LIMIT_WAIT_SECONDS}s before retry...")
                    time.sleep(RATE_LIMIT_WAIT_SECONDS)
                    continue

                attempt += 1
                if attempt < max_retries and "insufficient_quota" not in str(e):
                    wait = 2 ** attempt
                    logger.warning(f"Embedding API error (model: {self.model}, attempt {attempt}/{max_retries}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise
