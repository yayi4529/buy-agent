import pytest
from pydantic import ValidationError

from buy_agent.memory import CreateRequestDraft, apply_create_request_patch


def complete_data() -> dict[str, object]:
    return {
        "building_id": 10,
        "device_profession": "网络",
        "device_name": "交换机",
        "quantity": 5,
        "unit": "台",
        "application_reason": "网络扩容",
    }


def test_accepts_partial_fields() -> None:
    draft = CreateRequestDraft(device_name="交换机", quantity=2)
    assert draft.device_name == "交换机"
    assert draft.brand is None


def test_accepts_complete_fields_without_optional_brand_or_model() -> None:
    draft = CreateRequestDraft.model_validate(complete_data())
    assert draft.brand is None
    assert draft.model is None


@pytest.mark.parametrize("quantity", [0, -1])
def test_rejects_non_positive_quantity(quantity: int) -> None:
    with pytest.raises(ValidationError):
        CreateRequestDraft(quantity=quantity)


def test_rejects_unknown_or_system_fields() -> None:
    with pytest.raises(ValidationError):
        CreateRequestDraft.model_validate({"request_id": 1})


def test_whitespace_is_allowed_in_draft_for_missing_field_resolution() -> None:
    draft = CreateRequestDraft(device_name="   ")
    assert draft.device_name == "   "


def test_patch_preserves_fields_not_provided_this_round() -> None:
    current = CreateRequestDraft(device_name="交换机", quantity=2)
    updated = apply_create_request_patch(current, {"brand": "华为"})
    assert updated.device_name == "交换机"
    assert updated.quantity == 2


def test_patch_overrides_old_value_and_can_merge_multiple_fields() -> None:
    current = CreateRequestDraft(device_name="旧名称", quantity=2)
    updated = apply_create_request_patch(
        current,
        {"device_name": "新名称", "quantity": 3, "unit": "台"},
    )
    assert (updated.device_name, updated.quantity, updated.unit) == ("新名称", 3, "台")


def test_invalid_field_does_not_enter_draft() -> None:
    current = CreateRequestDraft(device_name="交换机")
    with pytest.raises(ValidationError):
        apply_create_request_patch(current, {"status": "DRAFT"})
    assert current.model_dump(exclude_none=True) == {"device_name": "交换机"}


def test_invalid_quantity_does_not_replace_valid_value() -> None:
    current = CreateRequestDraft(quantity=2)
    with pytest.raises(ValidationError):
        apply_create_request_patch(current, {"quantity": 0})
    assert current.quantity == 2
