"""Centralized configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from configs.constants import ModelProvider


class Settings(BaseSettings):
    """All application settings, loaded from .env file or environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Active Model Provider ("openai" or "gemini") ──
    active_model_provider: ModelProvider = ModelProvider.OPENAI

    # ── Gemini API ──
    gemini_api_key: str = ""
    gemini_embed_model: str = "gemini-embedding-2"
    gemini_llm_model: str = "gemma-4-26b-a4b-it" # Used for querying
    gemini_extraction_model: str = "gemma-4-12b-a4b-it" # Faster parsing model
    gemini_llm_model_complex: str = "gemma-4-26b-a4b-it"
    gemini_llm_fallback_models: str = "gemma-4-12b-a4b-it,gemma-4-26b-a4b-it"

    # ── OpenAI API ──
    openai_api_key: str = ""
    openai_embed_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o-mini"
    openai_extraction_model: str = "gpt-4o-mini"
    openai_llm_model_complex: str = "gpt-4o-mini"
    openai_llm_fallback_models: str = "gpt-4o-mini"

    # ── TypeSafe API ──
    typesafe_api_key: str = ""

    @property
    def fallback_models_list(self) -> list[str]:
        """Return up to 3 fallback models as a list of strings depending on active provider."""
        fallback_models_str = (
            self.openai_llm_fallback_models 
            if self.active_model_provider == ModelProvider.OPENAI 
            else self.gemini_llm_fallback_models
        )
        if not fallback_models_str:
            return []
        models = [m.strip() for m in fallback_models_str.split(",") if m.strip()]
        return models[:3]

    @property
    def get_llm_model(self) -> str:
        if self.active_model_provider == ModelProvider.OPENAI:
            return self.openai_llm_model
        return self.gemini_llm_model

    @property
    def get_embed_model(self) -> str:
        if self.active_model_provider == ModelProvider.OPENAI:
            return self.openai_embed_model
        return self.gemini_embed_model

    @property
    def get_extraction_model(self) -> str:
        if self.active_model_provider == ModelProvider.OPENAI:
            return self.openai_extraction_model
        return self.gemini_extraction_model

    @property
    def get_api_key(self) -> str:
        if self.active_model_provider == ModelProvider.OPENAI:
            return self.openai_api_key
        return self.gemini_api_key


    # ── Paths ──
    documents_dir: str = "./data/documents"
    chroma_db_dir: str = "./data/chroma_db"

    # ── Chunking ──
    max_chunk_tokens: int = 500
    chunk_overlap_tokens: int = 50

    # ── Retrieval ──
    top_k_results: int = 5

    # ── Generation ──
    temperature: float = 0.2
    max_output_tokens: int = 2048
    thinking_budget: int = 1024

    @property
    def documents_path(self) -> Path:
        """Return documents directory as a Path object."""
        return Path(self.documents_dir).resolve()

    @property
    def chroma_db_path(self) -> Path:
        """Return ChromaDB directory as a Path object."""
        return Path(self.chroma_db_dir).resolve()


def get_settings() -> Settings:
    """Create and return a Settings instance (cached via lru_cache if needed)."""
    return Settings()
