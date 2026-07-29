from buy_agent.adapters.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient
from buy_agent.bootstrap.settings import Settings
from buy_agent.ports.llm_client import LLMClient


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider != "openai-compatible":
        raise ValueError(f"unsupported LLM provider: {settings.llm_provider}")
    return OpenAICompatibleLLMClient(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        temperature=settings.llm_temperature,
    )
