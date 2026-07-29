import asyncio
from dataclasses import dataclass
from enum import StrEnum


class EventProcessingStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    message_id: str | None
    status: EventProcessingStatus
    error_code: str | None = None


class MemoryEventStore:
    def __init__(self) -> None:
        self._events: dict[str, EventRecord] = {}
        self._message_ids: set[str] = set()
        self._guard = asyncio.Lock()

    async def try_start(self, *, event_id: str, message_id: str | None) -> bool:
        async with self._guard:
            if event_id in self._events or (
                message_id is not None and message_id in self._message_ids
            ):
                return False
            self._events[event_id] = EventRecord(
                event_id, message_id, EventProcessingStatus.PROCESSING
            )
            if message_id is not None:
                self._message_ids.add(message_id)
            return True

    async def mark_completed(self, event_id: str) -> None:
        await self._update(event_id, EventProcessingStatus.COMPLETED)

    async def mark_failed(self, event_id: str, error_code: str) -> None:
        await self._update(event_id, EventProcessingStatus.FAILED, error_code)

    async def get(self, event_id: str) -> EventRecord | None:
        return self._events.get(event_id)

    async def _update(
        self,
        event_id: str,
        status: EventProcessingStatus,
        error_code: str | None = None,
    ) -> None:
        async with self._guard:
            current = self._events.get(event_id)
            if current is None:
                raise LookupError(f"event not found: {event_id}")
            self._events[event_id] = EventRecord(
                current.event_id, current.message_id, status, error_code
            )
