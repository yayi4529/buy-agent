import re

from buy_agent.application.errors import (
    RequirementAccessDeniedError,
    RequirementNotFoundError,
)
from buy_agent.domain.conversation import AgentConversation, SessionState
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.domain.requirement import RequirementContext, RequirementResolution
from buy_agent.memory.models import SessionMemory
from buy_agent.ports.backend_gateway import BackendGateway

_ID_PATTERN = re.compile(r"(?:requirement_id\s*=\s*|采购单\s*)(\d+)", re.IGNORECASE)
_NO_PATTERN = re.compile(r"\bPR-\d{4}-\d+\b", re.IGNORECASE)


class RequirementResolver:
    def __init__(self, backend: BackendGateway) -> None:
        self._backend = backend

    @property
    def backend(self) -> BackendGateway:
        return self._backend

    async def resolve(
        self, *, user_message: str, principal: CurrentPrincipal, session: SessionState
    ) -> RequirementResolution:
        requirements = await self._backend.list_active_requirements(principal=principal)
        explicit_id, explicit_no = self._extract_explicit(user_message)
        if explicit_id is not None:
            return RequirementResolution(await self._get_requirement(explicit_id, principal))
        if explicit_no is not None:
            for requirement in requirements:
                if requirement.requirement_no.upper() == explicit_no:
                    return RequirementResolution(requirement)
            raise RequirementNotFoundError

        if session.active_requirement_id is not None:
            requirement = await self._get_requirement(session.active_requirement_id, principal)
            return RequirementResolution(requirement)

        if len(requirements) == 1:
            return RequirementResolution(requirements[0])
        if len(requirements) > 1:
            return RequirementResolution(None, True, tuple(requirements))
        return RequirementResolution(None)

    async def resolve_for_conversation(
        self,
        *,
        user_message: str,
        principal: CurrentPrincipal,
        conversation: AgentConversation,
        memory: SessionMemory,
    ) -> RequirementResolution:
        if conversation.purchase_request_id is None and memory.current_action == "CREATE_REQUEST":
            return RequirementResolution(None)
        legacy = SessionState(
            session_key=conversation.session_key,
            user_id=conversation.employee_id,
            active_requirement_id=conversation.purchase_request_id,
        )
        return await self.resolve(user_message=user_message, principal=principal, session=legacy)

    @staticmethod
    def _extract_explicit(text: str) -> tuple[int | None, str | None]:
        id_match = _ID_PATTERN.search(text)
        no_match = _NO_PATTERN.search(text)
        return (
            int(id_match.group(1)) if id_match else None,
            no_match.group(0).upper() if no_match else None,
        )

    async def _get_requirement(
        self, requirement_id: int, principal: CurrentPrincipal
    ) -> RequirementContext:
        try:
            return await self._backend.get_requirement(
                requirement_id=requirement_id, principal=principal
            )
        except PermissionError as error:
            raise RequirementAccessDeniedError from error
        except LookupError as error:
            raise RequirementNotFoundError from error
