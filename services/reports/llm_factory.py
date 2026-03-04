import os

from core.abstractions.illm_client import ILLMClient
from services.reports.deepseek_client import DeepSeekClient
from services.reports.openai_client import OpenAIClient


def get_llm_client(provider: str | None = None) -> ILLMClient:
    selected_provider = (provider or os.getenv("LLM_PROVIDER", "deepseek")).strip().lower()

    if selected_provider == "openai":
        return OpenAIClient()

    if selected_provider == "deepseek":
        return DeepSeekClient()

    raise ValueError(f"Unsupported LLM provider: {selected_provider}. Use 'deepseek' or 'openai'.")
