from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity
from buy_agent.ports.backend_gateway import BackendGateway


class IdentityService:
    def __init__(self, backend: BackendGateway) -> None:
        self._backend = backend

    async def resolve(self, identity: ExternalIdentity) -> CurrentPrincipal:
        return await self._backend.resolve_identity(identity)
