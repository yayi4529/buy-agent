import re

from buy_agent.domain.conversation import SessionState
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.domain.requirement import RequirementContext, RequirementResolution
from buy_agent.ports.backend_gateway import BackendGateway

_ID_PATTERN = re.compile(r"(?:requirement_id\s*=\s*|采购单\s*)(\d+)", re.IGNORECASE)
_NO_PATTERN = re.compile(r"\bPR-\d{4}-\d+\b", re.IGNORECASE)


class RequirementResolver:
    def __init__(self, backend: BackendGateway) -> None:
        self._backend = backend

    async def resolve(
        self, *, user_message: str, principal: CurrentPrincipal, session: SessionState
    ) -> RequirementResolution:
        requirements = await self._backend.list_active_requirements(principal=principal)
        explicit = self._find_explicit(user_message, requirements)
        if explicit is not None:
            return RequirementResolution(explicit)

        if session.active_requirement_id is not None:
            requirement = await self._backend.get_requirement(
                requirement_id=session.active_requirement_id, principal=principal
            )
            return RequirementResolution(requirement)

        if len(requirements) == 1:
            return RequirementResolution(requirements[0])
        if len(requirements) > 1:
            return RequirementResolution(None, True, tuple(requirements))
        return RequirementResolution(None)

    @staticmethod
    def _find_explicit(
        text: str, requirements: list[RequirementContext]
    ) -> RequirementContext | None:
        id_match = _ID_PATTERN.search(text)
        no_match = _NO_PATTERN.search(text)
        wanted_id = int(id_match.group(1)) if id_match else None
        wanted_no = no_match.group(0).upper() if no_match else None
        for requirement in requirements:
            if (
                requirement.requirement_id == wanted_id
                or requirement.requirement_no.upper() == wanted_no
            ):
                return requirement
        return None
