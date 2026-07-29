import json
from typing import Any, cast

from pydantic import ValidationError

from buy_agent.agent.prompt_builder import PromptBuilder
from buy_agent.bootstrap.settings import Settings
from buy_agent.domain.agent import (
    AgentResponse,
    AgentRunResult,
    LLMMessage,
    ToolCall,
    ToolResult,
)
from buy_agent.domain.conversation import AgentRuntimeContext
from buy_agent.domain.interaction import InteractionView
from buy_agent.memory.models import SessionMemory
from buy_agent.memory.patches import MemoryPatch
from buy_agent.memory.service import apply_memory_patch
from buy_agent.ports.backend_gateway import BackendGateway
from buy_agent.ports.llm_client import LLMClient
from buy_agent.tools.base import ToolExecutionContext
from buy_agent.tools.registry import ToolRegistry

_MAX_ROUNDS = "已达到最大执行轮数，请稍后重试。"
_MAX_TOOL_CALLS = "已达到最大工具调用次数，请稍后重试。"


class ProcurementAgent:
    def __init__(
        self,
        *,
        llm: LLMClient,
        registry: ToolRegistry,
        settings: Settings,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._settings = settings
        self._prompt_builder = prompt_builder or PromptBuilder()

    async def respond(self, user_message: str, context: AgentRuntimeContext) -> str:
        return (await self.run(user_message, context)).response.text

    async def run(self, user_message: str, context: AgentRuntimeContext) -> AgentRunResult:
        messages = [
            LLMMessage(role="system", content=self._prompt_builder.build(context)),
            LLMMessage(role="user", content=user_message),
        ]
        definitions = self._registry.definitions_for(context.available_tool_names)
        results: list[ToolResult] = []
        executed: set[str] = set()
        tool_call_count = 0
        memory_patch = MemoryPatch.empty()
        working_memory = context.memory or SessionMemory(
            conversation_id=context.session_key or context.session.session_key,
            summary=context.session.summary,
        )

        for round_number in range(1, self._settings.agent_max_rounds + 1):
            llm_response = await self._llm.complete(messages, definitions)
            if len(llm_response.tool_calls) > 1:
                result = self._error("MULTIPLE_TOOL_CALLS", "每轮最多允许一个工具调用。")
                results.append(result)
                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=llm_response.content,
                        tool_calls=llm_response.tool_calls,
                    )
                )
                for rejected_call in llm_response.tool_calls:
                    self._append_tool_result(messages, rejected_call, result)
                continue
            if not llm_response.tool_calls:
                text = llm_response.content or ""
                return AgentRunResult(
                    AgentResponse(text, self._latest_interaction(results)),
                    round_number,
                    tool_call_count,
                    tuple(results),
                    None if memory_patch.is_empty else memory_patch,
                )
            if tool_call_count >= self._settings.agent_max_tool_calls:
                return AgentRunResult(
                    AgentResponse(_MAX_TOOL_CALLS, self._latest_interaction(results)),
                    round_number,
                    tool_call_count,
                    tuple(results),
                    None if memory_patch.is_empty else memory_patch,
                )

            call = llm_response.tool_calls[0]
            messages.append(
                LLMMessage(
                    role="assistant",
                    content=llm_response.content,
                    tool_calls=llm_response.tool_calls,
                )
            )
            tool_call_count += 1
            result = await self._execute(call, context, working_memory, executed)
            results.append(result)
            result_patch = result.memory_patch
            if result.success and result_patch is not None:
                try:
                    updated_memory = apply_memory_patch(working_memory, result_patch)
                except (TypeError, ValueError):
                    result = self._error("INVALID_MEMORY_PATCH", "工具返回的会话变更无效。")
                    results[-1] = result
                else:
                    working_memory = updated_memory
                    memory_patch = memory_patch.merge(result_patch)
            self._append_tool_result(messages, call, result)

        return AgentRunResult(
            AgentResponse(_MAX_ROUNDS, self._latest_interaction(results)),
            self._settings.agent_max_rounds,
            tool_call_count,
            tuple(results),
            None if memory_patch.is_empty else memory_patch,
        )

    async def _execute(
        self,
        call: ToolCall,
        context: AgentRuntimeContext,
        working_memory: SessionMemory,
        executed: set[str],
    ) -> ToolResult:
        tool = self._registry.get(call.name)
        if tool is None:
            return self._error("TOOL_NOT_REGISTERED", f"工具未注册: {call.name}")
        if call.name not in context.available_tool_names:
            return self._error("TOOL_NOT_AUTHORIZED", f"当前上下文无权调用工具: {call.name}")
        signature = self._signature(call)
        if signature in executed:
            return self._error("DUPLICATE_TOOL_CALL", "本次运行中相同工具和参数已执行。")
        try:
            arguments = tool.arguments_model.model_validate(call.arguments)
        except ValidationError as error:
            return ToolResult(
                success=False,
                code="VALIDATION_ERROR",
                message="工具参数校验失败。",
                data={"errors": error.errors(include_url=False, include_input=False)},
            )
        executed.add(signature)
        return await tool.execute(
            arguments,
            ToolExecutionContext(
                trace_id=context.trace_id,
                event_id=context.event_id,
                session_key=context.session_key or context.session.session_key,
                principal=context.principal,
                memory=working_memory,
                backend_gateway=cast(BackendGateway, context.backend_gateway),
            ),
        )

    @staticmethod
    def _signature(call: ToolCall) -> str:
        arguments = json.dumps(call.arguments, sort_keys=True, separators=(",", ":"), default=str)
        return f"{call.name}:{arguments}"

    @staticmethod
    def _error(code: str, message: str) -> ToolResult:
        return ToolResult(success=False, code=code, message=message)

    @staticmethod
    def _append_tool_result(
        messages: list[LLMMessage],
        call: ToolCall | None,
        result: ToolResult,
    ) -> None:
        payload: dict[str, Any] = {
            "success": result.success,
            "code": result.code,
            "message": result.message,
            "data": result.data,
            "interaction": result.interaction,
        }
        messages.append(
            LLMMessage(
                role="tool",
                content=json.dumps(payload, ensure_ascii=False, default=str),
                tool_call_id=call.call_id if call else None,
                name=call.name if call else None,
            )
        )

    @staticmethod
    def _latest_interaction(results: list[ToolResult]) -> InteractionView | None:
        return next(
            (result.interaction for result in reversed(results) if result.interaction is not None),
            None,
        )
