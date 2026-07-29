import logging

from buy_agent.application.context_builder import ContextBuilder
from buy_agent.application.errors import ApplicationError, map_application_error
from buy_agent.application.identity_service import IdentityService
from buy_agent.application.requirement_resolver import RequirementResolver
from buy_agent.application.session_service import SessionService, build_session_key
from buy_agent.application.tool_policy import ToolPolicy
from buy_agent.domain.agent import AgentResponse
from buy_agent.domain.conversation import SessionState
from buy_agent.domain.enums import InboundEventType
from buy_agent.domain.events import InboundEvent
from buy_agent.ports.agent import ProcurementAgentPort
from buy_agent.ports.backend_gateway import BackendGateway
from buy_agent.ports.channel import ChannelPort
from buy_agent.ports.event_store import EventStore
from buy_agent.ports.lock_manager import LockManager
from buy_agent.ports.message_store import MessageStore

logger = logging.getLogger(__name__)
_UNSUPPORTED_MESSAGE = "当前暂不支持图片识别，请直接发送采购信息文字。"
_INTERNAL_ERROR = "处理采购消息时出现问题，请稍后重试。"


class ChatOrchestrator:
    def __init__(
        self,
        *,
        identity_service: IdentityService,
        session_service: SessionService,
        requirement_resolver: RequirementResolver,
        context_builder: ContextBuilder,
        tool_policy: ToolPolicy,
        agent: ProcurementAgentPort,
        channel: ChannelPort,
        event_store: EventStore,
        lock_manager: LockManager,
        backend_gateway: BackendGateway | None = None,
        message_store: MessageStore | None = None,
    ) -> None:
        self._identity_service = identity_service
        self._session_service = session_service
        self._requirement_resolver = requirement_resolver
        self._context_builder = context_builder
        self._tool_policy = tool_policy
        self._agent = agent
        self._channel = channel
        self._event_store = event_store
        self._lock_manager = lock_manager
        self._backend = backend_gateway or requirement_resolver.backend

    async def handle(self, event: InboundEvent) -> AgentResponse | None:
        session_key = build_session_key(event.identity)
        async with self._lock_manager.lock(session_key):
            started = await self._event_store.try_start(
                event_id=event.event_id, message_id=event.message_id
            )
            if not started:
                return None
            try:
                if (
                    event.event_type is not InboundEventType.TEXT_MESSAGE
                    or event.text is None
                    or not event.text.strip()
                ):
                    response = AgentResponse(_UNSUPPORTED_MESSAGE)
                    await self._send(event, response)
                    await self._event_store.mark_completed(event.event_id)
                    return response

                principal = await self._identity_service.resolve(event.identity)
                bundle = await self._session_service.get_or_create(
                    session_key=session_key,
                    principal=principal,
                    platform_type=str(event.identity.channel),
                    external_conversation_id=event.conversation_id,
                )
                user_message = event.text
                await self._session_service.append_user_message(
                    conversation_id=bundle.conversation.conversation_id,
                    external_message_id=event.message_id,
                    content=user_message,
                )
                resolution = await self._requirement_resolver.resolve_for_conversation(
                    user_message=user_message,
                    principal=principal,
                    conversation=bundle.conversation,
                    memory=bundle.memory,
                )
                tools = self._tool_policy.resolve_allowed_tools(
                    principal, bundle.memory, bundle.conversation.purchase_request_id
                )
                context = self._context_builder.build(
                    principal=principal,
                    session=SessionState(session_key, principal.user_id),
                    requirement=resolution.requirement,
                    available_tool_names=tools,
                    trace_id=event.event_id,
                    event_id=event.event_id,
                    session_key=session_key,
                    memory=bundle.memory,
                    recent_messages=bundle.recent_messages,
                    user_message=user_message,
                    backend_gateway=self._backend,
                )
                result = await self._agent.run(user_message, context)
                await self._session_service.apply_agent_result(
                    conversation=bundle.conversation,
                    current_memory=bundle.memory,
                    result=result,
                )
                await self._session_service.append_agent_message(
                    conversation_id=bundle.conversation.conversation_id,
                    response=result.response,
                )
                await self._send(event, result.response)
                await self._event_store.mark_completed(event.event_id)
                return result.response
            except ApplicationError as error:
                logger.warning(
                    "application_error code=%s event_id=%s", error.error_code, event.event_id
                )
                response = AgentResponse(map_application_error(error))
                await self._send(event, response)
                await self._event_store.mark_failed(event.event_id, error.error_code)
                return response
            except Exception:
                logger.exception("unexpected_error event_id=%s", event.event_id)
                await self._event_store.mark_failed(event.event_id, "INTERNAL_ERROR")
                response = AgentResponse(_INTERNAL_ERROR)
                await self._send(event, response)
                return response

    async def _send(self, event: InboundEvent, response: AgentResponse) -> None:
        text = response.text.strip()
        if not text and response.interaction is not None:
            text = response.interaction.fallback_text or response.interaction.title
        if text:
            await self._channel.send_text(conversation_id=event.conversation_id, text=text)
