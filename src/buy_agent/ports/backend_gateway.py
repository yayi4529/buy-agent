from typing import Protocol

from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity
from buy_agent.domain.requirement import RequirementContext


class BackendGateway(Protocol):
    async def resolve_identity(self, identity: ExternalIdentity) -> CurrentPrincipal: ...

    async def list_active_requirements(
        self, *, principal: CurrentPrincipal
    ) -> list[RequirementContext]: ...

    async def get_requirement(
        self, *, requirement_id: int, principal: CurrentPrincipal
    ) -> RequirementContext: ...
