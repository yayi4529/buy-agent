import logging
from dataclasses import dataclass

from buy_agent.adapters.agent.fake_procurement_agent import FakeProcurementAgent
from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway
from buy_agent.adapters.channels.fake_channel import FakeChannel
from buy_agent.adapters.channels.feishu.action_adapter import FeishuActionAdapter
from buy_agent.adapters.channels.feishu.action_result_renderer import FeishuActionResultRenderer
from buy_agent.adapters.channels.feishu.client import FakeFeishuClient, FeishuChannelClient
from buy_agent.adapters.channels.feishu.event_adapter import FeishuEventAdapter
from buy_agent.adapters.channels.feishu.handlers import (
    FeishuActionHandler,
    FeishuClientPort,
    FeishuMessageHandler,
)
from buy_agent.adapters.channels.feishu.response_renderer import FeishuResponseRenderer
from buy_agent.adapters.persistence.local_lock_manager import LocalLockManager
from buy_agent.adapters.persistence.memory_action_execution_store import (
    MemoryActionExecutionStore,
)
from buy_agent.adapters.persistence.memory_conversation_store import MemoryConversationStore
from buy_agent.adapters.persistence.memory_event_store import MemoryEventStore
from buy_agent.adapters.persistence.memory_message_store import MemoryMessageStore
from buy_agent.adapters.persistence.memory_session_store import MemorySessionStore
from buy_agent.agent.procurement_agent import ProcurementAgent
from buy_agent.application.action_orchestrator import ActionOrchestrator
from buy_agent.application.chat_orchestrator import ChatOrchestrator
from buy_agent.application.context_builder import ContextBuilder
from buy_agent.application.identity_service import IdentityService
from buy_agent.application.requirement_resolver import RequirementResolver
from buy_agent.application.session_service import SessionService
from buy_agent.application.tool_policy import ToolPolicy
from buy_agent.bootstrap.llm_factory import build_llm_client
from buy_agent.bootstrap.settings import Settings
from buy_agent.interfaces.http.webhook_processor import (
    FeishuSecurityAdapter,
    FeishuWebhookProcessor,
    LarkOapiSecurityAdapter,
)
from buy_agent.ports.agent import ProcurementAgentPort
from buy_agent.ports.backend_gateway import BackendGateway
from buy_agent.ports.llm_client import LLMClient
from buy_agent.tools.requester import build_requester_tool_registry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApplicationOverrides:
    backend_gateway: BackendGateway | None = None
    llm_client: LLMClient | None = None
    procurement_agent: ProcurementAgentPort | None = None
    feishu_client: FeishuClientPort | None = None
    security_adapter: FeishuSecurityAdapter | None = None


@dataclass(frozen=True)
class ApplicationContainer:
    settings: Settings
    conversation_store: MemoryConversationStore
    session_store: MemorySessionStore
    message_store: MemoryMessageStore
    event_store: MemoryEventStore
    action_execution_store: MemoryActionExecutionStore
    lock_manager: LocalLockManager
    backend_gateway: BackendGateway
    identity_service: IdentityService
    session_service: SessionService
    procurement_agent: ProcurementAgentPort
    chat_orchestrator: ChatOrchestrator
    action_orchestrator: ActionOrchestrator
    feishu_client: FeishuClientPort
    feishu_message_handler: FeishuMessageHandler
    feishu_action_handler: FeishuActionHandler
    webhook_processor: FeishuWebhookProcessor
    closeables: tuple[object, ...] = ()

    async def aclose(self) -> None:
        for resource in self.closeables:
            try:
                close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
                if close is None:
                    continue
                result = close()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                logger.exception(
                    "application resource close failed type=%s", type(resource).__name__
                )


def build_application(
    settings: Settings, *, overrides: ApplicationOverrides | None = None
) -> ApplicationContainer:
    values = overrides or ApplicationOverrides()
    backend = values.backend_gateway or FakeBackendGateway()
    conversation_store = MemoryConversationStore()
    session_store = MemorySessionStore()
    message_store = MemoryMessageStore()
    event_store = MemoryEventStore()
    action_store = MemoryActionExecutionStore()
    lock_manager = LocalLockManager()
    identity_service = IdentityService(backend)
    session_service = SessionService(conversation_store, session_store, message_store, settings)
    resolver = RequirementResolver(backend)
    llm: LLMClient | None = values.llm_client
    if values.procurement_agent is not None:
        agent = values.procurement_agent
    elif llm is not None or (settings.llm_model and settings.llm_api_key):
        llm = llm or build_llm_client(settings)
        agent = ProcurementAgent(
            llm=llm,
            registry=build_requester_tool_registry(),
            settings=settings,
        )
    else:
        agent = FakeProcurementAgent()
    channel = FakeChannel()
    chat = ChatOrchestrator(
        identity_service=identity_service,
        session_service=session_service,
        requirement_resolver=resolver,
        context_builder=ContextBuilder(),
        tool_policy=ToolPolicy(),
        agent=agent,
        channel=channel,
        event_store=event_store,
        lock_manager=lock_manager,
        backend_gateway=backend,
        message_store=message_store,
    )
    action = ActionOrchestrator(
        session_service=session_service,
        backend_gateway=backend,
        action_execution_store=action_store,
        lock_manager=lock_manager,
    )
    if values.feishu_client is not None:
        feishu_client = values.feishu_client
    elif settings.feishu_enabled and settings.feishu_app_id and settings.feishu_app_secret:
        feishu_client = FeishuChannelClient(settings)
    else:
        feishu_client = FakeFeishuClient()
    message_handler = FeishuMessageHandler(
        event_adapter=FeishuEventAdapter(),
        orchestrator=chat,
        renderer=FeishuResponseRenderer(),
        client=feishu_client,
    )
    action_handler = FeishuActionHandler(
        action_adapter=FeishuActionAdapter(),
        identity_service=identity_service,
        orchestrator=action,
        renderer=FeishuActionResultRenderer(),
        client=feishu_client,
    )
    security = values.security_adapter or LarkOapiSecurityAdapter(
        encrypt_key=settings.feishu_encrypt_key or "",
        verification_token=settings.feishu_verification_token or "",
    )
    processor = FeishuWebhookProcessor(
        security=security,
        message_handler=message_handler,
        action_handler=action_handler,
    )
    closeables = tuple(item for item in (llm, feishu_client) if item is not None)
    return ApplicationContainer(
        settings,
        conversation_store,
        session_store,
        message_store,
        event_store,
        action_store,
        lock_manager,
        backend,
        identity_service,
        session_service,
        agent,
        chat,
        action,
        feishu_client,
        message_handler,
        action_handler,
        processor,
        closeables,
    )
