from decimal import Decimal
from typing import Any

from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity
from buy_agent.domain.requirement import RequirementContext
from buy_agent.ports.backend_gateway import (
    BuildingOption,
    CreatedPurchaseRequest,
    CreatePurchaseRequestCommand,
    HandlerCandidate,
    ProductRecommendation,
)


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
        create_failure: str | None = None,
    ) -> None:
        self.principals = principals or self.default_principals()
        self.requirements = (
            requirements if requirements is not None else self.default_requirements()
        )
        self.calls: dict[str, list[dict[str, Any]]] = {}
        self.create_purchase_request_call_count = 0
        self.formal_action_call_count = 0
        self.create_failure = create_failure
        self.last_create_purchase_request: (
            tuple[CurrentPrincipal, CreatePurchaseRequestCommand] | None
        ) = None
        self._created_by_key: dict[str, CreatedPurchaseRequest] = {}
        self.buildings = {
            1: (BuildingOption(1, "一号楼", True),),
            6: (
                BuildingOption(1, "一号楼", True),
                BuildingOption(2, "二号楼"),
            ),
            7: (),
        }
        self.reviewers: dict[int, dict[int, tuple[HandlerCandidate, ...]]] = {
            1: {
                1: (HandlerCandidate(101, "张楼长", "张楼长（一号楼）"),),
            },
            6: {
                1: (
                    HandlerCandidate(101, "张楼长", "张楼长（一号楼）"),
                    HandlerCandidate(102, "李楼长", "李楼长（一号楼）"),
                ),
                2: (HandlerCandidate(201, "王楼长", "王楼长（二号楼）"),),
            },
        }
        self.products: tuple[ProductRecommendation, ...] = (
            ProductRecommendation(
                "rec-server-1",
                "product-server-1",
                "服务器",
                "机架式服务器",
                "戴尔",
                "PowerEdge R760",
                "台",
                Decimal(68999),
                "适合模型推理",
            ),
            ProductRecommendation(
                "rec-server-2",
                "product-server-2",
                "服务器",
                "机架式服务器",
                "联想",
                "ThinkSystem SR650 V3",
                "台",
                Decimal(65999),
                "通用计算配置",
            ),
            ProductRecommendation(
                "rec-server-3",
                "product-server-3",
                "服务器",
                "机架式服务器",
                "浪潮",
                "NF5180M6",
                "台",
                Decimal(61999),
                "高性价比配置",
            ),
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

    def _record(self, name: str, **arguments: Any) -> None:
        self.calls.setdefault(name, []).append(arguments)

    async def list_available_buildings(
        self, *, principal: CurrentPrincipal
    ) -> tuple[BuildingOption, ...]:
        self._record("list_available_buildings", principal=principal)
        return self.buildings.get(principal.user_id, ())

    async def recommend_products(
        self,
        *,
        principal: CurrentPrincipal,
        query: str,
        device_profession: str | None,
        device_name: str | None,
        brand_preference: str | None,
        limit: int,
    ) -> tuple[ProductRecommendation, ...]:
        self._record(
            "recommend_products",
            principal=principal,
            query=query,
            device_profession=device_profession,
            device_name=device_name,
            brand_preference=brand_preference,
            limit=limit,
        )
        if "无结果" in query:
            return ()
        matches = self.products
        if brand_preference:
            matches = tuple(item for item in matches if item.brand == brand_preference)
        return matches[:limit]

    async def get_product_recommendation(
        self, *, principal: CurrentPrincipal, recommendation_id: str
    ) -> ProductRecommendation | None:
        self._record(
            "get_product_recommendation",
            principal=principal,
            recommendation_id=recommendation_id,
        )
        return next(
            (item for item in self.products if item.recommendation_id == recommendation_id),
            None,
        )

    async def list_reviewer_candidates(
        self, *, principal: CurrentPrincipal, building_id: int
    ) -> tuple[HandlerCandidate, ...]:
        self._record(
            "list_reviewer_candidates",
            principal=principal,
            building_id=building_id,
        )
        return self.reviewers.get(principal.user_id, {}).get(building_id, ())

    async def create_purchase_request(
        self,
        *,
        principal: CurrentPrincipal,
        command: CreatePurchaseRequestCommand,
    ) -> CreatedPurchaseRequest:
        self.create_purchase_request_call_count += 1
        self.last_create_purchase_request = (principal, command)
        self._record("create_purchase_request", principal=principal, command=command)
        existing = self._created_by_key.get(command.idempotency_key)
        if existing is not None:
            return existing
        if self.create_failure == "permission":
            raise PermissionError("mock permission denied")
        if self.create_failure in {"building", "reviewer", "validation", "business"}:
            raise ValueError(f"mock {self.create_failure} validation failed")
        if self.create_failure == "technical":
            raise RuntimeError("mock technical failure")
        request_id = 1_000_000 + len(self._created_by_key) + 1
        result = CreatedPurchaseRequest(
            request_id=request_id,
            request_no=f"MOCK-PR-{len(self._created_by_key) + 1:06d}",
            status="PENDING_REVIEW",
            current_handler_employee_id=command.reviewer_employee_id,
        )
        self._created_by_key[command.idempotency_key] = result
        return result


MockBackendGateway = FakeBackendGateway
