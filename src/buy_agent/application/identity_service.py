from buy_agent.application.errors import (
    IdentityNotFoundError,
    UserDisabledError,
    UserRoleMissingError,
)
from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity
from buy_agent.ports.backend_gateway import BackendGateway


class IdentityService:
    def __init__(self, backend: BackendGateway) -> None:
        self._backend = backend

    async def resolve(self, identity: ExternalIdentity) -> CurrentPrincipal:
        try:
            principal = await self._backend.resolve_identity(identity)
        except KeyError as error:
            raise IdentityNotFoundError from error
        if principal.system_status != "ACTIVE":
            raise UserDisabledError
        if not principal.roles:
            raise UserRoleMissingError
        return principal
