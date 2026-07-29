import asyncio
from dataclasses import replace
from datetime import UTC, datetime

from buy_agent.domain.action import ActionResult
from buy_agent.ports.action_execution_store import (
    ActionExecutionRecord,
    ActionExecutionStatus,
    ActionStartResult,
    ActionStartStatus,
)


class MemoryActionExecutionStore:
    def __init__(self) -> None:
        self._records: dict[str, ActionExecutionRecord] = {}
        self._index_lock = asyncio.Lock()

    async def try_start(
        self, *, action_token: str, action_type: str, conversation_id: int
    ) -> ActionStartResult:
        async with self._index_lock:
            current = self._records.get(action_token)
            if current is not None:
                status = {
                    ActionExecutionStatus.PROCESSING: ActionStartStatus.ALREADY_PROCESSING,
                    ActionExecutionStatus.COMPLETED: ActionStartStatus.ALREADY_COMPLETED,
                    ActionExecutionStatus.FAILED: ActionStartStatus.ALREADY_FAILED,
                }[current.status]
                return ActionStartResult(status, current)
            now = datetime.now(UTC)
            record = ActionExecutionRecord(
                action_token,
                action_type,
                conversation_id,
                ActionExecutionStatus.PROCESSING,
                now,
                now,
            )
            self._records[action_token] = record
            return ActionStartResult(ActionStartStatus.STARTED, record)

    async def mark_completed(self, *, action_token: str, result: ActionResult) -> None:
        await self._finish(action_token, ActionExecutionStatus.COMPLETED, result, None)

    async def mark_failed(
        self, *, action_token: str, error_code: str, result: ActionResult
    ) -> None:
        await self._finish(action_token, ActionExecutionStatus.FAILED, result, error_code)

    async def get(self, action_token: str) -> ActionExecutionRecord | None:
        async with self._index_lock:
            return self._records.get(action_token)

    async def _finish(
        self,
        action_token: str,
        status: ActionExecutionStatus,
        result: ActionResult,
        error_code: str | None,
    ) -> None:
        async with self._index_lock:
            current = self._records.get(action_token)
            if current is None:
                raise LookupError(f"action execution not found: {action_token}")
            if current.status is not ActionExecutionStatus.PROCESSING:
                raise RuntimeError(f"action execution is already final: {action_token}")
            self._records[action_token] = replace(
                current,
                status=status,
                updated_at=datetime.now(UTC),
                result=result,
                error_code=error_code,
            )
