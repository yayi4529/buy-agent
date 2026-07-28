from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity
from buy_agent.domain.requirement import RequirementContext


def fake_requirement(
    requirement_id: int, status: str = "DRAFT", requirement_no: str | None = None
) -> RequirementContext:
    return RequirementContext(
        requirement_id=requirement_id,
        requirement_no=requirement_no or f"PR-2026-{requirement_id:03d}",
        status=status,
        version=1,
        requester_fields={},
        reviewer_fields={},
        purchaser_fields={},
        warehouse_fields={},
        missing_fields=(),
        next_missing_field=None,
        allowed_actions=(),
    )


class FakeBackendGateway:
    def __init__(
        self,
        principals: dict[str, CurrentPrincipal] | None = None,
        requirements: dict[int, list[RequirementContext]] | None = None,
    ) -> None:
        self.principals = principals or self.default_principals()
        self.requirements = (
            requirements if requirements is not None else self.default_requirements()
        )

    @staticmethod
    def default_principals() -> dict[str, CurrentPrincipal]:
        roles = {
            "requester": frozenset({"REQUESTER"}),
            "reviewer": frozenset({"REVIEWER"}),
            "purchaser": frozenset({"PURCHASER"}),
            "warehouse": frozenset({"WAREHOUSE"}),
            "multi": frozenset({"REQUESTER", "REVIEWER"}),
            "disabled": frozenset({"REQUESTER"}),
            "no_role": frozenset(),
        }
        return {
            name: CurrentPrincipal(
                user_id=index,
                name=name,
                roles=user_roles,
                department_ids=("D1",),
                data_scopes=(),
                system_status="DISABLED" if name == "disabled" else "ACTIVE",
            )
            for index, (name, user_roles) in enumerate(roles.items(), start=1)
        }

    @staticmethod
    def default_requirements() -> dict[int, list[RequirementContext]]:
        return {
            1: [fake_requirement(101, "DRAFT")],
            2: [
                fake_requirement(201, "PENDING_REVIEW"),
                fake_requirement(202, "PENDING_REVIEW"),
            ],
            3: [],
            4: [fake_requirement(401, "PENDING_WAREHOUSE")],
            5: [fake_requirement(501, "READY_TO_SUBMIT")],
            6: [],
            7: [],
        }

    async def resolve_identity(self, identity: ExternalIdentity) -> CurrentPrincipal:
        return self.principals[identity.external_user_id]

    async def list_active_requirements(
        self, *, principal: CurrentPrincipal
    ) -> list[RequirementContext]:
        return list(self.requirements.get(principal.user_id, []))

    async def get_requirement(
        self, *, requirement_id: int, principal: CurrentPrincipal
    ) -> RequirementContext:
        for requirement in self.requirements.get(principal.user_id, []):
            if requirement.requirement_id == requirement_id:
                return requirement
        if any(
            requirement.requirement_id == requirement_id
            for requirements in self.requirements.values()
            for requirement in requirements
        ):
            raise PermissionError(f"requirement {requirement_id} is not accessible")
        raise LookupError(f"requirement {requirement_id} is not accessible")
