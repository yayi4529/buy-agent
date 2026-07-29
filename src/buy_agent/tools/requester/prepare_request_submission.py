from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict

from buy_agent.domain.agent import ToolResult
from buy_agent.domain.interaction import (
    InteractionAction,
    InteractionField,
    InteractionView,
    SelectionGroup,
    SelectionOption,
)
from buy_agent.memory import (
    AwaitingAction,
    CreateRequestDraft,
    MemoryPatch,
    resolve_create_request_missing_fields,
    resolve_next_pending_field,
)
from buy_agent.tools.base import ToolExecutionContext
from buy_agent.tools.requester.common import (
    ActionTokenFactory,
    RequesterTool,
    UUIDActionTokenFactory,
)


class PrepareRequestSubmissionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrepareRequestSubmissionTool(RequesterTool):
    name = "prepare_request_submission"
    description = "草稿完整后生成确认交互；只做准备，不创建正式采购单。"
    arguments_model = PrepareRequestSubmissionArgs

    def __init__(self, token_factory: ActionTokenFactory | None = None) -> None:
        self._token_factory = token_factory or UUIDActionTokenFactory()

    async def execute(
        self, arguments: BaseModel, execution_context: ToolExecutionContext
    ) -> ToolResult:
        PrepareRequestSubmissionArgs.model_validate(arguments)
        draft = CreateRequestDraft.model_validate(execution_context.memory.collected_data)
        missing = resolve_create_request_missing_fields(draft)
        pending = resolve_next_pending_field(missing)
        if missing:
            return ToolResult(
                False,
                "VALIDATION_ERROR",
                f"草稿仍缺少：{', '.join(missing)}；下一步询问：{pending}。",
                data={"missing_fields": missing, "pending_field": pending},
            )
        buildings = await execution_context.backend_gateway.list_available_buildings(
            principal=execution_context.principal
        )
        building = next((item for item in buildings if item.building_id == draft.building_id), None)
        if building is None:
            return ToolResult(False, "PERMISSION_DENIED", "草稿楼宇不在当前用户合法范围内。")
        reviewers = await execution_context.backend_gateway.list_reviewer_candidates(
            principal=execution_context.principal,
            building_id=building.building_id,
        )
        if not reviewers:
            return ToolResult(False, "BUSINESS_ERROR", "当前楼宇没有合法楼长候选人。")

        token = self._token_factory.create()
        expected_version = execution_context.memory.state_version + 1
        selected_reviewer = reviewers[0] if len(reviewers) == 1 else None
        payload = {
            "conversation_id": execution_context.memory.conversation_id,
            "expected_state_version": expected_version,
            "reviewer_employee_id": (selected_reviewer.employee_id if selected_reviewer else None),
        }
        awaiting = AwaitingAction(
            action_type="submit_request",
            action_token=token,
            interaction_id=f"submit:{token}",
            expected_state_version=expected_version,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            payload=payload,
        )
        groups: tuple[SelectionGroup, ...] = ()
        if len(reviewers) > 1:
            groups = (
                SelectionGroup(
                    "reviewer_employee_id",
                    "楼长",
                    tuple(
                        SelectionOption(str(item.employee_id), item.display_label)
                        for item in reviewers
                    ),
                ),
            )
        fields = (
            InteractionField("所属楼宇", building.building_name),
            InteractionField("设备专业", draft.device_profession or ""),
            InteractionField("设备名称", draft.device_name or ""),
            InteractionField("品牌", draft.brand or ""),
            InteractionField("型号", draft.model or ""),
            InteractionField("数量和单位", f"{draft.quantity}{draft.unit}"),
            InteractionField("申请原因", draft.application_reason or ""),
            InteractionField("备注", draft.applicant_remark or ""),
            InteractionField(
                "楼长",
                selected_reviewer.display_label if selected_reviewer else "请选择楼长",
            ),
        )
        interaction = InteractionView(
            "request_submission_confirmation",
            "确认采购申请",
            fields,
            groups,
            (
                InteractionAction(
                    "submit_request",
                    "确认提交",
                    {
                        "action_token": token,
                        "conversation_id": execution_context.memory.conversation_id,
                        "expected_state_version": expected_version,
                    },
                ),
            ),
        )
        return ToolResult(
            True,
            "OK",
            "已生成提交确认交互，正式采购单尚未创建。",
            data={"confirmed": False, "purchase_request_id": None},
            memory_patch=MemoryPatch(awaiting_action=awaiting, confirmed=False),
            interaction=interaction,
        )
