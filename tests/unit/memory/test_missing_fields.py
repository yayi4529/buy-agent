from buy_agent.memory import (
    CREATE_REQUEST_REQUIRED_FIELDS,
    CreateRequestDraft,
    resolve_create_request_missing_fields,
    resolve_next_pending_field,
)


def complete_data() -> dict[str, object]:
    return {
        "building_id": 10,
        "device_profession": "网络",
        "device_name": "交换机",
        "quantity": 5,
        "unit": "台",
        "application_reason": "网络扩容",
    }


def test_empty_draft_returns_all_required_fields_in_order() -> None:
    assert (
        resolve_create_request_missing_fields(CreateRequestDraft())
        == CREATE_REQUEST_REQUIRED_FIELDS
    )


def test_partial_draft_returns_missing_fields_in_fixed_order() -> None:
    draft = CreateRequestDraft(building_id=1, device_name="交换机", unit="台")
    assert resolve_create_request_missing_fields(draft) == (
        "device_profession",
        "quantity",
        "application_reason",
    )


def test_complete_draft_has_no_missing_fields() -> None:
    assert (
        resolve_create_request_missing_fields(CreateRequestDraft.model_validate(complete_data()))
        == ()
    )


def test_optional_fields_are_not_required() -> None:
    draft = CreateRequestDraft.model_validate(complete_data())
    assert draft.brand is None and draft.model is None and draft.applicant_remark is None
    assert resolve_create_request_missing_fields(draft) == ()


def test_whitespace_string_is_missing() -> None:
    data = complete_data()
    data["application_reason"] = " \t "
    assert resolve_create_request_missing_fields(CreateRequestDraft.model_validate(data)) == (
        "application_reason",
    )


def test_next_pending_field_uses_first_or_none() -> None:
    assert resolve_next_pending_field(("quantity", "unit")) == "quantity"
    assert resolve_next_pending_field(()) is None
