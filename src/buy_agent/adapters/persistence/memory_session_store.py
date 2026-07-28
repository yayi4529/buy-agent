from copy import deepcopy

from buy_agent.domain.conversation import SessionState


class MemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    async def get(self, session_key: str) -> SessionState | None:
        session = self._sessions.get(session_key)
        return deepcopy(session) if session is not None else None

    async def save(self, session: SessionState) -> None:
        self._sessions[session.session_key] = deepcopy(session)
