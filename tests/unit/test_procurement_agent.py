import pytest

from buy_agent.adapters.agent.fake_tool import FakeTool
from buy_agent.adapters.llm.scripted_llm_client import ScriptedLLMClient
from buy_agent.agent.procurement_agent import ProcurementAgent
from buy_agent.bootstrap.settings import Settings
from buy_agent.domain.agent import LLMResponse, ToolCall, ToolResult
from buy_agent.domain.conversation import AgentRuntimeContext, SessionState
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.memory import MemoryPatch
from buy_agent.tools.registry import ToolRegistry


def context(*tools: str) -> AgentRuntimeContext:
    return AgentRuntimeContext(
        principal=CurrentPrincipal(
            user_id=1,
            name="Requester",
            roles=frozenset({"REQUESTER"}),
            department_ids=frozenset(),
            data_scopes=frozenset(),
            system_status="ACTIVE",
        ),
        session=SessionState(session_key="procurement:test:t:u", user_id=1),
        requirement=None,
        available_tool_names=frozenset(tools),
    )


def agent(
    responses: list[LLMResponse],
    tool: FakeTool | None = None,
    *,
    rounds: int = 8,
    tool_calls: int = 4,
) -> tuple[ProcurementAgent, ScriptedLLMClient, FakeTool]:
    fake_tool = tool or FakeTool()
    llm = ScriptedLLMClient(responses)
    return (
        ProcurementAgent(
            llm=llm,
            registry=ToolRegistry([fake_tool]),
            settings=Settings(rounds, tool_calls),
        ),
        llm,
        fake_tool,
    )


@pytest.mark.asyncio
async def test_returns_text_without_tool_call() -> None:
    subject, llm, tool = agent([LLMResponse(content="请补充型号。")])
    result = await subject.run("买交换机", context("fake_tool"))
    assert result.response.text == "请补充型号。"
    assert result.rounds == 1
    assert result.tool_calls == 0
    assert tool.calls == []
    assert llm.calls[0][1][0]["name"] == "fake_tool"


@pytest.mark.asyncio
async def test_executes_one_tool_and_returns_result_to_model() -> None:
    subject, llm, tool = agent(
        [
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 7}, "call-1"),)),
            LLMResponse(content="已处理。"),
        ]
    )
    result = await subject.run("处理", context("fake_tool"))
    assert result.response.text == "已处理。"
    assert result.tool_calls == 1
    assert tool.calls[0][0].value == 7
    assert llm.calls[1][0][-1].role == "tool"
    assert '"code": "OK"' in llm.calls[1][0][-1].content


@pytest.mark.asyncio
async def test_allows_multi_round_calls_but_one_per_round() -> None:
    subject, _, tool = agent(
        [
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 1}),)),
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 2}),)),
            LLMResponse(content="完成"),
        ]
    )
    result = await subject.run("处理", context("fake_tool"))
    assert result.tool_calls == 2
    assert [call[0].value for call in tool.calls] == [1, 2]


@pytest.mark.asyncio
async def test_rejects_multiple_tool_calls_in_one_round() -> None:
    subject, _, tool = agent(
        [
            LLMResponse(
                tool_calls=(
                    ToolCall("fake_tool", {"value": 1}),
                    ToolCall("fake_tool", {"value": 2}),
                )
            ),
            LLMResponse(content="改为追问"),
        ]
    )
    result = await subject.run("处理", context("fake_tool"))
    assert result.tool_results[0].code == "MULTIPLE_TOOL_CALLS"
    assert result.tool_calls == 0
    assert tool.calls == []


@pytest.mark.asyncio
async def test_rejects_unregistered_tool() -> None:
    subject, _, tool = agent(
        [
            LLMResponse(tool_calls=(ToolCall("unknown", {}),)),
            LLMResponse(content="无法执行"),
        ]
    )
    result = await subject.run("处理", context("unknown"))
    assert result.tool_results[0].code == "TOOL_NOT_REGISTERED"
    assert tool.calls == []


@pytest.mark.asyncio
async def test_rejects_tool_not_authorized_by_context() -> None:
    subject, _, tool = agent(
        [
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 1}),)),
            LLMResponse(content="无权执行"),
        ]
    )
    result = await subject.run("处理", context())
    assert result.tool_results[0].code == "TOOL_NOT_AUTHORIZED"
    assert tool.calls == []


@pytest.mark.asyncio
async def test_validates_arguments_with_pydantic() -> None:
    subject, _, tool = agent(
        [
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": "bad"}),)),
            LLMResponse(content="参数无效"),
        ]
    )
    result = await subject.run("处理", context("fake_tool"))
    assert result.tool_results[0].code == "VALIDATION_ERROR"
    assert tool.calls == []


@pytest.mark.asyncio
async def test_prevents_duplicate_tool_and_arguments_in_same_run() -> None:
    subject, _, tool = agent(
        [
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 1}),)),
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 1}),)),
            LLMResponse(content="结束"),
        ]
    )
    result = await subject.run("处理", context("fake_tool"))
    assert result.tool_results[-1].code == "DUPLICATE_TOOL_CALL"
    assert len(tool.calls) == 1


@pytest.mark.asyncio
async def test_propagates_business_failure_to_model() -> None:
    failure = ToolResult(False, "INVALID_STATUS", "当前状态不允许。")
    subject, llm, _ = agent(
        [
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 1}),)),
            LLMResponse(content="当前不能处理。"),
        ],
        FakeTool(failure),
    )
    result = await subject.run("处理", context("fake_tool"))
    assert result.tool_results == (failure,)
    assert "INVALID_STATUS" in llm.calls[1][0][-1].content


@pytest.mark.asyncio
async def test_stops_at_maximum_rounds_from_settings() -> None:
    subject, llm, _ = agent(
        [
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 1}),)),
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 2}),)),
        ],
        rounds=2,
    )
    result = await subject.run("处理", context("fake_tool"))
    assert result.rounds == 2
    assert "最大执行轮数" in result.response.text
    assert len(llm.calls) == 2


@pytest.mark.asyncio
async def test_stops_before_exceeding_maximum_tool_calls() -> None:
    subject, _, tool = agent(
        [
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 1}),)),
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 2}),)),
        ],
        tool_calls=1,
    )
    result = await subject.run("处理", context("fake_tool"))
    assert result.tool_calls == 1
    assert "最大工具调用次数" in result.response.text
    assert len(tool.calls) == 1


@pytest.mark.asyncio
async def test_respond_keeps_existing_orchestrator_port_shape() -> None:
    subject, _, _ = agent([LLMResponse(content="兼容文本")])
    assert await subject.respond("消息", context()) == "兼容文本"


@pytest.mark.asyncio
async def test_aggregates_memory_patches_without_applying_them() -> None:
    tool = FakeTool(ToolResult(True, "OK", "done", memory_patch=MemoryPatch(summary="one")))
    subject, _, _ = agent(
        [
            LLMResponse(tool_calls=(ToolCall("fake_tool", {"value": 1}),)),
            LLMResponse(content="完成"),
        ],
        tool,
    )
    result = await subject.run("处理", context("fake_tool"))
    assert result.memory_patch == MemoryPatch(summary="one")
    assert context("fake_tool").session.summary == ""
