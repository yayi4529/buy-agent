import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    agent_max_rounds: int = 8
    agent_max_tool_calls: int = 4
    recent_message_limit: int = 20
    default_current_action: str = "CREATE_REQUEST"
    llm_provider: str = "openai-compatible"
    llm_model: str = ""
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    llm_temperature: float = 0.0

    def __post_init__(self) -> None:
        if self.agent_max_rounds < 1:
            raise ValueError("agent_max_rounds must be at least 1")
        if self.agent_max_tool_calls < 0:
            raise ValueError("agent_max_tool_calls must not be negative")
        if self.recent_message_limit < 1:
            raise ValueError("recent_message_limit must be at least 1")
        if self.llm_timeout_seconds <= 0 or self.llm_timeout_seconds > 300:
            raise ValueError("llm_timeout_seconds must be between 0 and 300")
        if self.llm_max_retries < 0 or self.llm_max_retries > 5:
            raise ValueError("llm_max_retries must be between 0 and 5")
        if not 0 <= self.llm_temperature <= 2:
            raise ValueError("llm_temperature must be between 0 and 2")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_provider=os.getenv("BUY_AGENT_LLM_PROVIDER", "openai-compatible"),
            llm_model=os.getenv("BUY_AGENT_LLM_MODEL", ""),
            llm_api_key=os.getenv("BUY_AGENT_LLM_API_KEY"),
            llm_base_url=os.getenv("BUY_AGENT_LLM_BASE_URL") or None,
            llm_timeout_seconds=float(os.getenv("BUY_AGENT_LLM_TIMEOUT_SECONDS", "30")),
            llm_max_retries=int(os.getenv("BUY_AGENT_LLM_MAX_RETRIES", "2")),
            llm_temperature=float(os.getenv("BUY_AGENT_LLM_TEMPERATURE", "0")),
        )

    def __repr__(self) -> str:
        values = dict(self.__dict__)
        values["llm_api_key"] = "***" if self.llm_api_key else None
        return f"Settings({values!r})"
