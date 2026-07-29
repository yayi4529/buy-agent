"""Manual, networked smoke test. It is never collected by pytest."""

import asyncio

from buy_agent.adapters.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient
from buy_agent.bootstrap.settings import Settings
from buy_agent.domain.agent import LLMMessage


async def main() -> None:
    settings = Settings.from_env()
    if not settings.llm_api_key:
        print("Skipped: BUY_AGENT_LLM_API_KEY is not configured.")
        return
    client = OpenAICompatibleLLMClient(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        temperature=settings.llm_temperature,
    )
    result = await client.complete(
        [LLMMessage("user", "我要采购两台服务器，请只简短确认收到。")],
        (),
    )
    print(
        f"finish_reason={result.finish_reason!r} "
        f"tool_call_count={len(result.tool_calls)} content_present={bool(result.content)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
