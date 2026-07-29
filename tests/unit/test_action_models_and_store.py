import asyncio

import pytest

from buy_agent.adapters.persistence.memory_action_execution_store import (
    MemoryActionExecutionStore,
)
from buy_agent.domain.action import (
    ActionCommand,
    ActionResult,
    ActionResultStatus,
    ActionType,
)
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.ports.action_execution_store import ActionStartStatus


def principal() -> CurrentPrincipal:
    return CurrentPrincipal(1, "requester", frozenset({"REQUESTER"}), (), (), "ACTIVE")


def test_action_command_validates_token_version_and_payload_boundary() -> None:
    command = ActionCommand(ActionType.SUBMIT_REQUEST, "token", 1, 0, principal())
    assert command.action == ActionType.SUBMIT_REQUEST
    with pytest.raises(ValueError, match="action_token"):
        ActionCommand(ActionType.SUBMIT_REQUEST, " ", 1, 0, principal())
    with pytest.raises(ValueError, match="state_version"):
        ActionCommand(ActionType.SUBMIT_REQUEST, "token", 1, -1, principal())
    with pytest.raises(ValueError, match="forbidden"):
        ActionCommand(
            ActionType.SUBMIT_REQUEST,
            "token",
            1,
            0,
            principal(),
            {"principal": {"roles": ["REQUESTER"]}},
        )


@pytest.mark.asyncio
async def test_action_execution_store_lifecycle_and_replay() -> None:
    store = MemoryActionExecutionStore()
    first = await store.try_start(
        action_token="token", action_type=ActionType.SUBMIT_REQUEST, conversation_id=1
    )
    processing = await store.try_start(
        action_token="token", action_type=ActionType.SUBMIT_REQUEST, conversation_id=1
    )
    assert first.status is ActionStartStatus.STARTED
    assert processing.status is ActionStartStatus.ALREADY_PROCESSING
    result = ActionResult(ActionResultStatus.SUCCESS, "OK", "done")
    await store.mark_completed(action_token="token", result=result)
    completed = await store.try_start(
        action_token="token", action_type=ActionType.SUBMIT_REQUEST, conversation_id=1
    )
    assert completed.status is ActionStartStatus.ALREADY_COMPLETED
    assert completed.record.result == result


@pytest.mark.asyncio
async def test_action_execution_store_failed_token_is_not_restarted() -> None:
    store = MemoryActionExecutionStore()
    await store.try_start(action_token="failed", action_type="SUBMIT_REQUEST", conversation_id=1)
    result = ActionResult(ActionResultStatus.BUSINESS_ERROR, "FAILED", "failed")
    await store.mark_failed(action_token="failed", error_code="FAILED", result=result)
    replay = await store.try_start(
        action_token="failed", action_type="SUBMIT_REQUEST", conversation_id=1
    )
    assert replay.status is ActionStartStatus.ALREADY_FAILED
    assert replay.record.result == result


@pytest.mark.asyncio
async def test_action_execution_store_same_token_starts_once_concurrently() -> None:
    store = MemoryActionExecutionStore()
    results = await asyncio.gather(
        *(
            store.try_start(action_token="same", action_type="SUBMIT_REQUEST", conversation_id=1)
            for _ in range(20)
        )
    )
    assert sum(item.status is ActionStartStatus.STARTED for item in results) == 1
