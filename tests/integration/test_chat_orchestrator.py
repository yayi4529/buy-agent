import asyncio
from dataclasses import dataclass

from buy_agent.adapters.agent.fake_procurement_agent import FakeProcurementAgent
from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway
from buy_agent.adapters.channels.fake_channel import FakeChannel
from buy_agent.adapters.persistence.local_lock_manager import LocalLockManager
from buy_agent.adapters.persistence.memory_conversation_store import (
    MemoryConversationStore,
)
from buy_agent.adapters.persistence.memory_event_store import MemoryEventStore
from buy_agent.adapters.persistence.memory_message_store import MemoryMessageStore
from buy_agent.adapters.persistence.memory_session_store import MemorySessionStateStore
from buy_agent.application.chat_orchestrator import ChatOrchestrator
from buy_agent.application.context_builder import ContextBuilder
from buy_agent.application.identity_service import IdentityService
from buy_agent.application.requirement_resolver import RequirementResolver
from buy_agent.application.session_service import SessionService, build_session_key
from buy_agent.application.tool_policy import ToolPolicy
from buy_agent.domain.enums import ChannelType, InboundEventType
from buy_agent.domain.events import InboundEvent
from buy_agent.domain.identity import ExternalIdentity


@dataclass
class Harness:
    orchestrator: ChatOrchestrator
    agent: FakeProcurementAgent
    channel: FakeChannel
    conversations: MemoryConversationStore
    states: MemorySessionStateStore
    messages: MemoryMessageStore


def harness(delay: float = 0) -> Harness:
    backend = FakeBackendGateway()
    conversations = MemoryConversationStore()
    states = MemorySessionStateStore()
    messages = MemoryMessageStore()
    agent = FakeProcurementAgent(delay)
    channel = FakeChannel()
    session_service = SessionService(conversations, states, messages)
    orchestrator = ChatOrchestrator(
        identity_service=IdentityService(backend),
        session_service=session_service,
        requirement_resolver=RequirementResolver(backend),
        context_builder=ContextBuilder(),
        tool_policy=ToolPolicy(),
        agent=agent,
        channel=channel,
        event_store=MemoryEventStore(),
        lock_manager=LocalLockManager(),
        backend_gateway=backend,
    )
    return Harness(orchestrator, agent, channel, conversations, states, messages)


def event(event_id: str, user: str = "requester", message_id: str | None = None) -> InboundEvent:
    return InboundEvent(
        event_id,
        message_id or f"m-{event_id}",
        InboundEventType.TEXT_MESSAGE,
        ExternalIdentity(ChannelType.FEISHU, "tenant", user),
        f"chat-{user}",
        "采购服务器",
        None,
        {},
    )


async def test_user_message_precedes_agent_and_memory_restores() -> None:
    app = harness()
    await app.orchestrator.handle(event("e1"))
    await app.orchestrator.handle(event("e2"))
    assert len(app.agent.calls) == 2
    assert app.agent.calls[1][1].memory is not None
    conversation = await app.conversations.get_active_by_session_key(
        build_session_key(event("x").identity)
    )
    recent = await app.messages.list_recent(conversation.conversation_id, limit=10)  # type: ignore[union-attr]
    assert [item.sender_type for item in recent] == ["USER", "AGENT", "USER", "AGENT"]


async def test_duplicate_event_and_message_call_agent_once() -> None:
    app = harness()
    await asyncio.gather(
        app.orchestrator.handle(event("same", message_id="same-message")),
        app.orchestrator.handle(event("same", message_id="same-message")),
    )
    await app.orchestrator.handle(event("other", message_id="same-message"))
    assert len(app.agent.calls) == 1
    assert len(app.channel.sent_messages) == 1


async def test_same_session_serial_and_different_sessions_parallel() -> None:
    same = harness(0.02)
    await asyncio.gather(*(same.orchestrator.handle(event(f"e{i}")) for i in range(2)))
    assert same.agent.max_active_calls == 1

    different = harness(0.02)
    await asyncio.gather(
        different.orchestrator.handle(event("a", "requester")),
        different.orchestrator.handle(event("b", "reviewer")),
    )
    assert different.agent.max_active_calls == 2
    assert {call[1].memory.conversation_id for call in different.agent.calls if call[1].memory} == {
        1,
        2,
    }
