from typing import Any

from pydantic import BaseModel, ConfigDict

from buy_agent.domain.agent import ToolResult
from buy_agent.memory import (
    CreateRequestDraft,
    MemoryPatch,
    apply_create_request_patch,
    resolve_create_request_missing_fields,
    resolve_next_pending_field,
)
from buy_agent.tools.base import ToolExecutionContext
from buy_agent.tools.requester.common import RequesterTool


class SaveRequestDraftFieldsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: CreateRequestDraft


class SaveRequestDraftFieldsTool(RequesterTool):
    name = "save_request_draft_fields"
    description = (
        "只保存用户在当前消息中明确说出的采购草稿字段，不得推断未表达字段；"
        "一次明确提供多个字段时必须批量保存。"
    )
    arguments_model = SaveRequestDraftFieldsArgs

    async def execute(
        self, arguments: BaseModel, execution_context: ToolExecutionContext
    ) -> ToolResult:
        parsed = SaveRequestDraftFieldsArgs.model_validate(arguments)
        fields: dict[str, Any] = parsed.fields.model_dump(exclude_unset=True, exclude_none=True)
        if not fields:
            return ToolResult(False, "VALIDATION_ERROR", "没有可保存的有效采购字段。")
        current = CreateRequestDraft.model_validate(execution_context.memory.collected_data)
        projected = apply_create_request_patch(current, fields)
        missing = resolve_create_request_missing_fields(projected)
        pending = resolve_next_pending_field(missing)
        patch = MemoryPatch(
            collected_data_patch=fields,
            replace_missing_fields=missing,
            pending_field=pending,
            clear_awaiting_action=execution_context.memory.awaiting_action is not None,
            confirmed=False,
        )
        return ToolResult(
            True,
            "OK",
            f"已保存字段：{', '.join(fields)}；"
            f"仍缺少：{', '.join(missing) if missing else '无'}；"
            f"下一步建议询问：{pending or '无'}。",
            data={"saved_fields": fields, "missing_fields": missing, "pending_field": pending},
            memory_patch=patch,
        )
