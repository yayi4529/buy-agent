from typing import Protocol


class EventStore(Protocol):
    async def is_duplicate(self, *, event_id: str, message_id: str | None) -> bool: ...

    async def mark_completed(self, *, event_id: str, message_id: str | None) -> None: ...
