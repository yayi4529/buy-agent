from typing import Protocol


class EventStore(Protocol):
    async def exists(self, event_id: str) -> bool: ...

    async def mark_completed(self, event_id: str, message_id: str | None) -> None: ...
