from dataclasses import replace

import pytest
from pydantic import ValidationError

from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.memory import (
    AwaitingAction,
    RecommendationReference,
    SessionMemory,
    apply_memory_patch,
)
from buy_agent.tools.base import ToolExecutionContext
from buy_agent.tools.requester.list_available_buildings import (
    ListAvailableBuildingsArgs,
    ListAvailableBuildingsTool,
)
from buy_agent.tools.requester.prepare_request_submission import (
    PrepareRequestSubmissionArgs,
    PrepareRequestSubmissionTool,
)
from buy_agent.tools.requester.recommend_products import (
    RecommendProductsArgs,
    RecommendProductsTool,
)
from buy_agent.tools.requester.save_request_draft_fields import (
    SaveRequestDraftFieldsArgs,
    SaveRequestDraftFieldsTool,
)
from buy_agent.tools.requester.select_building import (
    SelectBuildingArgs,
    SelectBuildingTool,
)
from buy_agent.tools.requester.select_product_recommendation import (
    SelectProductRecommendationArgs,
    SelectProductRecommendationTool,
)


class FixedTokenFactory:
    def create(self) -> str:
        return "fixed-token"


def principal(user_id: int = 1) -> CurrentPrincipal:
    return CurrentPrincipal(user_id, f"user-{user_id}", frozenset({"REQUESTER"}), (), (), "ACTIVE")


def memory(user_id: int = 1, **changes: object) -> SessionMemory:
    base = SessionMemory(
        conversation_id=f"conversation-{user_id}",
        current_action="CREATE_REQUEST",
    )
    return replace(base, **changes)


def context(user_id: int = 1, value: SessionMemory | None = None) -> ToolExecutionContext:
    return ToolExecutionContext(
        "trace",
        "event",
        f"session-{user_id}",
        principal(user_id),
        value or memory(user_id),
        FakeBackendGateway(),
    )


@pytest.mark.asyncio
async def test_save_fields_batches_preserves_old_values_and_allows_edits() -> None:
    subject = SaveRequestDraftFieldsTool()
    initial = memory(collected_data={"brand": "旧品牌", "quantity": 1})
    result = await subject.execute(
        SaveRequestDraftFieldsArgs(fields={"device_name": "服务器", "quantity": 2}),
        context(value=initial),
    )
    updated = apply_memory_patch(initial, result.memory_patch)  # type: ignore[arg-type]
    assert updated.collected_data == {
        "brand": "旧品牌",
        "device_name": "服务器",
        "quantity": 2,
    }
    assert "device_name" in result.message
    assert context().backend_gateway.create_purchase_request_call_count == 0  # type: ignore[attr-defined]


@pytest.mark.parametrize("quantity", [0, -1])
def test_save_fields_rejects_non_positive_quantity(quantity: int) -> None:
    with pytest.raises(ValidationError):
        SaveRequestDraftFieldsArgs(fields={"quantity": quantity})


@pytest.mark.parametrize(
    "payload",
    [
        {"fields": {"unknown": "x"}},
        {"fields": {"purchase_request_id": 10}},
        {"fields": {}, "employee_id": 1},
    ],
)
def test_save_fields_rejects_unknown_and_system_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SaveRequestDraftFieldsArgs.model_validate(payload)


@pytest.mark.asyncio
async def test_save_fields_rejects_empty_patch_and_clears_old_confirmation() -> None:
    subject = SaveRequestDraftFieldsTool()
    empty = await subject.execute(SaveRequestDraftFieldsArgs(fields={}), context())
    assert empty.code == "VALIDATION_ERROR"

    from datetime import UTC, datetime

    awaiting = AwaitingAction("submit_request", "old", "old-id", 1, datetime.now(UTC), {})
    initial = memory(
        collected_data={"quantity": 1},
        awaiting_action=awaiting,
        confirmed=False,
    )
    changed = await subject.execute(
        SaveRequestDraftFieldsArgs(fields={"quantity": 2}), context(value=initial)
    )
    assert apply_memory_patch(initial, changed.memory_patch).awaiting_action is None  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_id", "code", "has_patch", "count"),
    [(7, "BUSINESS_ERROR", False, 0), (1, "OK", True, 1), (6, "OK", False, 2)],
)
async def test_list_buildings_cases(user_id: int, code: str, has_patch: bool, count: int) -> None:
    result = await ListAvailableBuildingsTool().execute(
        ListAvailableBuildingsArgs(), context(user_id)
    )
    assert result.code == code
    assert (result.memory_patch is not None) is has_patch
    assert len(result.data["buildings"]) == count  # type: ignore[index]


def test_list_buildings_arguments_forbid_employee_id() -> None:
    with pytest.raises(ValidationError):
        ListAvailableBuildingsArgs.model_validate({"employee_id": 1})


@pytest.mark.asyncio
async def test_select_building_revalidates_scope_and_missing_fields() -> None:
    subject = SelectBuildingTool()
    allowed = await subject.execute(SelectBuildingArgs(building_id=1), context(6))
    denied = await subject.execute(SelectBuildingArgs(building_id=2), context(1))
    assert allowed.success
    assert "building_id" not in allowed.data["missing_fields"]  # type: ignore[index]
    assert denied.code == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_recommendations_are_bounded_referenced_and_not_collected() -> None:
    result = await RecommendProductsTool().execute(
        RecommendProductsArgs(query="服务器", limit=3), context()
    )
    assert len(result.data["recommendations"]) == 3  # type: ignore[index]
    assert len(result.memory_patch.replace_last_recommendations) == 3  # type: ignore[union-attr]
    assert result.memory_patch.collected_data_patch.__class__.__name__ == "UnsetType"  # type: ignore[union-attr]
    with pytest.raises(ValidationError):
        RecommendProductsArgs(query="服务器", limit=4)


@pytest.mark.asyncio
async def test_empty_recommendations_are_controlled() -> None:
    result = await RecommendProductsTool().execute(RecommendProductsArgs(query="无结果"), context())
    assert result.success
    assert result.data == {"recommendations": []}


@pytest.mark.asyncio
async def test_select_recommendation_uses_reference_and_preserves_user_fields() -> None:
    reference = RecommendationReference(
        1, "rec-server-1", "product", "product-server-1", "戴尔 R760"
    )
    initial = memory(
        collected_data={"quantity": 2, "application_reason": "推理"},
        last_recommendations=(reference,),
    )
    result = await SelectProductRecommendationTool().execute(
        SelectProductRecommendationArgs(selection_index=1), context(value=initial)
    )
    updated = apply_memory_patch(initial, result.memory_patch)  # type: ignore[arg-type]
    assert updated.collected_data["quantity"] == 2
    assert updated.collected_data["application_reason"] == "推理"
    assert updated.collected_data["model"] == "PowerEdge R760"
    assert updated.last_recommendations == ()


@pytest.mark.asyncio
async def test_select_recommendation_rejects_missing_or_mismatched_reference() -> None:
    subject = SelectProductRecommendationTool()
    missing = await subject.execute(SelectProductRecommendationArgs(selection_index=1), context())
    mismatch_memory = memory(
        last_recommendations=(
            RecommendationReference(1, "rec-server-1", "product", "wrong", "wrong"),
        )
    )
    mismatch = await subject.execute(
        SelectProductRecommendationArgs(selection_index=1),
        context(value=mismatch_memory),
    )
    assert missing.code == mismatch.code == "VALIDATION_ERROR"


def complete_memory(user_id: int = 1) -> SessionMemory:
    return memory(
        user_id,
        collected_data={
            "building_id": 1,
            "device_profession": "服务器",
            "device_name": "机架式服务器",
            "brand": "戴尔",
            "model": "PowerEdge R760",
            "quantity": 2,
            "unit": "台",
            "application_reason": "模型推理",
            "applicant_remark": "尽快",
        },
    )


@pytest.mark.asyncio
async def test_prepare_requires_complete_fields_and_does_no_formal_work() -> None:
    backend = FakeBackendGateway()
    incomplete_context = context()
    incomplete_context = replace(incomplete_context, backend_gateway=backend)
    result = await PrepareRequestSubmissionTool(FixedTokenFactory()).execute(
        PrepareRequestSubmissionArgs(), incomplete_context
    )
    assert result.code == "VALIDATION_ERROR"
    assert result.interaction is None
    assert backend.create_purchase_request_call_count == 0
    assert backend.formal_action_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("user_id", "selection_count"), [(1, 0), (6, 2)])
async def test_prepare_builds_confirmation_and_reviewer_choices(
    user_id: int, selection_count: int
) -> None:
    initial = complete_memory(user_id)
    result = await PrepareRequestSubmissionTool(FixedTokenFactory()).execute(
        PrepareRequestSubmissionArgs(), context(user_id, initial)
    )
    assert result.success
    assert result.interaction is not None
    assert len(result.interaction.selection_groups) == (1 if selection_count else 0)
    action = result.interaction.actions[0]
    assert action.payload["action_token"] == "fixed-token"
    assert action.payload["expected_state_version"] == initial.state_version + 1
    updated = apply_memory_patch(initial, result.memory_patch)  # type: ignore[arg-type]
    assert updated.confirmed is False
    assert updated.purchase_request_id is None
    assert updated.awaiting_action is not None


@pytest.mark.asyncio
async def test_prepare_rejects_when_no_reviewer() -> None:
    backend = FakeBackendGateway()
    backend.reviewers[1][1] = ()
    execution_context = replace(context(value=complete_memory()), backend_gateway=backend)
    result = await PrepareRequestSubmissionTool().execute(
        PrepareRequestSubmissionArgs(), execution_context
    )
    assert result.code == "BUSINESS_ERROR"
