from datetime import UTC, datetime

from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway
from buy_agent.adapters.llm.scripted_llm_client import ScriptedLLMClient
from buy_agent.agent.procurement_agent import ProcurementAgent
from buy_agent.bootstrap.settings import Settings
from buy_agent.domain.agent import LLMResponse, ToolCall
from buy_agent.domain.conversation import AgentRuntimeContext, SessionState
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.memory import AwaitingAction, SessionMemory, apply_memory_patch
from buy_agent.tools.requester import (
    REQUESTER_TOOL_NAMES,
    build_requester_tool_registry,
)


class FixedTokenFactory:
    def create(self) -> str:
        return "integration-token"


def runtime(
    backend: FakeBackendGateway,
    value: SessionMemory,
    user_id: int = 1,
) -> AgentRuntimeContext:
    session_key = f"procurement:test:t:{user_id}"
    return AgentRuntimeContext(
        principal=CurrentPrincipal(
            user_id,
            f"user-{user_id}",
            frozenset({"REQUESTER"}),
            (),
            (),
            "ACTIVE",
        ),
        session=SessionState(session_key, user_id),
        requirement=None,
        available_tool_names=REQUESTER_TOOL_NAMES,
        trace_id="trace",
        event_id="event",
        session_key=session_key,
        memory=value,
        backend_gateway=backend,
    )


async def test_single_building_draft_flow_uses_working_memory_only() -> None:
    backend = FakeBackendGateway()
    llm = ScriptedLLMClient(
        (
            LLMResponse(
                tool_calls=(
                    ToolCall(
                        "save_request_draft_fields",
                        {
                            "fields": {
                                "device_profession": "服务器",
                                "device_name": "机架式服务器",
                                "brand": "戴尔",
                                "model": "PowerEdge R760",
                                "quantity": 2,
                                "unit": "台",
                                "application_reason": "模型推理",
                            }
                        },
                    ),
                )
            ),
            LLMResponse(tool_calls=(ToolCall("list_available_buildings", {}),)),
            LLMResponse(tool_calls=(ToolCall("prepare_request_submission", {}),)),
            LLMResponse(content="请确认提交。"),
        )
    )
    initial = SessionMemory("conversation-1", current_action="CREATE_REQUEST")
    subject = ProcurementAgent(
        llm=llm,
        registry=build_requester_tool_registry(FixedTokenFactory()),
        settings=Settings(agent_max_rounds=6, agent_max_tool_calls=5),
    )
    result = await subject.run("我要采购两台戴尔 R760，用于模型推理。", runtime(backend, initial))

    updated = apply_memory_patch(initial, result.memory_patch)  # type: ignore[arg-type]
    assert updated.collected_data["building_id"] == 1
    assert updated.missing_fields == ()
    assert result.tool_results[-1].interaction is not None
    assert initial.collected_data == {}
    assert initial.state_version == 0
    assert updated.purchase_request_id is None
    assert backend.create_purchase_request_call_count == 0
    assert backend.formal_action_call_count == 0


async def test_tool_failure_does_not_pollute_working_memory() -> None:
    backend = FakeBackendGateway()
    llm = ScriptedLLMClient(
        (
            LLMResponse(tool_calls=(ToolCall("select_building", {"building_id": 999}),)),
            LLMResponse(tool_calls=(ToolCall("prepare_request_submission", {}),)),
            LLMResponse(content="请补充楼宇。"),
        )
    )
    initial = SessionMemory("conversation-1", current_action="CREATE_REQUEST")
    subject = ProcurementAgent(
        llm=llm,
        registry=build_requester_tool_registry(),
        settings=Settings(agent_max_rounds=5, agent_max_tool_calls=4),
    )
    result = await subject.run("选 999 号楼", runtime(backend, initial))
    assert result.tool_results[0].code == "PERMISSION_DENIED"
    assert result.tool_results[1].data["pending_field"] == "building_id"  # type: ignore[index]
    assert result.memory_patch is None


async def test_multi_building_user_must_select_legal_building() -> None:
    backend = FakeBackendGateway()
    initial = SessionMemory(
        "conversation-6",
        current_action="CREATE_REQUEST",
        collected_data={
            "device_profession": "服务器",
            "device_name": "服务器",
            "quantity": 1,
            "unit": "台",
            "application_reason": "测试",
        },
    )
    first = ProcurementAgent(
        llm=ScriptedLLMClient(
            (
                LLMResponse(tool_calls=(ToolCall("list_available_buildings", {}),)),
                LLMResponse(content="请选择一号楼或二号楼。"),
            )
        ),
        registry=build_requester_tool_registry(),
        settings=Settings(4, 3),
    )
    listed = await first.run("可选哪个楼？", runtime(backend, initial, 6))
    assert listed.memory_patch is None
    assert len(listed.tool_results[0].data["buildings"]) == 2  # type: ignore[index]

    second = ProcurementAgent(
        llm=ScriptedLLMClient(
            (
                LLMResponse(tool_calls=(ToolCall("select_building", {"building_id": 1}),)),
                LLMResponse(content="已选择一号楼。"),
            )
        ),
        registry=build_requester_tool_registry(),
        settings=Settings(4, 3),
    )
    selected = await second.run("一号楼", runtime(backend, initial, 6))
    updated = apply_memory_patch(initial, selected.memory_patch)  # type: ignore[arg-type]
    assert updated.collected_data["building_id"] == 1
    assert backend.create_purchase_request_call_count == 0


async def test_recommend_then_select_flow_uses_backend_product() -> None:
    backend = FakeBackendGateway()
    initial = SessionMemory(
        "conversation-1",
        current_action="CREATE_REQUEST",
        collected_data={"quantity": 2, "application_reason": "模型推理"},
    )
    recommender = ProcurementAgent(
        llm=ScriptedLLMClient(
            (
                LLMResponse(
                    tool_calls=(ToolCall("recommend_products", {"query": "服务器", "limit": 3}),)
                ),
                LLMResponse(content="有三项候选，请选择。"),
            )
        ),
        registry=build_requester_tool_registry(),
        settings=Settings(4, 3),
    )
    recommended = await recommender.run("推荐服务器", runtime(backend, initial))
    with_recommendations = apply_memory_patch(initial, recommended.memory_patch)  # type: ignore[arg-type]

    selector = ProcurementAgent(
        llm=ScriptedLLMClient(
            (
                LLMResponse(
                    tool_calls=(ToolCall("select_product_recommendation", {"selection_index": 1}),)
                ),
                LLMResponse(content="已选择第一项。"),
            )
        ),
        registry=build_requester_tool_registry(),
        settings=Settings(4, 3),
    )
    selected = await selector.run("第一个", runtime(backend, with_recommendations))
    updated = apply_memory_patch(with_recommendations, selected.memory_patch)  # type: ignore[arg-type]
    assert updated.collected_data["brand"] == backend.products[0].brand
    assert updated.collected_data["model"] == backend.products[0].model
    assert updated.last_recommendations == ()


async def test_edit_after_confirmation_invalidates_old_action() -> None:
    backend = FakeBackendGateway()
    awaiting = AwaitingAction(
        "submit_request",
        "old-token",
        "old-interaction",
        1,
        datetime.now(UTC),
        {},
    )
    initial = SessionMemory(
        "conversation-1",
        current_action="CREATE_REQUEST",
        collected_data={"quantity": 1},
        awaiting_action=awaiting,
        confirmed=True,
    )
    subject = ProcurementAgent(
        llm=ScriptedLLMClient(
            (
                LLMResponse(
                    tool_calls=(ToolCall("save_request_draft_fields", {"fields": {"quantity": 3}}),)
                ),
                LLMResponse(content="数量已修改，请重新确认。"),
            )
        ),
        registry=build_requester_tool_registry(),
        settings=Settings(4, 3),
    )
    result = await subject.run("改成三台", runtime(backend, initial))
    updated = apply_memory_patch(initial, result.memory_patch)  # type: ignore[arg-type]
    assert updated.collected_data["quantity"] == 3
    assert updated.confirmed is False
    assert updated.awaiting_action is None
