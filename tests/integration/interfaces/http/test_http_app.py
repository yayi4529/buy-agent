from collections.abc import Mapping
from typing import Any

from fastapi.testclient import TestClient

from buy_agent.adapters.channels.feishu.client import FakeFeishuClient
from buy_agent.bootstrap.settings import Settings
from buy_agent.interfaces.http.app import create_app
from buy_agent.interfaces.http.application_container import (
    ApplicationOverrides,
    build_application,
)
from buy_agent.interfaces.http.models import (
    FeishuSignatureError,
    FeishuWebhookResponse,
)


class SecurityStub:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        immediate: FeishuWebhookResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.immediate = immediate
        self.error = error
        self.calls = 0

    def decode_and_validate(
        self, *, headers: Mapping[str, str], body: bytes
    ) -> tuple[dict[str, Any] | None, FeishuWebhookResponse | None]:
        del headers, body
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.payload, self.immediate


def configured_settings(**changes: object) -> Settings:
    values: dict[str, object] = {
        "feishu_enabled": True,
        "feishu_app_id": "app-id",
        "feishu_app_secret": "app-secret",
        "feishu_verification_token": "verification-token",
        "feishu_encrypt_key": "encrypt-key",
    }
    values.update(changes)
    return Settings(**values)  # type: ignore[arg-type]


def test_health_endpoints_do_not_require_network() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        assert client.get("/health/ready").json() == {
            "status": "ready",
            "feishu": "disabled",
        }


def test_ready_reports_missing_enabled_configuration() -> None:
    app = create_app(Settings(feishu_enabled=True))
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["feishu"] == "configuration_missing"


def test_challenge_is_returned_without_creating_session() -> None:
    security = SecurityStub(immediate=FeishuWebhookResponse(200, {"challenge": "exact-value"}))
    settings = configured_settings()
    container = build_application(
        settings, overrides=ApplicationOverrides(security_adapter=security)
    )
    app = create_app(container=container)
    with TestClient(app) as client:
        response = client.post(
            settings.feishu_webhook_path,
            content=b'{"challenge":"exact-value"}',
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 200
    assert response.json() == {"challenge": "exact-value"}
    assert security.calls == 1
    assert container.conversation_store._conversations == {}  # type: ignore[attr-defined]


def test_message_event_reaches_existing_handler() -> None:
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": "event-1",
            "event_type": "im.message.receive_v1",
            "tenant_key": "tenant",
        },
        "event": {
            "sender": {"sender_id": {"open_id": "requester"}},
            "message": {
                "message_id": "message-1",
                "chat_id": "chat-1",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"我要采购服务器"}',
            },
        },
    }
    security = SecurityStub(payload=payload)
    feishu = FakeFeishuClient()
    settings = configured_settings()
    container = build_application(
        settings,
        overrides=ApplicationOverrides(
            security_adapter=security,
            feishu_client=feishu,
        ),
    )
    with TestClient(create_app(container=container)) as client:
        response = client.post(
            settings.feishu_webhook_path,
            json={"event": "validated-by-stub"},
        )
    assert response.status_code == 200
    assert feishu.reply_text_calls


def test_invalid_content_and_body_are_rejected_before_processor() -> None:
    security = SecurityStub()
    settings = configured_settings(feishu_webhook_max_body_bytes=4)
    container = build_application(
        settings, overrides=ApplicationOverrides(security_adapter=security)
    )
    with TestClient(create_app(container=container), raise_server_exceptions=False) as client:
        invalid_type = client.post(settings.feishu_webhook_path, content=b"{}")
        empty = client.post(
            settings.feishu_webhook_path,
            content=b"",
            headers={"content-type": "application/json"},
        )
        too_large = client.post(settings.feishu_webhook_path, json={"large": True})
    assert invalid_type.status_code == 415
    assert empty.status_code == 400
    assert too_large.status_code == 413
    assert security.calls == 0


def test_signature_failure_is_401_and_does_not_call_handler() -> None:
    security = SecurityStub(error=FeishuSignatureError("bad signature"))
    settings = configured_settings()
    container = build_application(
        settings, overrides=ApplicationOverrides(security_adapter=security)
    )
    with TestClient(create_app(container=container), raise_server_exceptions=False) as client:
        response = client.post(settings.feishu_webhook_path, json={"event": "invalid"})
    assert response.status_code == 401
    assert response.json()["code"] == "SIGNATURE_INVALID"
    assert container.conversation_store._conversations == {}  # type: ignore[attr-defined]


def test_same_application_reuses_container_across_requests() -> None:
    settings = configured_settings()
    security = SecurityStub(immediate=FeishuWebhookResponse())
    container = build_application(
        settings, overrides=ApplicationOverrides(security_adapter=security)
    )
    with TestClient(create_app(container=container)) as client:
        first = client.post(settings.feishu_webhook_path, json={})
        second = client.post(settings.feishu_webhook_path, json={})
    assert first.status_code == second.status_code == 200
    assert security.calls == 2
