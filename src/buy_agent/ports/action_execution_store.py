from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from buy_agent.domain.action import ActionResult


class ActionExecutionStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ActionStartStatus(StrEnum):
    STARTED = "STARTED"
    ALREADY_PROCESSING = "ALREADY_PROCESSING"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    ALREADY_FAILED = "ALREADY_FAILED"


@dataclass(frozen=True)
class ActionExecutionRecord:
    action_token: str
    action_type: str
    conversation_id: int
    status: ActionExecutionStatus
    started_at: datetime
    updated_at: datetime
    result: ActionResult | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class ActionStartResult:
    status: ActionStartStatus
    record: ActionExecutionRecord


class ActionExecutionStore(Protocol):
    async def try_start(
        self, *, action_token: str, action_type: str, conversation_id: int
    ) -> ActionStartResult: ...

    async def mark_completed(self, *, action_token: str, result: ActionResult) -> None: ...

    async def mark_failed(
        self, *, action_token: str, error_code: str, result: ActionResult
    ) -> None: ...

    async def get(self, action_token: str) -> ActionExecutionRecord | None: ...
