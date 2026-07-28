from dataclasses import replace
from typing import Any, TypeVar, cast

from buy_agent.memory.draft_fields import apply_create_request_patch
from buy_agent.memory.missing_fields import (
    resolve_create_request_missing_fields,
    resolve_next_pending_field,
)
from buy_agent.memory.models import (
    AwaitingAction,
    CreateRequestDraft,
    SessionMemory,
)
from buy_agent.memory.patches import MemoryPatch, UnsetType, is_set

T = TypeVar("T")


def apply_memory_patch(memory: SessionMemory, patch: MemoryPatch) -> SessionMemory:
    if patch.is_empty:
        return memory

    action = _value(patch.current_action, memory.current_action)
    action_changed = is_set(patch.current_action) and action != memory.current_action
    collected_data = dict(memory.collected_data)
    draft_changed = is_set(patch.collected_data_patch)
    if draft_changed:
        draft = CreateRequestDraft.model_validate(collected_data)
        field_patch = dict(cast(dict[str, Any], patch.collected_data_patch))
        collected_data = apply_create_request_patch(draft, field_patch).model_dump(
            exclude_none=True
        )

    missing_fields = _value(patch.replace_missing_fields, memory.missing_fields)
    pending_field = _value(patch.pending_field, memory.pending_field)
    if action == "CREATE_REQUEST":
        draft = CreateRequestDraft.model_validate(collected_data)
        missing_fields = resolve_create_request_missing_fields(draft)
        pending_field = resolve_next_pending_field(missing_fields)

    recommendations = _value(
        patch.replace_last_recommendations,
        memory.last_recommendations,
    )
    awaiting = _resolve_awaiting(memory.awaiting_action, patch)
    if draft_changed and not is_set(patch.awaiting_action):
        awaiting = None
    if action_changed:
        recommendations = ()
        awaiting = None

    confirmed = _value(patch.confirmed, memory.confirmed)
    if draft_changed:
        confirmed = False

    return replace(
        memory,
        current_action=action,
        focused_role=_value(patch.focused_role, memory.focused_role),
        current_stage=_value(patch.current_stage, memory.current_stage),
        pending_field=pending_field,
        collected_data=collected_data,
        missing_fields=missing_fields,
        last_recommendations=recommendations,
        awaiting_action=awaiting,
        confirmed=confirmed,
        state_version=memory.state_version + 1,
        summary=_value(patch.summary, memory.summary),
    )


def _value(value: T | UnsetType, fallback: T) -> T:
    return cast(T, value) if is_set(value) else fallback


def _resolve_awaiting(
    current: AwaitingAction | None,
    patch: MemoryPatch,
) -> AwaitingAction | None:
    if patch.clear_awaiting_action:
        return None
    return _value(patch.awaiting_action, current)
