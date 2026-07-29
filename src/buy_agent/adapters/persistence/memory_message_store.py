from dataclasses import replace

from buy_agent.domain.conversation import ConversationMessage, NewConversationMessage


class DuplicateExternalMessageError(ValueError):
    pass


class MemoryMessageStore:
    def __init__(self) -> None:
        self._messages: dict[int, list[ConversationMessage]] = {}
        self._next_id = 1

    async def append(self, message: NewConversationMessage) -> ConversationMessage:
        messages = self._messages.setdefault(message.conversation_id, [])
        if message.external_message_id is not None and any(
            item.external_message_id == message.external_message_id for item in messages
        ):
            raise DuplicateExternalMessageError(message.external_message_id)
        stored = ConversationMessage(
            message_id=self._next_id,
            conversation_id=message.conversation_id,
            external_message_id=message.external_message_id,
            sender_type=message.sender_type,
            content=message.content,
            created_at=message.created_at,
        )
        self._next_id += 1
        messages.append(stored)
        return replace(stored)

    async def list_recent(
        self, conversation_id: int, *, limit: int
    ) -> tuple[ConversationMessage, ...]:
        if limit < 0:
            raise ValueError("limit must not be negative")
        ordered = sorted(
            self._messages.get(conversation_id, ()),
            key=lambda message: (message.created_at, message.message_id),
        )
        return tuple(replace(item) for item in ordered[-limit:] if limit)
