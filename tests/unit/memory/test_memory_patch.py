from datetime import UTC, datetime

import pytest

from buy_agent.memory import (
    AwaitingAction,
    MemoryPatch,
    RecommendationReference,
    SessionMemory,
    apply_memory_patch,
)


def recommendation(name: str = "交换机") -> RecommendationReference:
    return RecommendationReference(1, "rec-1", "device", "device-1", name)


def awaiting() -> AwaitingAction:
    return AwaitingAction(
        action_type="CONFIRM_CREATE_REQUEST",
        action_token="system-token",
        interaction_id="interaction-1",
        expected_state_version=1,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        payload={"view": "confirm"},
    )


def test_empty_patch_is_empty_and_does_not_change_memory() -> None:
    memory = SessionMemory("conversation-1")
    assert MemoryPatch.empty().is_empty
    assert apply_memory_patch(memory, MemoryPatch.empty()) is memory
    assert not MemoryPatch(current_stage=None).is_empty


def test_merge_combines_collected_data_and_later_scalar_wins() -> None:
    first = MemoryPatch(
        current_stage="FIRST",
        collected_data_patch={"brand": "旧品牌", "quantity": 1},
    )
    later = MemoryPatch(
        current_stage=None,
        collected_data_patch={"brand": "新品牌", "unit": "台"},
    )
    merged = first.merge(later)
    assert merged.current_stage is None
    assert dict(merged.collected_data_patch) == {
        "brand": "新品牌",
        "quantity": 1,
        "unit": "台",
    }


def test_replace_fields_use_complete_replacement_semantics() -> None:
    merged = MemoryPatch(
        replace_missing_fields=("quantity", "unit"),
        replace_last_recommendations=(recommendation(),),
    ).merge(
        MemoryPatch(
            replace_missing_fields=(),
            replace_last_recommendations=(),
        )
    )
    assert merged.replace_missing_fields == ()
    assert merged.replace_last_recommendations == ()


def test_cannot_set_and_clear_awaiting_action_together() -> None:
    with pytest.raises(ValueError, match="set and clear"):
        MemoryPatch(awaiting_action=awaiting(), clear_awaiting_action=True)


def test_patch_cannot_modify_identity_or_formal_request_id() -> None:
    with pytest.raises(TypeError):
        MemoryPatch(conversation_id="other")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        MemoryPatch(purchase_request_id=1)  # type: ignore[call-arg]


def test_awaiting_action_rejects_sensitive_payload() -> None:
    with pytest.raises(ValueError, match="sensitive"):
        AwaitingAction(
            "CONFIRM",
            "system-token",
            "interaction",
            0,
            datetime(2030, 1, 1, tzinfo=UTC),
            {"nested": {"password": "do-not-store"}},
        )
