from collections.abc import Mapping
from typing import Any

from buy_agent.memory.models import CreateRequestDraft


def apply_create_request_patch(
    current_draft: CreateRequestDraft,
    field_patch: Mapping[str, Any],
) -> CreateRequestDraft:
    merged = current_draft.model_dump()
    merged.update(field_patch)
    return CreateRequestDraft.model_validate(merged)
