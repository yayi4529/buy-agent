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


class SelectBuildingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    building_id: int = Field(gt=0)


class SelectBuildingTool(RequesterTool):
    name = "select_building"
    description = "按用户选择确认系统返回的合法楼宇，不得猜测楼宇编号。"
    arguments_model = SelectBuildingArgs

    async def execute(
        self, arguments: BaseModel, execution_context: ToolExecutionContext
    ) -> ToolResult:
        parsed = SelectBuildingArgs.model_validate(arguments)
        options = await execution_context.backend_gateway.list_available_buildings(
            principal=execution_context.principal
        )
        selected = next((item for item in options if item.building_id == parsed.building_id), None)
        if selected is None:
            return ToolResult(False, "PERMISSION_DENIED", "所选楼宇不在当前用户合法范围内。")
        current = CreateRequestDraft.model_validate(execution_context.memory.collected_data)
        projected = apply_create_request_patch(current, {"building_id": selected.building_id})
        missing = resolve_create_request_missing_fields(projected)
        return ToolResult(
            True,
            "OK",
            f"已选择楼宇：{selected.building_name}。",
            data={
                "building_id": selected.building_id,
                "building_name": selected.building_name,
                "missing_fields": missing,
            },
            memory_patch=MemoryPatch(
                collected_data_patch={"building_id": selected.building_id},
                replace_missing_fields=missing,
            ),
        )
