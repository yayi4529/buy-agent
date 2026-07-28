from buy_agent.application.context_builder import ContextBuilder
from buy_agent.application.identity_service import IdentityService
from buy_agent.application.requirement_resolver import RequirementResolver
from buy_agent.application.session_service import SessionService, build_session_key
from buy_agent.application.tool_policy import ToolPolicy
from buy_agent.domain.events import InboundEvent
from buy_agent.ports.agent import ProcurementAgentPort
from buy_agent.ports.channel import ChannelPort
from buy_agent.ports.event_store import EventStore
from buy_agent.ports.lock_manager import LockManager
from buy_agent.ports.message_store import MessageStore


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
        message_store: MessageStore,
        event_store: EventStore,
        lock_manager: LockManager,
    ) -> None:
        self._identity_service = identity_service
        self._session_service = session_service
        self._requirement_resolver = requirement_resolver
        self._context_builder = context_builder
        self._tool_policy = tool_policy
        self._agent = agent
        self._channel = channel
        self._message_store = message_store
        self._event_store = event_store
        self._lock_manager = lock_manager

    async def handle(self, event: InboundEvent) -> None:
        if await self._event_store.exists(event.event_id):
            return
        session_key = build_session_key(event.identity)
        async with self._lock_manager.lock(session_key):
            if await self._event_store.exists(event.event_id):
                return
            principal = await self._identity_service.resolve(event.identity)
            session = await self._session_service.load_or_create(event.identity, principal)
            user_message = event.text or ""
            resolution = await self._requirement_resolver.resolve(
                user_message=user_message, principal=principal, session=session
            )
            if resolution.needs_selection:
                choices = ", ".join(
                    f"{item.requirement_no}(ID={item.requirement_id})"
                    for item in resolution.candidates
                )
                await self._channel.send_text(
                    conversation_id=event.conversation_id,
                    text=f"检测到多条未完成采购单，请明确选择：{choices}",
                )
                await self._event_store.mark_completed(event.event_id, event.message_id)
                return

            requirement = resolution.requirement
            tools = self._tool_policy.allowed_tools(principal, requirement)
            context = self._context_builder.build(
                principal=principal,
                session=session,
                requirement=requirement,
                available_tool_names=tools,
            )
            response = await self._agent.respond(user_message, context)
            await self._message_store.append(session_key, "user", user_message)
            await self._message_store.append(session_key, "assistant", response)
            session.recent_messages = await self._message_store.recent(session_key)
            if requirement is not None:
                session.active_requirement_id = requirement.requirement_id
                session.current_stage = requirement.status
            await self._session_service.save(session)
            await self._channel.send_text(conversation_id=event.conversation_id, text=response)
            await self._event_store.mark_completed(event.event_id, event.message_id)
