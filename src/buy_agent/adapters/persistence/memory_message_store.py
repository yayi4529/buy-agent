class MemoryMessageStore:
    def __init__(self) -> None:
        self._messages: dict[str, list[dict[str, str]]] = {}

    async def append(self, session_key: str, role: str, content: str) -> None:
        self._messages.setdefault(session_key, []).append({"role": role, "content": content})

    async def recent(self, session_key: str, limit: int = 20) -> list[dict[str, str]]:
        return [dict(item) for item in self._messages.get(session_key, [])[-limit:]]
