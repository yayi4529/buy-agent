from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.domain.requirement import RequirementContext

_ROLE_TOOLS = {
    "REQUESTER": {
        "create_requirement_draft",
        "query_purchase_records",
        "save_requester_fields",
        "recommend_device_types",
        "recommend_brands",
        "recommend_models",
        "cancel_requirement",
        "submit_for_review",
    },
    "REVIEWER": {"approve_requirement", "reject_requirement", "get_requirement_detail"},
    "PURCHASER": {"query_supplier_profile", "save_purchaser_fields"},
    "WAREHOUSE": {"save_warehouse_fields", "complete_warehouse_entry"},
}

_STATUS_TOOLS = {
    None: {"create_requirement_draft", "query_purchase_records"},
    "DRAFT": {
        "save_requester_fields",
        "recommend_device_types",
        "recommend_brands",
        "recommend_models",
        "cancel_requirement",
    },
    "READY_TO_SUBMIT": {
        "save_requester_fields",
        "submit_for_review",
        "cancel_requirement",
    },
    "PENDING_REVIEW": {"approve_requirement", "reject_requirement", "get_requirement_detail"},
    "PURCHASER_FILLING": {"query_supplier_profile", "save_purchaser_fields"},
    "PENDING_WAREHOUSE": {"save_warehouse_fields", "complete_warehouse_entry"},
}


class ToolPolicy:
    def allowed_tools(
        self, principal: CurrentPrincipal, requirement: RequirementContext | None
    ) -> frozenset[str]:
        role_tools: set[str] = set()
        for role in principal.roles:
            role_tools.update(_ROLE_TOOLS.get(role, set()))
        status = requirement.status if requirement is not None else None
        return frozenset(role_tools & _STATUS_TOOLS.get(status, set()))
