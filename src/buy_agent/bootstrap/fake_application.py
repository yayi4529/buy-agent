from dataclasses import dataclass

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


@dataclass(frozen=True)
class ApplicationContainer:
    backend: FakeBackendGateway
    session_store: MemorySessionStore
    message_store: MemoryMessageStore
    event_store: MemoryEventStore
    lock_manager: LocalLockManager
    identity_service: IdentityService
    session_service: SessionService
    requirement_resolver: RequirementResolver
    context_builder: ContextBuilder
    tool_policy: ToolPolicy
    agent: FakeProcurementAgent
    channel: FakeChannel
    orchestrator: ChatOrchestrator


def build_fake_application() -> ApplicationContainer:
    backend = FakeBackendGateway()
    session_store = MemorySessionStore()
    message_store = MemoryMessageStore()
    event_store = MemoryEventStore()
    lock_manager = LocalLockManager()
    identity_service = IdentityService(backend)
    session_service = SessionService(session_store)
    requirement_resolver = RequirementResolver(backend)
    context_builder = ContextBuilder()
    tool_policy = ToolPolicy()
    agent = FakeProcurementAgent()
    channel = FakeChannel()
    orchestrator = ChatOrchestrator(
        identity_service=identity_service,
        session_service=session_service,
        requirement_resolver=requirement_resolver,
        context_builder=context_builder,
        tool_policy=tool_policy,
        agent=agent,
        channel=channel,
        message_store=message_store,
        event_store=event_store,
        lock_manager=lock_manager,
    )
    return ApplicationContainer(
        backend=backend,
        session_store=session_store,
        message_store=message_store,
        event_store=event_store,
        lock_manager=lock_manager,
        identity_service=identity_service,
        session_service=session_service,
        requirement_resolver=requirement_resolver,
        context_builder=context_builder,
        tool_policy=tool_policy,
        agent=agent,
        channel=channel,
        orchestrator=orchestrator,
    )
