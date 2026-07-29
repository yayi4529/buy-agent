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
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_verification_token: str | None = None
    feishu_encrypt_key: str | None = None
    feishu_enabled: bool = False
    feishu_request_timeout_seconds: float = 10.0
    http_host: str = "127.0.0.1"
    http_port: int = 8000
    http_log_level: str = "info"
    feishu_webhook_path: str = "/webhooks/feishu"
    feishu_webhook_max_body_bytes: int = 1_048_576

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
        if not 0 < self.feishu_request_timeout_seconds <= 300:
            raise ValueError("feishu_request_timeout_seconds must be between 0 and 300")
        if not 1 <= self.http_port <= 65535:
            raise ValueError("http_port must be between 1 and 65535")
        if self.http_log_level not in {"critical", "error", "warning", "info", "debug", "trace"}:
            raise ValueError("unsupported http_log_level")
        if not self.feishu_webhook_path.startswith("/"):
            raise ValueError("feishu_webhook_path must start with /")
        if not 1 <= self.feishu_webhook_max_body_bytes <= 10 * 1024 * 1024:
            raise ValueError("feishu_webhook_max_body_bytes must be between 1 and 10485760")

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
            feishu_app_id=os.getenv("BUY_AGENT_FEISHU_APP_ID") or None,
            feishu_app_secret=os.getenv("BUY_AGENT_FEISHU_APP_SECRET") or None,
            feishu_verification_token=os.getenv("BUY_AGENT_FEISHU_VERIFICATION_TOKEN") or None,
            feishu_encrypt_key=os.getenv("BUY_AGENT_FEISHU_ENCRYPT_KEY") or None,
            feishu_enabled=os.getenv("BUY_AGENT_FEISHU_ENABLED", "").lower()
            in {"1", "true", "yes", "on"},
            feishu_request_timeout_seconds=float(
                os.getenv("BUY_AGENT_FEISHU_REQUEST_TIMEOUT_SECONDS", "10")
            ),
            http_host=os.getenv("BUY_AGENT_HTTP_HOST", "127.0.0.1"),
            http_port=int(os.getenv("BUY_AGENT_HTTP_PORT", "8000")),
            http_log_level=os.getenv("BUY_AGENT_HTTP_LOG_LEVEL", "info").lower(),
            feishu_webhook_path=os.getenv("BUY_AGENT_FEISHU_WEBHOOK_PATH", "/webhooks/feishu"),
            feishu_webhook_max_body_bytes=int(
                os.getenv("BUY_AGENT_FEISHU_WEBHOOK_MAX_BODY_BYTES", "1048576")
            ),
        )

    def __repr__(self) -> str:
        values = dict(self.__dict__)
        values["llm_api_key"] = "***" if self.llm_api_key else None
        for name in (
            "feishu_app_secret",
            "feishu_verification_token",
            "feishu_encrypt_key",
        ):
            values[name] = "***" if values[name] else None
        return f"Settings({values!r})"
