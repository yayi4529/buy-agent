from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway
from buy_agent.adapters.channels.fake_channel import FakeChannel
from buy_agent.adapters.llm.scripted_llm_client import ScriptedLLMClient
from buy_agent.adapters.persistence.local_lock_manager import LocalLockManager
from buy_agent.adapters.persistence.memory_conversation_store import (
    MemoryConversationStore,
)
from buy_agent.adapters.persistence.memory_event_store import MemoryEventStore
from buy_agent.adapters.persistence.memory_message_store import MemoryMessageStore
from buy_agent.adapters.persistence.memory_session_store import MemorySessionStateStore
from buy_agent.agent.procurement_agent import ProcurementAgent
from buy_agent.application.chat_orchestrator import ChatOrchestrator
from buy_agent.application.context_builder import ContextBuilder
from buy_agent.application.identity_service import IdentityService
from buy_agent.application.requirement_resolver import RequirementResolver
from buy_agent.application.session_service import SessionService, build_session_key
from buy_agent.application.tool_policy import ToolPolicy
from buy_agent.bootstrap.settings import Settings
from buy_agent.domain.agent import LLMResponse, ToolCall
from buy_agent.domain.enums import ChannelType, InboundEventType
from buy_agent.domain.events import InboundEvent
from buy_agent.domain.identity import ExternalIdentity
from buy_agent.tools.requester import build_requester_tool_registry


def event(index: int, text: str) -> InboundEvent:
    return InboundEvent(
        f"event-{index}",
        f"message-{index}",
        InboundEventType.TEXT_MESSAGE,
        ExternalIdentity(ChannelType.FEISHU, "tenant", "requester"),
        "chat-requester",
        text,
        None,
        {},
    )


async def test_three_turn_requester_draft_restores_memory_without_formal_request() -> None:
    backend = FakeBackendGateway()
    conversations = MemoryConversationStore()
    states = MemorySessionStateStore()
    messages = MemoryMessageStore()
    llm = ScriptedLLMClient(
        (
            LLMResponse(
                tool_calls=(
                    ToolCall(
                        "save_request_draft_fields",
                        {
                            "fields": {
                                "device_profession": "服务器",
                                "device_name": "服务器",
                                "quantity": 2,
                                "unit": "台",
                            }
                        },
                    ),
                )
            ),
            LLMResponse(content="请问采购设备放在哪栋楼？"),
            LLMResponse(tool_calls=(ToolCall("select_building", {"building_id": 1}),)),
            LLMResponse(content="请补充申请原因。"),
            LLMResponse(
                tool_calls=(
                    ToolCall(
                        "save_request_draft_fields",
                        {"fields": {"application_reason": "用于内部模型推理"}},
                    ),
                )
            ),
            LLMResponse(tool_calls=(ToolCall("prepare_request_submission", {}),)),
            LLMResponse(content="已生成采购申请提交确认，请确认后提交。"),
        )
    )
    agent = ProcurementAgent(
        llm=llm,
        registry=build_requester_tool_registry(),
        settings=Settings(),
    )
    session_service = SessionService(conversations, states, messages)
    orchestrator = ChatOrchestrator(
        identity_service=IdentityService(backend),
        session_service=session_service,
        requirement_resolver=RequirementResolver(backend),
        context_builder=ContextBuilder(),
        tool_policy=ToolPolicy(),
        agent=agent,
        channel=FakeChannel(),
        event_store=MemoryEventStore(),
        lock_manager=LocalLockManager(),
        backend_gateway=backend,
    )

    await orchestrator.handle(event(1, "我要采购两台服务器。"))
    await orchestrator.handle(event(2, "一号楼。"))
    await orchestrator.handle(event(3, "用于内部模型推理。"))

    conversation = await conversations.get_active_by_session_key(
        build_session_key(event(1, "").identity)
    )
    memory = await states.get(conversation.conversation_id)  # type: ignore[union-attr]
    assert memory is not None
    assert memory.collected_data["device_name"] == "服务器"
    assert memory.collected_data["quantity"] == 2
    assert memory.collected_data["building_id"] == 1
    assert memory.collected_data["application_reason"] == "用于内部模型推理"
    assert memory.purchase_request_id is None
    assert memory.confirmed is False
    assert memory.missing_fields == ()
    assert memory.pending_field is None
    assert memory.awaiting_action is not None
    assert backend.create_purchase_request_call_count == 0
