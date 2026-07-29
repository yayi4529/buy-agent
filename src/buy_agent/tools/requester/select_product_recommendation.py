from pydantic import BaseModel, ConfigDict, Field

from buy_agent.domain.agent import ToolResult
from buy_agent.memory import (
    CreateRequestDraft,
    MemoryPatch,
    apply_create_request_patch,
    resolve_create_request_missing_fields,
)
from buy_agent.tools.base import ToolExecutionContext
from buy_agent.tools.requester.common import RequesterTool


class SelectProductRecommendationArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selection_index: int = Field(ge=1, le=3)


class SelectProductRecommendationTool(RequesterTool):
    name = "select_product_recommendation"
    description = "按用户所说的推荐序号选择最近推荐，不接受模型重传商品详情或内部 ID。"
    arguments_model = SelectProductRecommendationArgs

    async def execute(
        self, arguments: BaseModel, execution_context: ToolExecutionContext
    ) -> ToolResult:
        parsed = SelectProductRecommendationArgs.model_validate(arguments)
        reference = next(
            (
                item
                for item in execution_context.memory.last_recommendations
                if item.selection_index == parsed.selection_index
            ),
            None,
        )
        if reference is None:
            return ToolResult(False, "VALIDATION_ERROR", "找不到对应的最近推荐项。")
        product = await execution_context.backend_gateway.get_product_recommendation(
            principal=execution_context.principal,
            recommendation_id=str(reference.recommendation_id),
        )
        if (
            product is None
            or product.recommendation_id != str(reference.recommendation_id)
            or product.entity_id != str(reference.entity_id)
        ):
            return ToolResult(False, "VALIDATION_ERROR", "推荐引用与后端结果不一致。")
        fields = {
            "device_profession": product.device_profession,
            "device_name": product.device_name,
            "brand": product.brand,
            "model": product.model,
            "unit": product.unit,
        }
        current = CreateRequestDraft.model_validate(execution_context.memory.collected_data)
        projected = apply_create_request_patch(current, fields)
        missing = resolve_create_request_missing_fields(projected)
        return ToolResult(
            True,
            "OK",
            f"用户已确认第{parsed.selection_index}项：{product.brand} {product.model}。",
            data={"selected": fields, "missing_fields": missing},
            memory_patch=MemoryPatch(
                collected_data_patch=fields,
                replace_missing_fields=missing,
                replace_last_recommendations=(),
            ),
        )
