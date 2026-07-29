from types import SimpleNamespace
from typing import Any

import pytest

from buy_agent.adapters.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient
from buy_agent.domain.agent import LLMMessage


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> object:
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content="完成", tool_calls=[]),
                )
            ]
        )


@pytest.mark.asyncio
async def test_client_maps_request_and_response_without_executing_tools() -> None:
    completions = FakeCompletions()
    sdk = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    client = OpenAICompatibleLLMClient(
        model="test-model",
        api_key=None,
        temperature=0,
        sdk_client=sdk,
    )
    response = await client.complete(
        [LLMMessage("user", "采购服务器")],
        [
            {
                "name": "save",
                "description": "save fields",
                "parameters": {"type": "object", "properties": {}},
            }
        ],
    )
    assert response.content == "完成"
    assert completions.kwargs["model"] == "test-model"
    assert completions.kwargs["temperature"] == 0
    assert completions.kwargs["messages"][0]["role"] == "user"
    assert completions.kwargs["tools"][0]["function"]["name"] == "save"


def test_real_client_requires_model_and_api_key() -> None:
    with pytest.raises(ValueError, match="model"):
        OpenAICompatibleLLMClient(model="", api_key="fake")
    with pytest.raises(ValueError, match="API key"):
        OpenAICompatibleLLMClient(model="model", api_key=None)
