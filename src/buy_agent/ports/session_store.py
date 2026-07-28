from typing import Protocol

from buy_agent.domain.conversation import SessionState


class SessionStore(Protocol):
    async def get(self, session_key: str) -> SessionState | None: ...

    async def save(self, session: SessionState) -> None: ...
