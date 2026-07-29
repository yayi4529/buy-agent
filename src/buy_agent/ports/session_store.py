from typing import Protocol

from buy_agent.domain.conversation import AgentConversation, NewAgentConversation
from buy_agent.memory.models import SessionMemory


class SessionStateVersionConflict(RuntimeError):
    pass


class ConversationStore(Protocol):
    async def get_active_by_session_key(self, session_key: str) -> AgentConversation | None: ...

    async def create(self, new_conversation: NewAgentConversation) -> AgentConversation: ...

    async def update_last_active(self, conversation_id: int) -> None: ...

    async def get_by_id(self, conversation_id: int) -> AgentConversation | None: ...

    async def bind_purchase_request_and_complete(
        self, *, conversation_id: int, request_id: int
    ) -> AgentConversation: ...


class SessionStateStore(Protocol):
    async def get(self, conversation_id: int) -> SessionMemory | None: ...

    async def create(self, memory: SessionMemory) -> SessionMemory: ...

    async def save(self, memory: SessionMemory, *, expected_version: int) -> SessionMemory: ...
