from pydantic import BaseModel, ConfigDict

from buy_agent.domain.agent import ToolResult
from buy_agent.memory import (
    CreateRequestDraft,
    MemoryPatch,
    apply_create_request_patch,
    resolve_create_request_missing_fields,
)
from buy_agent.tools.base import ToolExecutionContext
from buy_agent.tools.requester.common import RequesterTool


class ListAvailableBuildingsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListAvailableBuildingsTool(RequesterTool):
    name = "list_available_buildings"
    description = "查询系统提供的当前用户合法楼宇；不得传入员工身份或猜测楼宇编号。"
    arguments_model = ListAvailableBuildingsArgs

    async def execute(
        self, arguments: BaseModel, execution_context: ToolExecutionContext
    ) -> ToolResult:
        ListAvailableBuildingsArgs.model_validate(arguments)
        options = await execution_context.backend_gateway.list_available_buildings(
            principal=execution_context.principal
        )
        data = {
            "buildings": [
                {
                    "building_id": item.building_id,
                    "building_name": item.building_name,
                    "is_primary": item.is_primary,
                }
                for item in options
            ]
        }
        if not options:
            return ToolResult(
                False,
                "BUSINESS_ERROR",
                "当前没有可用楼宇，请联系管理员维护楼宇关系。",
                data=data,
            )
        if len(options) > 1:
            return ToolResult(True, "OK", "请让用户从合法楼宇中选择一个。", data=data)
        building = options[0]
        current = CreateRequestDraft.model_validate(execution_context.memory.collected_data)
        projected = apply_create_request_patch(current, {"building_id": building.building_id})
        missing = resolve_create_request_missing_fields(projected)
        return ToolResult(
            True,
            "OK",
            f"当前用户仅有一个合法楼宇，已选择{building.building_name}。",
            data=data,
            memory_patch=MemoryPatch(
                collected_data_patch={"building_id": building.building_id},
                replace_missing_fields=missing,
            ),
        )
