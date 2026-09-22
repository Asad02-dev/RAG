"""Query engine — orchestrates retrieval and LLM generation for answering questions."""

import logging
import time
from dataclasses import dataclass

from google import genai
from google.genai import types

from src.retrieval.search_client import SearchClient
from src.retrieval.prompts import SYSTEM_PROMPT, build_prompt

logger = logging.getLogger(__name__)


@dataclass
class QueryResponse:
    """The result of a RAG query."""

    answer: str
    sources: list[dict]
    query: str
    model: str
    chunks_retrieved: int


class QueryEngine:
    """RAG query engine: embed query → search → generate grounded answer.

    Uses Gemini for both embedding (via SearchClient) and generation.
    """

    def __init__(
        self,
        search_client: SearchClient,
        api_key: str,
        llm_model: str = "gemma-4-26b-a4b-it",
        fallback_models: list[str] | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
        top_k: int = 5,
    ):
        self.search_client = search_client
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key or "dummy-api-key")
        self.llm_model = llm_model
        self.fallback_models = (
            fallback_models
            if fallback_models is not None
            else ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.6-flash"]
        )
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.top_k = top_k

    def query(self, question: str) -> QueryResponse:
        """Answer a question using retrieved document context.

        Steps:
            1. Search for relevant chunks via SearchClient
            2. Build augmented prompt with context
            3. Generate answer with Gemini/Gemma LLM (with up to 3 fallback models)
            4. Return answer with source citations
        """
        if not question.strip():
            return QueryResponse(
                answer="Please provide a question.",
                sources=[],
                query=question,
                model=self.llm_model,
                chunks_retrieved=0,
            )

        if not self.api_key or self.api_key == "dummy-api-key":
            return QueryResponse(
                answer="⚠️ GEMINI_API_KEY is not set. Please add your Gemini API key to `.env` to enable AI query responses.",
                sources=[],
                query=question,
                model=self.llm_model,
                chunks_retrieved=0,
            )

        # Step 1: Retrieve relevant chunks
        search_results = self.search_client.search(
            query=question,
            top_k=self.top_k,
        )

        if not search_results:
            return QueryResponse(
                answer="I don't have any documents indexed yet. "
                       "Please ingest some documents first using the /api/ingest endpoint or the CLI.",
                sources=[],
                query=question,
                model=self.llm_model,
                chunks_retrieved=0,
            )

        # Step 2: Build prompt with context and system instructions
        prompt = build_prompt(question, search_results)
        full_prompt = f"{SYSTEM_PROMPT}\n\n---\n\n{prompt}"

        # Step 3: Generate answer with LLM (with up to 3 fallback models)
        models_to_try = [self.llm_model]
        for fallback_model in self.fallback_models[:3]:
            if fallback_model and fallback_model not in models_to_try:
                models_to_try.append(fallback_model)

        answer = ""
        active_model = self.llm_model
        last_error = None

        for model_candidate in models_to_try:
            logger.info(
                f"Generating answer for: '{question[:80]}...' "
                f"with {len(search_results)} chunks using candidate model: '{model_candidate}'"
            )
            # Try model; retry once only on transient 503 error
            for attempt in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=model_candidate,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=self.temperature,
                            max_output_tokens=self.max_output_tokens,
                        ),
                    )
                    answer = response.text or "No response generated."
                    active_model = model_candidate
                    logger.info(f"Answer successfully generated using '{model_candidate}'")
                    break
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    # On 404 (model not found/deprecated) or 429 (quota exhausted), immediately fail over
                    if "404" in err_str or "NOT_FOUND" in err_str:
                        logger.warning(
                            f"Model '{model_candidate}' not found / unavailable (404). Trying next fallback model..."
                        )
                        break
                    elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        logger.warning(
                            f"Model '{model_candidate}' quota exhausted (429). Trying next fallback model..."
                        )
                        break
                    elif "503" in err_str or "UNAVAILABLE" in err_str:
                        if attempt == 0:
                            logger.warning(
                                f"Model '{model_candidate}' temporarily unavailable (503). Retrying once in 1s..."
                            )
                            time.sleep(1)
                        else:
                            logger.warning(
                                f"Model '{model_candidate}' still unavailable (503). Trying next fallback model..."
                            )
                            break
                    else:
                        logger.warning(
                            f"Model '{model_candidate}' failed with error: {e}. Trying next fallback model..."
                        )
                        break

            if answer:
                break

        if not answer:
            logger.error(
                f"All candidate models {models_to_try} failed to generate an answer. Last error: {last_error}",
                exc_info=True,
            )
            answer = f"Error generating answer: {last_error}"

        # Step 4: Extract source citations
        sources = [
            {
                "file_name": r["metadata"].get("file_name", "unknown"),
                "page_number": r["metadata"].get("page_number", 0),
                "section_heading": r["metadata"].get("section_heading", ""),
                "distance": r.get("distance", 0),
            }
            for r in search_results
        ]

        # Deduplicate sources by file_name + page_number
        seen = set()
        unique_sources = []
        for s in sources:
            key = (s["file_name"], s["page_number"])
            if key not in seen:
                seen.add(key)
                unique_sources.append(s)

        return QueryResponse(
            answer=answer,
            sources=unique_sources,
            query=question,
            model=active_model,
            chunks_retrieved=len(search_results),
        )

