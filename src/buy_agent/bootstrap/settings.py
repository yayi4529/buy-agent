from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    agent_max_rounds: int = 8
    agent_max_tool_calls: int = 4

    def __post_init__(self) -> None:
        if self.agent_max_rounds < 1:
            raise ValueError("agent_max_rounds must be at least 1")
        if self.agent_max_tool_calls < 0:
            raise ValueError("agent_max_tool_calls must not be negative")
