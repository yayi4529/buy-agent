import logging

import pytest

from buy_agent.adapters.agent.fake_procurement_agent import FakeProcurementAgent
from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway
from buy_agent.adapters.channels.fake_channel import FakeChannel
from buy_agent.adapters.persistence.local_lock_manager import LocalLockManager
from buy_agent.adapters.persistence.memory_event_store import MemoryEventStore
from buy_agent.adapters.persistence.memory_message_store import MemoryMessageStore
from buy_agent.adapters.persistence.memory_session_store import MemorySessionStore
from buy_agent.application.chat_orchestrator import ChatOrchestrator
from buy_agent.application.context_builder import ContextBuilder
from buy_agent.application.identity_service import IdentityService
from buy_agent.application.requirement_resolver import RequirementResolver
from buy_agent.application.session_service import SessionService
from buy_agent.application.tool_policy import ToolPolicy
from buy_agent.domain.enums import ChannelType, InboundEventType
from buy_agent.domain.events import InboundEvent
from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity

ERROR_MESSAGES = {
    "missing": ("IDENTITY_NOT_FOUND", "未找到您的用户身份，请联系管理员。"),
    "disabled": ("USER_DISABLED", "当前用户已被禁用，请联系管理员。"),
    "no_role": ("USER_ROLE_MISSING", "当前用户未配置采购角色，请联系管理员。"),
}


def build_orchestrator(
    backend: FakeBackendGateway | None = None,
) -> tuple[ChatOrchestrator, FakeProcurementAgent, FakeChannel]:
    backend = backend or FakeBackendGateway()
    agent = FakeProcurementAgent()
    channel = FakeChannel()
    orchestrator = ChatOrchestrator(
        identity_service=IdentityService(backend),
        session_service=SessionService(MemorySessionStore()),
        requirement_resolver=RequirementResolver(backend),
        context_builder=ContextBuilder(),
        tool_policy=ToolPolicy(),
        agent=agent,
        channel=channel,
        message_store=MemoryMessageStore(),
        event_store=MemoryEventStore(),
        lock_manager=LocalLockManager(),
    )
    return orchestrator, agent, channel


def event(
    event_id: str,
    *,
    user: str = "requester",
    message_id: str | None = None,
    event_type: InboundEventType = InboundEventType.TEXT_MESSAGE,
    text: str | None = "查看采购单",
) -> InboundEvent:
    return InboundEvent(
        event_id=event_id,
        message_id=message_id or f"message-{event_id}",
        event_type=event_type,
        identity=ExternalIdentity(ChannelType.FEISHU, "tenant", user),
        conversation_id=f"conversation-{user}",
        text=text,
        action=None,
        raw_payload={},
    )


@pytest.mark.parametrize("user", ["missing", "disabled", "no_role"])
async def test_identity_errors_are_mapped_without_agent(
    user: str, caplog: pytest.LogCaptureFixture
) -> None:
    orchestrator, agent, channel = build_orchestrator()
    code, expected_message = ERROR_MESSAGES[user]
    with caplog.at_level(logging.WARNING):
        await orchestrator.handle(event("identity-error", user=user))

    assert agent.calls == []
    assert [message.text for message in channel.sent_messages] == [expected_message]
    assert code in caplog.text
    assert "event_id=identity-error" in caplog.text
    assert "message_id=message-identity-error" in caplog.text
    assert f"conversation_id=conversation-{user}" in caplog.text


@pytest.mark.parametrize(
    ("text", "code", "expected_message"),
    [
        (
            "requirement_id=999",
            "REQUIREMENT_NOT_FOUND",
            "未找到指定采购单，请确认编号后重试。",
        ),
        (
            "requirement_id=201",
            "REQUIREMENT_ACCESS_DENIED",
            "您无权访问该采购单。",
        ),
    ],
)
async def test_requirement_errors_are_mapped_without_agent(
    text: str,
    code: str,
    expected_message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    orchestrator, agent, channel = build_orchestrator()
    with caplog.at_level(logging.WARNING):
        await orchestrator.handle(event("requirement-error", text=text))

    assert agent.calls == []
    assert [message.text for message in channel.sent_messages] == [expected_message]
    assert code in caplog.text


@pytest.mark.parametrize(
    ("event_type", "text"),
    [
        (InboundEventType.UNSUPPORTED_MESSAGE, "ignored"),
        (InboundEventType.TEXT_MESSAGE, None),
        (InboundEventType.TEXT_MESSAGE, ""),
        (InboundEventType.TEXT_MESSAGE, "   "),
    ],
)
async def test_invalid_message_returns_fixed_reply_before_identity_and_agent(
    event_type: InboundEventType, text: str | None
) -> None:
    class FailOnIdentityBackend(FakeBackendGateway):
        async def resolve_identity(self, identity: ExternalIdentity) -> CurrentPrincipal:
            raise AssertionError("identity resolution must not be called")

    orchestrator, agent, channel = build_orchestrator(FailOnIdentityBackend())
    await orchestrator.handle(event("invalid", event_type=event_type, text=text))

    assert agent.calls == []
    assert [message.text for message in channel.sent_messages] == [
        "当前仅支持文字采购信息，请直接发送文字内容。"
    ]


async def test_duplicate_message_id_with_new_event_id_is_not_replied_twice() -> None:
    orchestrator, agent, channel = build_orchestrator()
    await orchestrator.handle(event("first", message_id="same-message"))
    await orchestrator.handle(event("second", message_id="same-message"))

    assert len(agent.calls) == 1
    assert len(channel.sent_messages) == 1


async def test_unexpected_error_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingBackend(FakeBackendGateway):
        async def resolve_identity(self, identity: ExternalIdentity) -> CurrentPrincipal:
            raise RuntimeError("unexpected")

    orchestrator, agent, channel = build_orchestrator(FailingBackend())
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="unexpected"):
        await orchestrator.handle(event("unexpected"))

    assert agent.calls == []
    assert channel.sent_messages == []
    assert "unexpected_error" in caplog.text


async def test_invalid_duplicate_is_not_replied_twice() -> None:
    orchestrator, agent, channel = build_orchestrator()
    invalid = event("invalid", text="")
    await orchestrator.handle(invalid)
    await orchestrator.handle(invalid)

    assert agent.calls == []
    assert len(channel.sent_messages) == 1
