from buy_agent.tools.base import AgentTool
from buy_agent.tools.registry import ToolRegistry
from buy_agent.tools.requester.common import ActionTokenFactory
from buy_agent.tools.requester.list_available_buildings import ListAvailableBuildingsTool
from buy_agent.tools.requester.prepare_request_submission import PrepareRequestSubmissionTool
from buy_agent.tools.requester.recommend_products import RecommendProductsTool
from buy_agent.tools.requester.save_request_draft_fields import SaveRequestDraftFieldsTool
from buy_agent.tools.requester.select_building import SelectBuildingTool
from buy_agent.tools.requester.select_product_recommendation import (
    SelectProductRecommendationTool,
)

REQUESTER_TOOL_NAMES = frozenset(
    {
        "save_request_draft_fields",
        "list_available_buildings",
        "select_building",
        "recommend_products",
        "select_product_recommendation",
        "prepare_request_submission",
    }
)


def build_requester_tool_registry(
    token_factory: ActionTokenFactory | None = None,
) -> ToolRegistry:
    tools = cast(
        tuple[AgentTool, ...],
        (
            SaveRequestDraftFieldsTool(),
            ListAvailableBuildingsTool(),
            SelectBuildingTool(),
            RecommendProductsTool(),
            SelectProductRecommendationTool(),
            PrepareRequestSubmissionTool(token_factory),
        ),
    )
    return ToolRegistry(tools)


__all__ = ["REQUESTER_TOOL_NAMES", "build_requester_tool_registry"]
from typing import cast
