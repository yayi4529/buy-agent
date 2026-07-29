from copy import deepcopy
from dataclasses import replace

from buy_agent.memory.models import SessionMemory
from buy_agent.ports.session_store import SessionStateVersionConflict


class MemorySessionStateStore:
    def __init__(self) -> None:
        self._states: dict[int, SessionMemory] = {}

    async def get(self, conversation_id: int) -> SessionMemory | None:
        memory = self._states.get(conversation_id)
        return _clone(memory) if memory is not None else None

    async def create(self, memory: SessionMemory) -> SessionMemory:
        conversation_id = _conversation_id(memory)
        if conversation_id in self._states:
            raise ValueError(f"session state already exists: {conversation_id}")
        stored = _clone(memory)
        self._states[conversation_id] = stored
        return _clone(stored)

    async def save(self, memory: SessionMemory, *, expected_version: int) -> SessionMemory:
        conversation_id = _conversation_id(memory)
        current = self._states.get(conversation_id)
        if current is None:
            raise LookupError(f"session state not found: {conversation_id}")
        if current.state_version != expected_version:
            raise SessionStateVersionConflict(
                f"expected state version {expected_version}, got {current.state_version}"
            )
        stored = _clone(memory)
        self._states[conversation_id] = stored
        return _clone(stored)


def _conversation_id(memory: SessionMemory) -> int:
    if not isinstance(memory.conversation_id, int):
        raise TypeError("persisted SessionMemory conversation_id must be an integer")
    return memory.conversation_id


def _clone(memory: SessionMemory) -> SessionMemory:
    awaiting = memory.awaiting_action
    if awaiting is not None:
        awaiting = replace(awaiting, payload=deepcopy(dict(awaiting.payload)))
    return replace(
        memory,
        collected_data=deepcopy(dict(memory.collected_data)),
        awaiting_action=awaiting,
    )


# Transitional alias for imports from the earlier in-memory implementation.
MemorySessionStore = MemorySessionStateStore
