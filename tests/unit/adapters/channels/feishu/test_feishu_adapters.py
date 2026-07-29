from unittest.mock import AsyncMock

import pytest

from buy_agent.adapters.channels.feishu.action_adapter import FeishuActionAdapter
from buy_agent.adapters.channels.feishu.action_result_renderer import (
    FeishuActionResultRenderer,
)
from buy_agent.adapters.channels.feishu.client import FakeFeishuClient, FeishuChannelClient
from buy_agent.adapters.channels.feishu.errors import (
    ChannelEventFormatError,
    ChannelPermissionError,
)
from buy_agent.adapters.channels.feishu.event_adapter import FeishuEventAdapter
from buy_agent.adapters.channels.feishu.handlers import (
    IMAGE_MESSAGE,
    FeishuMessageHandler,
)
from buy_agent.adapters.channels.feishu.response_renderer import FeishuResponseRenderer
from buy_agent.application.session_service import build_session_key
from buy_agent.bootstrap.settings import Settings
from buy_agent.domain.action import ActionResult, ActionResultStatus
from buy_agent.domain.agent import AgentResponse
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.domain.interaction import (
    InteractionAction,
    InteractionField,
    InteractionView,
    SelectionGroup,
    SelectionOption,
)


def message_event(
    *, message_type: str = "text", chat_type: str = "p2p", content: str = '{"text":"采购"}'
) -> dict[str, object]:
    return {
        "header": {"event_id": "evt-1", "tenant_key": "tenant-1", "create_time": "123"},
        "event": {
            "sender": {"sender_id": {"open_id": "requester"}},
            "message": {
                "message_id": "msg-1",
                "chat_id": "chat-1",
                "chat_type": chat_type,
                "message_type": message_type,
                "content": content,
                "create_time": "456",
            },
        },
    }


def callback(value: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "header": {"event_id": "callback-1", "tenant_key": "tenant-1"},
        "event": {
            "operator": {"operator_id": {"open_id": "requester"}},
            "context": {"open_message_id": "card-1"},
            "action": {
                "value": value
                or {
                    "action": "SUBMIT_REQUEST",
                    "action_token": "token-1",
                    "conversation_id": "1",
                    "expected_state_version": "2",
                }
            },
        },
    }


def test_settings_read_and_mask_feishu_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUY_AGENT_FEISHU_APP_ID", "app")
    monkeypatch.setenv("BUY_AGENT_FEISHU_APP_SECRET", "top-secret")
    monkeypatch.setenv("BUY_AGENT_FEISHU_VERIFICATION_TOKEN", "verify")
    monkeypatch.setenv("BUY_AGENT_FEISHU_ENCRYPT_KEY", "encrypt")
    settings = Settings.from_env()
    assert settings.feishu_app_id == "app"
    assert "top-secret" not in repr(settings)
    assert "verify" not in repr(settings)
    assert "'feishu_encrypt_key': 'encrypt'" not in repr(settings)


def test_settings_timeout_and_real_client_config_validation() -> None:
    with pytest.raises(ValueError):
        Settings(feishu_request_timeout_seconds=0)
    with pytest.raises(ValueError, match="app id"):
        FeishuChannelClient(Settings())
    FakeFeishuClient()


def test_event_adapter_maps_identity_and_keeps_raw_payload_empty() -> None:
    parsed = FeishuEventAdapter().parse(message_event())
    event = parsed.inbound_event
    assert event is not None
    assert (event.event_id, event.message_id, event.conversation_id) == (
        "evt-1",
        "msg-1",
        "chat-1",
    )
    assert event.identity.external_tenant_id == "tenant-1"
    assert event.identity.external_user_id == "requester"
    assert "chat-1" not in build_session_key(event.identity)
    assert event.raw_payload == {}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"event": {"message": {}}}, "sender"),
        ({"header": {"event_id": "evt-1"}}, "tenant_key"),
    ],
)
def test_event_adapter_rejects_missing_fields(change: dict[str, object], message: str) -> None:
    raw = message_event()
    raw.update(change)
    with pytest.raises(ChannelEventFormatError, match=message):
        FeishuEventAdapter().parse(raw)


def test_event_adapter_rejects_empty_text_and_recognizes_image() -> None:
    with pytest.raises(ChannelEventFormatError, match="empty"):
        FeishuEventAdapter().parse(message_event(content='{"text":"  "}'))
    parsed = FeishuEventAdapter().parse(message_event(message_type="image", content="{}"))
    assert parsed.inbound_event is None
    assert parsed.message_kind == "image"


def confirmation_view(*, multiple: bool = False) -> InteractionView:
    groups = (
        (
            SelectionGroup(
                "reviewer_employee_id",
                "楼长",
                (SelectionOption("101", "张楼长"), SelectionOption("102", "李楼长")),
            ),
        )
        if multiple
        else ()
    )
    return InteractionView(
        "request_submission_confirmation",
        "确认采购申请",
        (
            InteractionField("所属楼宇", "一号楼"),
            InteractionField("设备名称", "服务器"),
            InteractionField("备注", ""),
        ),
        groups,
        (
            InteractionAction(
                "submit_request",
                "确认提交",
                {
                    "action_token": "token-1",
                    "conversation_id": 1,
                    "expected_state_version": 2,
                },
            ),
        ),
        "请确认",
    )


@pytest.mark.parametrize("multiple", [False, True])
def test_response_renderer_uses_minimal_payload(multiple: bool) -> None:
    rendered = FeishuResponseRenderer().render_interaction(confirmation_view(multiple=multiple))
    text = str(rendered.payload)
    assert "采购申请确认" in text
    assert "token-1" in text
    assert "conversation_id" in text
    assert "expected_state_version" in text
    for forbidden in ("roles", "data_scopes", "applicant_employee_id", "collected_data"):
        assert forbidden not in text
    assert ("reviewer_employee_id" in text) is multiple


def test_action_adapter_resolves_only_action_data() -> None:
    adapter = FeishuActionAdapter()
    parsed = adapter.parse(callback())
    principal = CurrentPrincipal(1, "requester", frozenset({"REQUESTER"}), (), (), "ACTIVE")
    command = adapter.to_command(parsed, principal)
    assert command.principal is principal
    assert command.payload == {}


@pytest.mark.parametrize(
    "field",
    ["action_token", "conversation_id", "expected_state_version"],
)
def test_action_adapter_rejects_missing_required_value(field: str) -> None:
    value = callback()["event"]["action"]["value"]  # type: ignore[index]
    assert isinstance(value, dict)
    value.pop(field)
    with pytest.raises(ChannelEventFormatError):
        FeishuActionAdapter().parse(callback(value))


@pytest.mark.parametrize(
    "status",
    [
        ActionResultStatus.SUCCESS,
        ActionResultStatus.IN_PROGRESS,
        ActionResultStatus.VERSION_CONFLICT,
        ActionResultStatus.PERMISSION_DENIED,
        ActionResultStatus.BUSINESS_ERROR,
        ActionResultStatus.TECHNICAL_ERROR,
    ],
)
def test_action_result_renderer_has_no_action_token_or_button(
    status: ActionResultStatus,
) -> None:
    result = ActionResult(status, "SAFE-CODE", "message", interaction=confirmation_view())
    text = str(FeishuActionResultRenderer().render(result).payload)
    assert "token-1" not in text
    assert "'tag': 'button'" not in text


async def test_fake_client_records_and_simulates_failure() -> None:
    client = FakeFeishuClient()
    await client.reply_text(external_message_id="msg", text="hello")
    rendered = FeishuResponseRenderer().render_interaction(confirmation_view())
    await client.reply_interaction(external_message_id="msg", interaction=rendered)
    await client.update_interaction(external_interaction_id="card", interaction=rendered)
    assert client.last_text == "hello"
    assert client.last_interaction == rendered
    client.failure = ChannelPermissionError("denied")
    with pytest.raises(ChannelPermissionError):
        await client.reply_text(external_message_id="msg", text="again")


async def test_image_handler_never_calls_orchestrator() -> None:
    orchestrator = AsyncMock()
    client = FakeFeishuClient()
    handler = FeishuMessageHandler(
        event_adapter=FeishuEventAdapter(),
        orchestrator=orchestrator,
        renderer=FeishuResponseRenderer(),
        client=client,  # type: ignore[arg-type]
    )
    result = await handler.handle(message_event(message_type="image", content="{}"))
    assert result.code == "IMAGE_UNSUPPORTED"
    assert client.last_text == IMAGE_MESSAGE
    orchestrator.handle.assert_not_called()


async def test_text_handler_renders_orchestrator_response_once() -> None:
    orchestrator = AsyncMock()
    orchestrator.handle.return_value = AgentResponse("下一字段")
    client = FakeFeishuClient()
    handler = FeishuMessageHandler(
        event_adapter=FeishuEventAdapter(),
        orchestrator=orchestrator,
        renderer=FeishuResponseRenderer(),
        client=client,  # type: ignore[arg-type]
    )
    result = await handler.handle(message_event())
    assert result.code == "OK"
    orchestrator.handle.assert_awaited_once()
    assert client.reply_text_calls == [("msg-1", "下一字段")]
