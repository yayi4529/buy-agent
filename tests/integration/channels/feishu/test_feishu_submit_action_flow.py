from dataclasses import replace
from datetime import UTC, datetime, timedelta

from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway
from buy_agent.adapters.channels.feishu import (
    FakeFeishuClient,
    FeishuActionAdapter,
    FeishuActionHandler,
    FeishuActionResultRenderer,
)
from buy_agent.adapters.persistence.local_lock_manager import LocalLockManager
from buy_agent.adapters.persistence.memory_action_execution_store import (
    MemoryActionExecutionStore,
)
from buy_agent.adapters.persistence.memory_conversation_store import MemoryConversationStore
from buy_agent.adapters.persistence.memory_message_store import MemoryMessageStore
from buy_agent.adapters.persistence.memory_session_store import MemorySessionStateStore
from buy_agent.application.action_orchestrator import ActionOrchestrator
from buy_agent.application.identity_service import IdentityService
from buy_agent.application.session_service import SessionService
from buy_agent.domain.conversation import ConversationStatus
from buy_agent.memory import AwaitingAction


async def test_feishu_submit_callback_is_idempotent_and_updates_card() -> None:
    backend = FakeBackendGateway()
    state_store = MemorySessionStateStore()
    sessions = SessionService(MemoryConversationStore(), state_store, MemoryMessageStore())
    principal = backend.principals["requester"]
    bundle = await sessions.get_or_create(
        session_key="procurement:FEISHU:tenant:requester",
        principal=principal,
        platform_type="FEISHU",
        external_conversation_id="chat",
    )
    version = bundle.memory.state_version + 1
    await state_store.save(
        replace(
            bundle.memory,
            collected_data={
                "building_id": 1,
                "device_profession": "IT",
                "device_name": "服务器",
                "brand": "Dell",
                "model": "R760",
                "quantity": 2,
                "unit": "台",
                "application_reason": "模型推理",
                "applicant_remark": None,
            },
            awaiting_action=AwaitingAction(
                "submit_request",
                "token-1",
                "card-1",
                version,
                datetime.now(UTC) + timedelta(minutes=30),
                {"reviewer_employee_id": 101},
            ),
            state_version=version,
        ),
        expected_version=bundle.memory.state_version,
    )
    orchestrator = ActionOrchestrator(
        session_service=sessions,
        backend_gateway=backend,
        action_execution_store=MemoryActionExecutionStore(),
        lock_manager=LocalLockManager(),
    )
    client = FakeFeishuClient()
    handler = FeishuActionHandler(
        action_adapter=FeishuActionAdapter(),
        identity_service=IdentityService(backend),
        orchestrator=orchestrator,
        renderer=FeishuActionResultRenderer(),
        client=client,  # type: ignore[arg-type]
    )
    callback = {
        "header": {"event_id": "callback-1", "tenant_key": "tenant"},
        "event": {
            "operator": {"operator_id": {"open_id": "requester"}},
            "context": {"open_message_id": "card-1"},
            "action": {
                "value": {
                    "action": "SUBMIT_REQUEST",
                    "action_token": "token-1",
                    "conversation_id": bundle.conversation.conversation_id,
                    "expected_state_version": version,
                }
            },
        },
    }
    first = await handler.handle(callback)
    callback["header"]["event_id"] = "callback-2"  # type: ignore[index]
    second = await handler.handle(callback)
    assert first.interaction_updated and second.interaction_updated
    assert backend.create_purchase_request_call_count == 1
    assert len(client.update_interaction_calls) == 2
    assert "MOCK-PR-000001" in str(client.last_interaction.payload)
    saved = await sessions.get_by_conversation_id(bundle.conversation.conversation_id)
    assert saved is not None
    assert saved.conversation.status is ConversationStatus.COMPLETED
    assert saved.memory.confirmed is True
