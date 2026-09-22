"""Centralized configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application settings, loaded from .env file or environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Gemini API ──
    gemini_api_key: str = ""
    gemini_embed_model: str = "gemini-embedding-2"
    gemini_llm_model: str = "gemma-4-26b-a4b-it"
    gemini_llm_model_complex: str = "gemini-3.1-pro-preview"
    gemini_llm_fallback_models: str = "gemini-3-flash-preview,gemini-3.5-flash,gemini-3.6-flash"

    @property
    def fallback_models_list(self) -> list[str]:
        """Return up to 3 fallback models as a list of strings."""
        if not self.gemini_llm_fallback_models:
            return []
        models = [m.strip() for m in self.gemini_llm_fallback_models.split(",") if m.strip()]
        return models[:3]

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
