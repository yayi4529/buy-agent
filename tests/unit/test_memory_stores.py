from buy_agent.adapters.persistence.memory_event_store import MemoryEventStore
from buy_agent.adapters.persistence.memory_message_store import MemoryMessageStore
from buy_agent.adapters.persistence.memory_session_store import MemorySessionStore
from buy_agent.domain.conversation import SessionState


async def test_session_store_saves_reads_isolates_and_deep_copies() -> None:
    store = MemorySessionStore()
    first = SessionState("first", 1, recent_messages=[{"role": "user", "content": "one"}])
    second = SessionState("second", 2)
    await store.save(first)
    await store.save(second)

    loaded = await store.get("first")
    assert loaded == first
    assert loaded is not first
    assert loaded is not None
    loaded.recent_messages[0]["content"] = "changed"

    reloaded = await store.get("first")
    assert reloaded is not None
    assert reloaded.recent_messages[0]["content"] == "one"
    assert (await store.get("second")).user_id == 2  # type: ignore[union-attr]


async def test_message_store_isolates_keys_limits_results_and_returns_copies() -> None:
    store = MemoryMessageStore()
    for index in range(4):
        await store.append("first", "user", str(index))
    await store.append("second", "user", "other")

    recent = await store.recent("first", limit=2)
    assert [message["content"] for message in recent] == ["2", "3"]
    recent[0]["content"] = "changed"
    assert [message["content"] for message in await store.recent("first", 2)] == ["2", "3"]
    assert await store.recent("second") == [{"role": "user", "content": "other"}]


async def test_event_store_deduplicates_event_and_message_ids_independently() -> None:
    store = MemoryEventStore()
    assert not await store.is_duplicate(event_id="event-1", message_id="message-1")
    await store.mark_completed(event_id="event-1", message_id="message-1")

    assert await store.is_duplicate(event_id="event-1", message_id="message-2")
    assert await store.is_duplicate(event_id="event-2", message_id="message-1")
    assert not await store.is_duplicate(event_id="event-2", message_id="message-2")


async def test_event_store_allows_distinct_events_without_message_id() -> None:
    store = MemoryEventStore()
    await store.mark_completed(event_id="event-1", message_id=None)

    assert await store.is_duplicate(event_id="event-1", message_id=None)
    assert not await store.is_duplicate(event_id="event-2", message_id=None)
