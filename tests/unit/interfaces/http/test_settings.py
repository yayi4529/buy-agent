import pytest

from buy_agent.bootstrap.settings import Settings


def test_http_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUY_AGENT_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("BUY_AGENT_HTTP_PORT", "9001")
    monkeypatch.setenv("BUY_AGENT_HTTP_LOG_LEVEL", "debug")
    monkeypatch.setenv("BUY_AGENT_FEISHU_WEBHOOK_PATH", "/hooks/lark")
    monkeypatch.setenv("BUY_AGENT_FEISHU_WEBHOOK_MAX_BODY_BYTES", "2048")

    settings = Settings.from_env()

    assert settings.http_host == "0.0.0.0"
    assert settings.http_port == 9001
    assert settings.http_log_level == "debug"
    assert settings.feishu_webhook_path == "/hooks/lark"
    assert settings.feishu_webhook_max_body_bytes == 2048


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("http_port", 0),
        ("http_port", 65536),
        ("feishu_webhook_path", "hooks"),
        ("feishu_webhook_max_body_bytes", 0),
        ("feishu_webhook_max_body_bytes", 10 * 1024 * 1024 + 1),
    ),
)
def test_http_settings_reject_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        Settings(**{field: value})  # type: ignore[arg-type]


def test_settings_repr_redacts_webhook_secrets() -> None:
    rendered = repr(
        Settings(
            feishu_app_secret="secret",
            feishu_verification_token="token",
            feishu_encrypt_key="key",
        )
    )
    assert "'secret'" not in rendered
    assert "'token'" not in rendered
    assert "'key'" not in rendered
