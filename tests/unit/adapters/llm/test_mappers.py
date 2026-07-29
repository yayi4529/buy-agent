from types import SimpleNamespace

import pytest

from buy_agent.adapters.llm.errors import LLMResponseFormatError, LLMToolArgumentsError
from buy_agent.adapters.llm.message_mapper import map_messages
from buy_agent.adapters.llm.response_mapper import map_response
from buy_agent.adapters.llm.tool_schema_mapper import map_tools
from buy_agent.domain.agent import LLMMessage, ToolCall
from buy_agent.tools.requester import build_requester_tool_registry


def test_maps_all_message_roles_and_tool_linkage() -> None:
    messages = (
        LLMMessage("system", "rules"),
        LLMMessage("user", "request"),
        LLMMessage(
            "assistant",
            None,
            tool_calls=(ToolCall("save", {"quantity": 2}, "call-1"),),
        ),
        LLMMessage("tool", '{"success": true}', "call-1", "save"),
    )
    mapped = map_messages(messages)
    assert [item["role"] for item in mapped] == ["system", "user", "assistant", "tool"]
    assert mapped[2]["tool_calls"][0]["id"] == "call-1"
    assert mapped[3]["tool_call_id"] == "call-1"


def test_tool_message_requires_call_id() -> None:
    with pytest.raises(ValueError, match="tool_call_id"):
        map_messages((LLMMessage("tool", "{}"),))


def test_maps_requester_tool_schemas_from_pydantic() -> None:
    registry = build_requester_tool_registry()
    tools = [registry.get(name) for name in ("save_request_draft_fields", "recommend_products")]
    mapped = map_tools(tool for tool in tools if tool is not None)
    save_schema = mapped[0]["function"]["parameters"]
    assert "fields" in save_schema["properties"]
    assert "employee_id" not in str(save_schema)
    recommend_schema = mapped[1]["function"]["parameters"]
    assert recommend_schema["properties"]["limit"]["maximum"] == 3


def test_maps_text_and_multiple_tool_calls() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="one",
                            function=SimpleNamespace(name="first", arguments='{"value": 1}'),
                        ),
                        {
                            "id": "two",
                            "function": {"name": "second", "arguments": {"value": 2}},
                        },
                    ],
                ),
            )
        ]
    )
    mapped = map_response(response)
    assert mapped.content is None
    assert [call.call_id for call in mapped.tool_calls] == ["one", "two"]
    assert mapped.finish_reason == "tool_calls"


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (SimpleNamespace(choices=[]), LLMResponseFormatError),
        (
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    id="x",
                                    function=SimpleNamespace(name="save", arguments="{bad"),
                                )
                            ],
                        )
                    )
                ]
            ),
            LLMToolArgumentsError,
        ),
    ],
)
def test_rejects_invalid_responses(response: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        map_response(response)
