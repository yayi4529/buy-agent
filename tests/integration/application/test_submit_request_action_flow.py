from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway
from buy_agent.adapters.persistence.local_lock_manager import LocalLockManager
from buy_agent.adapters.persistence.memory_action_execution_store import (
    MemoryActionExecutionStore,
)
from buy_agent.adapters.persistence.memory_conversation_store import MemoryConversationStore
from buy_agent.adapters.persistence.memory_message_store import MemoryMessageStore
from buy_agent.adapters.persistence.memory_session_store import MemorySessionStateStore
from buy_agent.application.action_orchestrator import ActionOrchestrator
from buy_agent.application.session_service import SessionService
from buy_agent.domain.action import ActionCommand, ActionResultStatus, ActionType
from buy_agent.domain.conversation import ConversationStatus
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.memory import AwaitingAction


async def setup_flow(
    *, backend: FakeBackendGateway | None = None
) -> tuple[
    ActionOrchestrator,
    ActionCommand,
    SessionService,
    FakeBackendGateway,
    MemoryActionExecutionStore,
]:
    backend = backend or FakeBackendGateway()
    conversations = MemoryConversationStore()
    states = MemorySessionStateStore()
    service = SessionService(conversations, states, MemoryMessageStore())
    principal = CurrentPrincipal(1, "requester", frozenset({"REQUESTER"}), (), (), "ACTIVE")
    bundle = await service.get_or_create(
        session_key="procurement:WEB:t:u",
        principal=principal,
        platform_type="WEB",
        external_conversation_id="chat",
    )
    version = bundle.memory.state_version + 1
    awaiting = AwaitingAction(
        "submit_request",
        "action-token",
        "interaction",
        version,
        datetime.now(UTC) + timedelta(minutes=30),
        {"reviewer_employee_id": 101},
    )
    memory = replace(
        bundle.memory,
        collected_data={
            "building_id": 1,
            "device_profession": "IT",
            "device_name": "Server",
            "brand": "Dell",
            "model": "R760",
            "quantity": 2,
            "unit": "台",
            "application_reason": "Capacity",
            "applicant_remark": None,
        },
        awaiting_action=awaiting,
        state_version=version,
    )
    await states.save(memory, expected_version=bundle.memory.state_version)
    executions = MemoryActionExecutionStore()
    orchestrator = ActionOrchestrator(
        session_service=service,
        backend_gateway=backend,
        action_execution_store=executions,
        lock_manager=LocalLockManager(),
    )
    command = ActionCommand(
        ActionType.SUBMIT_REQUEST,
        "action-token",
        bundle.conversation.conversation_id,
        version,
        principal,
    )
    return orchestrator, command, service, backend, executions


@pytest.mark.asyncio
async def test_submit_request_success_and_duplicate_click() -> None:
    orchestrator, command, service, backend, _ = await setup_flow()
    first = await orchestrator.handle(command)
    second = await orchestrator.handle(command)
    assert first.status is ActionResultStatus.SUCCESS
    assert second == first
    assert first.data is not None
    assert first.data["request_no"] == "MOCK-PR-000001"
    assert backend.create_purchase_request_call_count == 1
    bundle = await service.get_by_conversation_id(command.conversation_id)
    assert bundle is not None
    assert bundle.conversation.status is ConversationStatus.COMPLETED
    assert bundle.conversation.purchase_request_id == first.data["request_id"]
    assert bundle.memory.purchase_request_id == first.data["request_id"]
    assert bundle.memory.confirmed is True
    assert bundle.memory.awaiting_action is None


@pytest.mark.asyncio
async def test_stale_version_does_not_create_request() -> None:
    orchestrator, command, service, backend, _ = await setup_flow()
    stale = replace(command, expected_state_version=command.expected_state_version - 1)
    result = await orchestrator.handle(stale)
    assert result.status is ActionResultStatus.VERSION_CONFLICT
    assert backend.create_purchase_request_call_count == 0
    bundle = await service.get_by_conversation_id(command.conversation_id)
    assert bundle is not None
    assert bundle.conversation.status is ConversationStatus.ACTIVE
    assert bundle.conversation.purchase_request_id is None


@pytest.mark.asyncio
async def test_invalid_reviewer_does_not_create_request() -> None:
    orchestrator, command, _, backend, _ = await setup_flow()
    command = replace(command, payload={"reviewer_employee_id": 999})
    result = await orchestrator.handle(command)
    assert result.status is ActionResultStatus.BUSINESS_ERROR
    assert result.code == "INVALID_REVIEWER"
    assert backend.create_purchase_request_call_count == 0


@pytest.mark.asyncio
async def test_backend_failure_marks_action_failed_without_completing_session() -> None:
    orchestrator, command, service, backend, executions = await setup_flow(
        backend=FakeBackendGateway(create_failure="business")
    )
    first = await orchestrator.handle(command)
    second = await orchestrator.handle(command)
    assert first.status is ActionResultStatus.BUSINESS_ERROR
    assert second == first
    assert backend.create_purchase_request_call_count == 1
    record = await executions.get(command.action_token)
    assert record is not None
    assert record.error_code == "BACKEND_VALIDATION_ERROR"
    bundle = await service.get_by_conversation_id(command.conversation_id)
    assert bundle is not None
    assert bundle.conversation.status is ConversationStatus.ACTIVE
    assert bundle.memory.confirmed is False
