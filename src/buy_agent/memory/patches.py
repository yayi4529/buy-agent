from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypeVar, cast

from buy_agent.memory.models import AwaitingAction, RecommendationReference

T = TypeVar("T")


class UnsetType:
    __slots__ = ()


UNSET = UnsetType()


@dataclass(frozen=True)
class MemoryPatch:
    current_action: str | None | UnsetType = UNSET
    focused_role: str | None | UnsetType = UNSET
    current_stage: str | None | UnsetType = UNSET
    pending_field: str | None | UnsetType = UNSET
    collected_data_patch: Mapping[str, Any] | UnsetType = UNSET
    replace_missing_fields: tuple[str, ...] | UnsetType = UNSET
    replace_last_recommendations: tuple[RecommendationReference, ...] | UnsetType = UNSET
    awaiting_action: AwaitingAction | None | UnsetType = UNSET
    clear_awaiting_action: bool = False
    confirmed: bool | UnsetType = UNSET
    summary: str | UnsetType = UNSET

    def __post_init__(self) -> None:
        if self.clear_awaiting_action and is_set(self.awaiting_action):
            raise ValueError("cannot set and clear awaiting_action in the same patch")
        if is_set(self.collected_data_patch):
            value = cast(Mapping[str, Any], self.collected_data_patch)
            object.__setattr__(
                self,
                "collected_data_patch",
                MappingProxyType(dict(value)),
            )

    @classmethod
    def empty(cls) -> "MemoryPatch":
        return cls()

    @property
    def is_empty(self) -> bool:
        return not (
            is_set(self.current_action)
            or is_set(self.focused_role)
            or is_set(self.current_stage)
            or is_set(self.pending_field)
            or is_set(self.collected_data_patch)
            or is_set(self.replace_missing_fields)
            or is_set(self.replace_last_recommendations)
            or is_set(self.awaiting_action)
            or self.clear_awaiting_action
            or is_set(self.confirmed)
            or is_set(self.summary)
        )

    def merge(self, later: "MemoryPatch") -> "MemoryPatch":
        collected = _merge_collected(self.collected_data_patch, later.collected_data_patch)
        awaiting_action, clear_awaiting = _merge_awaiting(self, later)
        return MemoryPatch(
            current_action=_later(self.current_action, later.current_action),
            focused_role=_later(self.focused_role, later.focused_role),
            current_stage=_later(self.current_stage, later.current_stage),
            pending_field=_later(self.pending_field, later.pending_field),
            collected_data_patch=collected,
            replace_missing_fields=_later(
                self.replace_missing_fields, later.replace_missing_fields
            ),
            replace_last_recommendations=_later(
                self.replace_last_recommendations,
                later.replace_last_recommendations,
            ),
            awaiting_action=awaiting_action,
            clear_awaiting_action=clear_awaiting,
            confirmed=_later(self.confirmed, later.confirmed),
            summary=_later(self.summary, later.summary),
        )


def is_set(value: object) -> bool:
    return value is not UNSET


def _later(first: T | UnsetType, second: T | UnsetType) -> T | UnsetType:
    return second if is_set(second) else first


def _merge_collected(
    first: Mapping[str, Any] | UnsetType,
    second: Mapping[str, Any] | UnsetType,
) -> Mapping[str, Any] | UnsetType:
    if not is_set(first):
        return second
    if not is_set(second):
        return first
    merged = dict(cast(Mapping[str, Any], first))
    merged.update(cast(Mapping[str, Any], second))
    return merged


def _merge_awaiting(
    first: MemoryPatch,
    second: MemoryPatch,
) -> tuple[AwaitingAction | None | UnsetType, bool]:
    if second.clear_awaiting_action:
        return UNSET, True
    if is_set(second.awaiting_action):
        return second.awaiting_action, False
    return first.awaiting_action, first.clear_awaiting_action
