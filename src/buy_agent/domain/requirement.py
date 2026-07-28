from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequirementContext:
    requirement_id: int
    requirement_no: str
    status: str
    version: int
    requester_fields: dict[str, Any]
    reviewer_fields: dict[str, Any]
    purchaser_fields: dict[str, Any]
    warehouse_fields: dict[str, Any]
    missing_fields: tuple[str, ...]
    next_missing_field: str | None
    allowed_actions: tuple[str, ...]


@dataclass(frozen=True)
class RequirementResolution:
    requirement: RequirementContext | None
    needs_selection: bool = False
    candidates: tuple[RequirementContext, ...] = ()
