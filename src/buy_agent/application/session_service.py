from buy_agent.domain.conversation import SessionState
from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity
from buy_agent.ports.session_store import SessionStore


def build_session_key(identity: ExternalIdentity) -> str:
    return (
        f"procurement:{identity.channel}:{identity.external_tenant_id}:{identity.external_user_id}"
    )


class SessionService:
    def __init__(self, store: SessionStore) -> None:
        self._store = store

    async def load_or_create(
        self, identity: ExternalIdentity, principal: CurrentPrincipal
    ) -> SessionState:
        key = build_session_key(identity)
        existing = await self._store.get(key)
        if existing is not None:
            return existing
        session = SessionState(session_key=key, user_id=principal.user_id)
        await self._store.save(session)
        return session

    async def save(self, session: SessionState) -> None:
        await self._store.save(session)
