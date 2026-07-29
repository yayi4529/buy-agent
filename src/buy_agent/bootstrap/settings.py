from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    agent_max_rounds: int = 8
    agent_max_tool_calls: int = 4
    recent_message_limit: int = 20
    default_current_action: str = "CREATE_REQUEST"

    def __post_init__(self) -> None:
        if self.agent_max_rounds < 1:
            raise ValueError("agent_max_rounds must be at least 1")
        if self.agent_max_tool_calls < 0:
            raise ValueError("agent_max_tool_calls must not be negative")
        if self.recent_message_limit < 1:
            raise ValueError("recent_message_limit must be at least 1")
