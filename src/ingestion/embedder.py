"""Embedder — generates vector embeddings using Gemini models with a fallback strategy."""

import logging
import time
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50
DEFAULT_DELAY_SECONDS = 1.0


class Embedder:
    """Generate embeddings using Gemini embedding-2 model, falling back to text-embedding-004.

    If the primary Gemini model hits a rate limit (429), it will fall back to another
    Gemini model to preserve the 768-dimension consistency in ChromaDB.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-2",
        fallback_model: str = "text-embedding-004",
        batch_size: int = DEFAULT_BATCH_SIZE,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
    ):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key or "dummy-api-key")
        self.model = model
        self.fallback_model_name = fallback_model
        self.batch_size = batch_size
        self.delay_seconds = delay_seconds
        
        self._using_fallback = False

    def embed_document_chunk(
        self, text: str, title: str = "none"
    ) -> list[float]:
        prefixed = f"title: {title} | text: {text}"
        return self._embed_single(prefixed)

    def embed_query(self, query: str) -> list[float]:
        prefixed = f"task: question answering | query: {query}"
        return self._embed_single(prefixed)

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
                # Attempt to embed via Gemini (Primary or Fallback)
                batch_embs = self._embed_batch_gemini(batch_texts)
                all_embeddings.extend(batch_embs)
                
                if i + self.batch_size < len(chunks):
                    logger.debug(f"Embedded {min(i + self.batch_size, len(chunks))}/{len(chunks)} chunks, waiting {self.delay_seconds}s...")
                    time.sleep(self.delay_seconds)
                    
            except Exception as e:
                if not self._using_fallback:
                    logger.warning(f"Primary Gemini batch embedding failed: {e}. Switching to fallback model: {self.fallback_model_name}")
                    self._using_fallback = True
                    # Retry the current batch with the fallback model
                    batch_embs = self._embed_batch_gemini(batch_texts)
                    all_embeddings.extend(batch_embs)
                else:
                    logger.error(f"Fallback Gemini batch embedding failed: {e}")
                    raise

        logger.info(f"Embedded {len(all_embeddings)} chunks total")
        return all_embeddings

    def _embed_single(self, text: str) -> list[float]:
        current_model = self.fallback_model_name if self._using_fallback else self.model
        
        try:
            result = self.client.models.embed_content(
                model=current_model,
                contents=text,
            )
            return result.embeddings[0].values
        except Exception as e:
            if not self._using_fallback:
                logger.warning(f"Primary Gemini single embedding failed: {e}. Switching to fallback model.")
                self._using_fallback = True
                result = self.client.models.embed_content(
                    model=self.fallback_model_name,
                    contents=text,
                )
                return result.embeddings[0].values
            else:
                raise

    def _embed_batch_gemini(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key or self.api_key == "dummy-api-key":
            raise ValueError("GEMINI_API_KEY is not configured.")
            
        content_objects = [
            types.Content(parts=[types.Part.from_text(text=t)]) 
            for t in texts
        ]

        current_model = self.fallback_model_name if self._using_fallback else self.model

        # Use an internal retry logic just for transient errors before doing a full fallback switch
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = self.client.models.embed_content(
                    model=current_model,
                    contents=content_objects,
                )
                return [emb.values for emb in result.embeddings]
            except Exception as e:
                # If we hit a 429 quota error, don't wait 3 times, fail fast so we can trigger the fallback
                if "429" in str(e) and "quota" in str(e).lower() and not self._using_fallback:
                    raise e
                    
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Gemini API error (model: {current_model}, attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise
