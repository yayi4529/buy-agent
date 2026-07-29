from collections.abc import Iterable
from typing import Any

from buy_agent.memory.models import CreateRequestDraft

CREATE_REQUEST_REQUIRED_FIELDS = (
    "building_id",
    "device_profession",
    "device_name",
    "quantity",
    "unit",
    "application_reason",
)


def _is_missing(value: Any) -> bool:
    return value is None or isinstance(value, str) and not value.strip()


def resolve_create_request_missing_fields(
    draft: CreateRequestDraft,
) -> tuple[str, ...]:
    return tuple(
        field_name
        for field_name in CREATE_REQUEST_REQUIRED_FIELDS
        if _is_missing(getattr(draft, field_name))
    )


def resolve_next_pending_field(missing_fields: Iterable[str]) -> str | None:
    return next(iter(missing_fields), None)
