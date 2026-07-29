import pytest

from buy_agent.bootstrap.settings import Settings


def test_settings_read_llm_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUY_AGENT_LLM_MODEL", "test-model")
    monkeypatch.setenv("BUY_AGENT_LLM_API_KEY", "secret-value")
    monkeypatch.setenv("BUY_AGENT_LLM_BASE_URL", "https://example.invalid/v1")
    settings = Settings.from_env()
    assert settings.llm_model == "test-model"
    assert settings.llm_base_url == "https://example.invalid/v1"
    assert "secret-value" not in repr(settings)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"llm_timeout_seconds": 0},
        {"llm_timeout_seconds": 301},
        {"llm_max_retries": 6},
        {"llm_temperature": 3},
    ],
)
def test_settings_reject_invalid_llm_limits(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Settings(**kwargs)  # type: ignore[arg-type]
