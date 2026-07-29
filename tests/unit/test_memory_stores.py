from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from buy_agent.adapters.persistence.memory_conversation_store import (
    MemoryConversationStore,
)
from buy_agent.adapters.persistence.memory_event_store import (
    EventProcessingStatus,
    MemoryEventStore,
)
from buy_agent.adapters.persistence.memory_message_store import (
    DuplicateExternalMessageError,
    MemoryMessageStore,
)
from buy_agent.adapters.persistence.memory_session_store import (
    MemorySessionStateStore,
)
from buy_agent.domain.conversation import (
    MessageSenderType,
    NewAgentConversation,
    NewConversationMessage,
)
from buy_agent.memory import MemoryPatch, SessionMemory, apply_memory_patch
from buy_agent.ports.session_store import SessionStateVersionConflict


async def test_conversation_store_create_lookup_isolation_and_activity() -> None:
    store = MemoryConversationStore()
    assert await store.get_active_by_session_key("missing") is None
    first = await store.create(NewAgentConversation("a", 1, "WEB"))
    await store.create(NewAgentConversation("b", 2, "WEB"))
    assert first.purchase_request_id is None
    assert (await store.get_active_by_session_key("a")) == first
    old_time = first.last_active_at
    await store.update_last_active(first.conversation_id)
    assert (await store.get_by_id(first.conversation_id)).last_active_at >= old_time  # type: ignore[union-attr]
    assert (await store.get_active_by_session_key("b")).employee_id == 2  # type: ignore[union-attr]


async def test_state_store_versions_isolation_and_safe_copy() -> None:
    store = MemorySessionStateStore()
    first = await store.create(SessionMemory(1, current_action="CREATE_REQUEST"))
    await store.create(SessionMemory(2, current_action="CREATE_REQUEST"))
    updated = apply_memory_patch(first, MemoryPatch(collected_data_patch={"quantity": 2}))
    saved = await store.save(updated, expected_version=0)
    assert saved.state_version == 1
    assert (await store.get(2)).collected_data == {}  # type: ignore[union-attr]
    mutable = dict(saved.collected_data)
    mutable["quantity"] = 99
    assert (await store.get(1)).collected_data["quantity"] == 2  # type: ignore[union-attr]
    with pytest.raises(SessionStateVersionConflict):
        await store.save(replace(updated, state_version=2), expected_version=0)


async def test_message_store_order_limit_isolation_and_duplicate() -> None:
    store = MemoryMessageStore()
    now = datetime.now(UTC)
    await store.append(NewConversationMessage(1, MessageSenderType.USER, "later", "m1", now))
    await store.append(
        NewConversationMessage(
            1, MessageSenderType.AGENT, "earlier", None, now - timedelta(seconds=1)
        )
    )
    await store.append(NewConversationMessage(2, MessageSenderType.USER, "other"))
    recent = await store.list_recent(1, limit=1)
    assert [item.content for item in recent] == ["later"]
    assert [item.content for item in await store.list_recent(2, limit=5)] == ["other"]
    with pytest.raises(DuplicateExternalMessageError):
        await store.append(NewConversationMessage(1, MessageSenderType.USER, "dup", "m1"))


async def test_event_store_lifecycle_and_deduplication() -> None:
    store = MemoryEventStore()
    assert await store.try_start(event_id="e1", message_id="m1")
    assert not await store.try_start(event_id="e1", message_id="m2")
    assert not await store.try_start(event_id="e2", message_id="m1")
    await store.mark_completed("e1")
    assert (await store.get("e1")).status is EventProcessingStatus.COMPLETED  # type: ignore[union-attr]
    assert await store.try_start(event_id="e3", message_id=None)
    await store.mark_failed("e3", "FAILED")
    assert (await store.get("e3")).status is EventProcessingStatus.FAILED  # type: ignore[union-attr]
