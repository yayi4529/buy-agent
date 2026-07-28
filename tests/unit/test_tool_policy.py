import pytest

from buy_agent.adapters.backend.fake_backend_gateway import fake_requirement
from buy_agent.application.tool_policy import ToolPolicy
from buy_agent.domain.identity import CurrentPrincipal


def principal(*roles: str) -> CurrentPrincipal:
    return CurrentPrincipal(1, "u", frozenset(roles), (), (), "ACTIVE")


@pytest.mark.parametrize(
    ("role", "status", "expected"),
    [
        ("REQUESTER", None, {"create_requirement_draft", "query_purchase_records"}),
        (
            "REQUESTER",
            "DRAFT",
            {
                "save_requester_fields",
                "recommend_device_types",
                "recommend_brands",
                "recommend_models",
                "cancel_requirement",
            },
        ),
        (
            "REQUESTER",
            "READY_TO_SUBMIT",
            {"save_requester_fields", "submit_for_review", "cancel_requirement"},
        ),
        (
            "REVIEWER",
            "PENDING_REVIEW",
            {"approve_requirement", "reject_requirement", "get_requirement_detail"},
        ),
        (
            "PURCHASER",
            "PURCHASER_FILLING",
            {"query_supplier_profile", "save_purchaser_fields"},
        ),
        (
            "WAREHOUSE",
            "PENDING_WAREHOUSE",
            {"save_warehouse_fields", "complete_warehouse_entry"},
        ),
    ],
)
def test_role_and_status_intersection(role: str, status: str | None, expected: set[str]) -> None:
    requirement = fake_requirement(1, status) if status else None
    assert ToolPolicy().allowed_tools(principal(role), requirement) == expected


def test_multiple_roles_are_merged_before_status_filter() -> None:
    tools = ToolPolicy().allowed_tools(
        principal("REQUESTER", "REVIEWER"), fake_requirement(1, "PENDING_REVIEW")
    )
    assert tools == {"approve_requirement", "reject_requirement", "get_requirement_detail"}


def test_terminal_status_exposes_no_mutation_tools() -> None:
    assert (
        ToolPolicy().allowed_tools(
            principal("REQUESTER", "REVIEWER"), fake_requirement(1, "COMPLETED")
        )
        == frozenset()
    )
