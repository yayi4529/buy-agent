from pydantic import BaseModel, ConfigDict, Field

from buy_agent.domain.agent import ToolResult
from buy_agent.memory import MemoryPatch, RecommendationReference
from buy_agent.tools.base import ToolExecutionContext
from buy_agent.tools.requester.common import RequesterTool


class RecommendProductsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)
    device_profession: str | None = None
    device_name: str | None = None
    brand_preference: str | None = None
    limit: int = Field(default=3, ge=1, le=3)


class RecommendProductsTool(RequesterTool):
    name = "recommend_products"
    description = "从后端查询最多三条商品推荐；不得自行生成品牌、型号或价格。"
    arguments_model = RecommendProductsArgs

    async def execute(
        self, arguments: BaseModel, execution_context: ToolExecutionContext
    ) -> ToolResult:
        parsed = RecommendProductsArgs.model_validate(arguments)
        products = await execution_context.backend_gateway.recommend_products(
            principal=execution_context.principal,
            query=parsed.query,
            device_profession=parsed.device_profession,
            device_name=parsed.device_name,
            brand_preference=parsed.brand_preference,
            limit=parsed.limit,
        )
        references = tuple(
            RecommendationReference(
                index,
                item.recommendation_id,
                "product",
                item.entity_id,
                f"{item.brand} {item.model}",
            )
            for index, item in enumerate(products[:3], start=1)
        )
        data = {
            "recommendations": [
                {
                    "selection_index": index,
                    "recommendation_id": item.recommendation_id,
                    "entity_id": item.entity_id,
                    "device_profession": item.device_profession,
                    "device_name": item.device_name,
                    "brand": item.brand,
                    "model": item.model,
                    "unit": item.unit,
                    "reference_price": item.reference_price,
                    "match_explanation": item.match_explanation,
                }
                for index, item in enumerate(products[:3], start=1)
            ]
        }
        return ToolResult(
            True,
            "OK",
            "未找到匹配的商品推荐。"
            if not products
            else "已返回后端商品候选，请等待用户明确选择。",
            data=data,
            memory_patch=MemoryPatch(replace_last_recommendations=references),
        )
