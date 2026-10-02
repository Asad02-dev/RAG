"""LLM client — one interface over OpenAI and Gemini for generation, embeddings and file extraction.

The active provider is chosen by ACTIVE_MODEL_PROVIDER in settings (default: openai).
"""

import base64
import logging
import mimetypes
from pathlib import Path

from configs.constants import ModelProvider

logger = logging.getLogger(__name__)

PLACEHOLDER_KEY = "dummy-api-key"


class LLMClient:
    """Thin wrapper so the rest of the code doesn't depend on a specific provider SDK."""

    def __init__(self, provider: ModelProvider | str, api_key: str):
        self.provider = ModelProvider(provider)
        self.api_key = api_key
        self._client = None

    @property
    def key_env_name(self) -> str:
        return "OPENAI_API_KEY" if self.provider == ModelProvider.OPENAI else "GEMINI_API_KEY"

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key) and self.api_key != PLACEHOLDER_KEY

    @property
    def client(self):
        """Provider SDK client, created on first use."""
        if self._client is None:
            if not self.has_api_key:
                raise ValueError(f"{self.key_env_name} is not configured.")
            if self.provider == ModelProvider.OPENAI:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            else:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        json_mode: bool = False,
        thinking_budget: int | None = None,
    ) -> str:
        """Generate text from a single user prompt."""
        if self.provider == ModelProvider.OPENAI:
            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
            if max_output_tokens:
                kwargs["max_completion_tokens"] = max_output_tokens
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""

        from google.genai import types

        config_kwargs = {"temperature": temperature}
        if max_output_tokens:
            config_kwargs["max_output_tokens"] = max_output_tokens
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        if thinking_budget and "gemini-3" in model:
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return response.text or ""

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning one vector per text."""
        if self.provider == ModelProvider.OPENAI:
            response = self.client.embeddings.create(model=model, input=texts)
            return [item.embedding for item in response.data]

        from google.genai import types

        contents = [types.Content(parts=[types.Part.from_text(text=t)]) for t in texts]
        result = self.client.models.embed_content(model=model, contents=contents)
        return [emb.values for emb in result.embeddings]

    def extract_from_file(self, model: str, path: str | Path, prompt: str) -> str:
        """Run a vision/document model over a PDF or image file and return its text output."""
        path = Path(path)
        is_pdf = path.suffix.lower() == ".pdf"

        if self.provider == ModelProvider.OPENAI:
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            if is_pdf:
                file_part = {
                    "type": "file",
                    "file": {"filename": path.name, "file_data": f"data:application/pdf;base64,{data}"},
                }
            else:
                mime = mimetypes.guess_type(path.name)[0] or "image/png"
                file_part = {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [file_part, {"type": "text", "text": prompt}]}],
            )
            return response.choices[0].message.content or ""

        if is_pdf:
            uploaded_file = self.client.files.upload(file=str(path))
            try:
                response = self.client.models.generate_content(model=model, contents=[uploaded_file, prompt])
            finally:
                try:
                    self.client.files.delete(name=uploaded_file.name)
                except Exception as e:
                    logger.debug(f"Could not delete file {uploaded_file.name} from Gemini API: {e}")
            return response.text or ""

        from PIL import Image

        response = self.client.models.generate_content(model=model, contents=[Image.open(str(path)), prompt])
        return response.text or ""


def get_llm_client(settings=None) -> LLMClient:
    """Build an LLMClient for the provider configured in settings."""
    if settings is None:
        from configs.settings import get_settings
        settings = get_settings()
    return LLMClient(settings.active_model_provider, settings.get_api_key)


def candidate_models(primary: str, fallbacks: list[str]) -> list[str]:
    """Primary model followed by up to 3 distinct fallbacks."""
    models = [primary]
    for model in fallbacks[:3]:
        if model and model not in models:
            models.append(model)
    return models
