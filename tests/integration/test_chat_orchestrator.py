import asyncio
from dataclasses import dataclass

import pytest

from buy_agent.adapters.agent.fake_procurement_agent import FakeProcurementAgent
from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway, fake_requirement
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
from buy_agent.domain.identity import ExternalIdentity


@dataclass
class Harness:
    orchestrator: ChatOrchestrator
    agent: FakeProcurementAgent
    channel: FakeChannel
    sessions: MemorySessionStore


def harness(requirements: dict[int, list] | None = None, delay: float = 0.0) -> Harness:
    backend = FakeBackendGateway(requirements=requirements)
    sessions = MemorySessionStore()
    agent = FakeProcurementAgent(delay=delay)
    channel = FakeChannel()
    orchestrator = ChatOrchestrator(
        identity_service=IdentityService(backend),
        session_service=SessionService(sessions),
        requirement_resolver=RequirementResolver(backend),
        context_builder=ContextBuilder(),
        tool_policy=ToolPolicy(),
        agent=agent,
        channel=channel,
        message_store=MemoryMessageStore(),
        event_store=MemoryEventStore(),
        lock_manager=LocalLockManager(),
    )
    return Harness(orchestrator, agent, channel, sessions)


def event(event_id: str, user: str = "requester") -> InboundEvent:
    return InboundEvent(
        event_id=event_id,
        message_id=f"message-{event_id}",
        event_type=InboundEventType.TEXT_MESSAGE,
        identity=ExternalIdentity(ChannelType.FEISHU, "tenant", user),
        conversation_id=f"conversation-{user}",
        text="查看我的采购单",
        action=None,
        raw_payload={},
    )


@pytest.mark.asyncio
async def test_single_user_flows_through_agent_and_channel() -> None:
    app = harness({1: [fake_requirement(101)]})
    await app.orchestrator.handle(event("e1"))
    assert len(app.agent.calls) == 1
    context = app.agent.calls[0][1]
    assert context.principal.user_id == 1
    assert context.requirement and context.requirement.requirement_id == 101
    assert "save_requester_fields" in context.available_tool_names
    assert len(app.channel.sent_messages) == 1
    assert "requirement_id=101" in app.channel.sent_messages[0].text


@pytest.mark.asyncio
async def test_multiple_requirements_prompt_without_agent_call() -> None:
    app = harness({1: [fake_requirement(101), fake_requirement(102)]})
    await app.orchestrator.handle(event("e1"))
    assert app.agent.calls == []
    assert len(app.channel.sent_messages) == 1
    assert "请明确选择" in app.channel.sent_messages[0].text


@pytest.mark.asyncio
async def test_duplicate_event_is_processed_once() -> None:
    app = harness({1: [fake_requirement(101)]})
    duplicate = event("same")
    await asyncio.gather(app.orchestrator.handle(duplicate), app.orchestrator.handle(duplicate))
    assert len(app.agent.calls) == 1
    assert len(app.channel.sent_messages) == 1


@pytest.mark.asyncio
async def test_same_session_is_strictly_serialized() -> None:
    app = harness({1: [fake_requirement(101)]}, delay=0.03)
    await asyncio.gather(*(app.orchestrator.handle(event(f"e{i}")) for i in range(3)))
    assert len(app.agent.calls) == 3
    assert app.agent.max_active_calls == 1


@pytest.mark.asyncio
async def test_different_sessions_run_in_parallel_and_do_not_mix_memory() -> None:
    app = harness({1: [fake_requirement(101)], 2: [fake_requirement(201)]}, delay=0.03)
    await asyncio.gather(
        app.orchestrator.handle(event("e1", "requester")),
        app.orchestrator.handle(event("e2", "reviewer")),
    )
    assert app.agent.max_active_calls == 2
    contexts = [call[1] for call in app.agent.calls]
    assert {context.principal.user_id for context in contexts} == {1, 2}
    assert {context.session.user_id for context in contexts} == {1, 2}
