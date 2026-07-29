from dataclasses import dataclass

from buy_agent.bootstrap.settings import Settings
from buy_agent.domain.agent import AgentResponse, AgentRunResult
from buy_agent.domain.conversation import (
    AgentConversation,
    ConversationMessage,
    MessageSenderType,
    NewAgentConversation,
    NewConversationMessage,
)
from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity
from buy_agent.memory.models import SessionMemory
from buy_agent.memory.service import apply_memory_patch
from buy_agent.ports.message_store import MessageStore
from buy_agent.ports.session_store import ConversationStore, SessionStateStore


def build_session_key(identity: ExternalIdentity) -> str:
    return (
        f"procurement:{identity.channel}:{identity.external_tenant_id}:{identity.external_user_id}"
    )


@dataclass(frozen=True)
class SessionBundle:
    conversation: AgentConversation
    memory: SessionMemory
    recent_messages: tuple[ConversationMessage, ...]


class SessionService:
    def __init__(
        self,
        conversation_store: ConversationStore,
        state_store: SessionStateStore,
        message_store: MessageStore,
        settings: Settings | None = None,
    ) -> None:
        self._conversations = conversation_store
        self._states = state_store
        self._messages = message_store
        self._settings = settings or Settings()

    async def get_or_create(
        self,
        *,
        session_key: str,
        principal: CurrentPrincipal,
        platform_type: str,
        external_conversation_id: str | None,
    ) -> SessionBundle:
        conversation = await self._conversations.get_active_by_session_key(session_key)
        if conversation is None:
            conversation = await self._conversations.create(
                NewAgentConversation(
                    session_key=session_key,
                    employee_id=principal.user_id,
                    platform_type=platform_type,
                    external_conversation_id=external_conversation_id,
                )
            )
        memory = await self._states.get(conversation.conversation_id)
        if memory is None:
            memory = await self._states.create(
                SessionMemory(
                    conversation_id=conversation.conversation_id,
                    current_action=self._settings.default_current_action,
                    purchase_request_id=None,
                    confirmed=False,
                )
            )
        recent = await self._messages.list_recent(
            conversation.conversation_id, limit=self._settings.recent_message_limit
        )
        return SessionBundle(conversation, memory, recent)

    async def append_user_message(
        self,
        *,
        conversation_id: int,
        external_message_id: str | None,
        content: str,
    ) -> ConversationMessage:
        return await self._messages.append(
            NewConversationMessage(
                conversation_id=conversation_id,
                external_message_id=external_message_id,
                sender_type=MessageSenderType.USER,
                content=content,
            )
        )

    async def apply_agent_result(
        self,
        *,
        conversation: AgentConversation,
        current_memory: SessionMemory,
        result: AgentRunResult,
    ) -> SessionMemory:
        patch = result.memory_patch
        if patch is None or patch.is_empty:
            await self._conversations.update_last_active(conversation.conversation_id)
            return current_memory
        updated = apply_memory_patch(current_memory, patch)
        saved = await self._states.save(updated, expected_version=current_memory.state_version)
        await self._conversations.update_last_active(conversation.conversation_id)
        return saved

    async def append_agent_message(
        self, *, conversation_id: int, response: AgentResponse
    ) -> ConversationMessage | None:
        content = response.text.strip()
        if not content and response.interaction is not None:
            content = (response.interaction.fallback_text or response.interaction.title).strip()
        if not content:
            return None
        return await self._messages.append(
            NewConversationMessage(
                conversation_id=conversation_id,
                sender_type=MessageSenderType.AGENT,
                content=content,
            )
        )
