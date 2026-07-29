from dataclasses import dataclass, field
from typing import Any, Literal

from buy_agent.domain.interaction import InteractionView
from buy_agent.memory.patches import MemoryPatch


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass(frozen=True)
class LLMMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class LLMResponse:
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str | None = None


@dataclass(frozen=True)
class AgentResponse:
    text: str
    interaction: InteractionView | None = None


@dataclass(frozen=True)
class AgentRunResult:
    response: AgentResponse
    rounds: int
    tool_calls: int
    tool_results: tuple["ToolResult", ...] = field(default_factory=tuple)
    memory_patch: MemoryPatch | None = None


@dataclass(frozen=True)
class ToolEffect:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    success: bool
    code: str
    message: str
    data: dict[str, Any] | None = None
    effects: tuple[ToolEffect, ...] = ()
    memory_patch: MemoryPatch | None = None
    interaction: InteractionView | None = None
