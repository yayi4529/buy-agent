from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity
from buy_agent.domain.requirement import RequirementContext


@dataclass(frozen=True)
class BuildingOption:
    building_id: int
    building_name: str
    is_primary: bool = False


@dataclass(frozen=True)
class ProductRecommendation:
    recommendation_id: str
    entity_id: str
    device_profession: str
    device_name: str
    brand: str
    model: str
    unit: str
    reference_price: Decimal | None
    match_explanation: str


@dataclass(frozen=True)
class HandlerCandidate:
    employee_id: int
    name: str
    display_label: str


@dataclass(frozen=True)
class CreatePurchaseRequestCommand:
    building_id: int
    device_profession: str
    device_name: str
    brand: str | None
    model: str | None
    quantity: int
    unit: str
    application_reason: str
    applicant_remark: str | None
    reviewer_employee_id: int
    idempotency_key: str


@dataclass(frozen=True)
class CreatedPurchaseRequest:
    request_id: int
    request_no: str
    status: str
    current_handler_employee_id: int


class BackendGateway(Protocol):
    async def resolve_identity(self, identity: ExternalIdentity) -> CurrentPrincipal: ...

    async def list_active_requirements(
        self, *, principal: CurrentPrincipal
    ) -> list[RequirementContext]: ...

    async def get_requirement(
        self, *, requirement_id: int, principal: CurrentPrincipal
    ) -> RequirementContext: ...

    async def list_available_buildings(
        self, *, principal: CurrentPrincipal
    ) -> tuple[BuildingOption, ...]: ...

    async def recommend_products(
        self,
        *,
        principal: CurrentPrincipal,
        query: str,
        device_profession: str | None,
        device_name: str | None,
        brand_preference: str | None,
        limit: int,
    ) -> tuple[ProductRecommendation, ...]: ...

    async def get_product_recommendation(
        self, *, principal: CurrentPrincipal, recommendation_id: str
    ) -> ProductRecommendation | None: ...

    async def list_reviewer_candidates(
        self, *, principal: CurrentPrincipal, building_id: int
    ) -> tuple[HandlerCandidate, ...]: ...

    async def create_purchase_request(
        self,
        *,
        principal: CurrentPrincipal,
        command: CreatePurchaseRequestCommand,
    ) -> CreatedPurchaseRequest: ...
