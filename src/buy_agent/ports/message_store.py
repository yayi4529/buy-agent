from typing import Protocol

from buy_agent.domain.conversation import ConversationMessage, NewConversationMessage


class MessageStore(Protocol):
    async def append(self, message: NewConversationMessage) -> ConversationMessage: ...

    async def list_recent(
        self, conversation_id: int, *, limit: int
    ) -> tuple[ConversationMessage, ...]: ...
