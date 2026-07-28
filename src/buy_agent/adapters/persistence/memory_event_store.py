import asyncio


class MemoryEventStore:
    def __init__(self) -> None:
        self._event_ids: set[str] = set()
        self._message_ids: set[str] = set()
        self._guard = asyncio.Lock()

    async def is_duplicate(self, *, event_id: str, message_id: str | None) -> bool:
        async with self._guard:
            return event_id in self._event_ids or (
                message_id is not None and message_id in self._message_ids
            )

    async def mark_completed(self, *, event_id: str, message_id: str | None) -> None:
        async with self._guard:
            self._event_ids.add(event_id)
            if message_id is not None:
                self._message_ids.add(message_id)
