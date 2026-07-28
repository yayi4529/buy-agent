from typing import Protocol


class MessageStore(Protocol):
    async def append(self, session_key: str, role: str, content: str) -> None: ...

    async def recent(self, session_key: str, limit: int = 20) -> list[dict[str, str]]: ...
