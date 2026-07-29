from dataclasses import replace
from datetime import UTC, datetime

from buy_agent.domain.conversation import (
    AgentConversation,
    ConversationStatus,
    NewAgentConversation,
)


class MemoryConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[int, AgentConversation] = {}
        self._next_id = 1

    async def get_active_by_session_key(self, session_key: str) -> AgentConversation | None:
        matches = [
            conversation
            for conversation in self._conversations.values()
            if conversation.session_key == session_key
            and conversation.status is ConversationStatus.ACTIVE
        ]
        if not matches:
            return None
        return replace(max(matches, key=lambda value: value.started_at))

    async def create(self, new_conversation: NewAgentConversation) -> AgentConversation:
        now = datetime.now(UTC)
        conversation = AgentConversation(
            conversation_id=self._next_id,
            session_key=new_conversation.session_key,
            employee_id=new_conversation.employee_id,
            platform_type=new_conversation.platform_type,
            external_conversation_id=new_conversation.external_conversation_id,
            purchase_request_id=None,
            started_at=now,
            last_active_at=now,
        )
        self._next_id += 1
        self._conversations[conversation.conversation_id] = conversation
        return replace(conversation)

    async def update_last_active(self, conversation_id: int) -> None:
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            raise LookupError(f"conversation not found: {conversation_id}")
        self._conversations[conversation_id] = replace(
            conversation, last_active_at=datetime.now(UTC)
        )

    async def get_by_id(self, conversation_id: int) -> AgentConversation | None:
        conversation = self._conversations.get(conversation_id)
        return replace(conversation) if conversation is not None else None
