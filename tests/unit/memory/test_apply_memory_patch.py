from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from buy_agent.memory import (
    AwaitingAction,
    MemoryPatch,
    RecommendationReference,
    SessionMemory,
    apply_memory_patch,
)


def complete_data() -> dict[str, object]:
    return {
        "building_id": 10,
        "device_profession": "网络",
        "device_name": "交换机",
        "quantity": 5,
        "unit": "台",
        "application_reason": "网络扩容",
    }


def recommendation() -> RecommendationReference:
    return RecommendationReference(1, "rec-1", "device", "device-1", "交换机")


def awaiting() -> AwaitingAction:
    return AwaitingAction(
        "CONFIRM_CREATE_REQUEST",
        "system-token",
        "interaction-1",
        1,
        datetime(2030, 1, 1, tzinfo=UTC),
        {"view": "confirm"},
    )


def create_memory(**overrides: object) -> SessionMemory:
    values: dict[str, object] = {
        "conversation_id": "conversation-1",
        "current_action": "CREATE_REQUEST",
    }
    values.update(overrides)
    return SessionMemory(**values)  # type: ignore[arg-type]


def test_draft_update_recalculates_missing_and_pending_field() -> None:
    memory = create_memory()
    updated = apply_memory_patch(
        memory,
        MemoryPatch(collected_data_patch={"building_id": 1, "device_name": "交换机"}),
    )
    assert updated.missing_fields == (
        "device_profession",
        "quantity",
        "unit",
        "application_reason",
    )
    assert updated.pending_field == "device_profession"


def test_new_create_memory_calculates_initial_missing_fields() -> None:
    memory = create_memory()
    assert memory.missing_fields == (
        "building_id",
        "device_profession",
        "device_name",
        "quantity",
        "unit",
        "application_reason",
    )
    assert memory.pending_field == "building_id"


def test_complete_fields_clear_pending_field() -> None:
    updated = apply_memory_patch(
        create_memory(),
        MemoryPatch(collected_data_patch=complete_data()),
    )
    assert updated.missing_fields == ()
    assert updated.pending_field is None


def test_draft_change_resets_confirmation_and_old_awaiting_action() -> None:
    memory = create_memory(
        collected_data={"quantity": 1},
        confirmed=True,
        awaiting_action=awaiting(),
    )
    updated = apply_memory_patch(
        memory,
        MemoryPatch(collected_data_patch={"quantity": 2}),
    )
    assert updated.confirmed is False
    assert updated.awaiting_action is None


def test_valid_patch_increments_version_but_empty_patch_does_not() -> None:
    memory = create_memory(state_version=3)
    assert apply_memory_patch(memory, MemoryPatch(summary="new")).state_version == 4
    assert apply_memory_patch(memory, MemoryPatch.empty()).state_version == 3


def test_switching_action_clears_recommendations_and_awaiting_action() -> None:
    memory = create_memory(
        last_recommendations=(recommendation(),),
        awaiting_action=awaiting(),
    )
    updated = apply_memory_patch(memory, MemoryPatch(current_action="QUERY_REQUEST"))
    assert updated.last_recommendations == ()
    assert updated.awaiting_action is None


def test_instances_do_not_share_collected_data() -> None:
    first = create_memory()
    second = create_memory(conversation_id="conversation-2")
    updated = apply_memory_patch(first, MemoryPatch(collected_data_patch={"quantity": 1}))
    assert dict(second.collected_data) == {}
    assert dict(updated.collected_data) == {"quantity": 1}


def test_memory_and_nested_collections_are_immutable() -> None:
    memory = create_memory(collected_data={"quantity": 1})
    with pytest.raises(FrozenInstanceError):
        memory.confirmed = True  # type: ignore[misc]
    with pytest.raises(TypeError):
        memory.collected_data["quantity"] = 2  # type: ignore[index]


def test_invalid_patch_is_atomic_and_does_not_overwrite_memory() -> None:
    memory = create_memory(collected_data={"quantity": 2})
    with pytest.raises(ValidationError):
        apply_memory_patch(memory, MemoryPatch(collected_data_patch={"quantity": 0}))
    assert memory.collected_data["quantity"] == 2


def test_create_request_must_not_have_formal_request_id() -> None:
    with pytest.raises(ValueError, match="must be empty"):
        create_memory(purchase_request_id=123)
