import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import NoReturn

from pydantic import ValidationError

from buy_agent.application.session_service import SessionService
from buy_agent.domain.action import (
    ActionCommand,
    ActionResult,
    ActionResultStatus,
    ActionType,
)
from buy_agent.domain.conversation import ConversationStatus
from buy_agent.domain.interaction import InteractionField, InteractionView
from buy_agent.memory import CreateRequestDraft, resolve_create_request_missing_fields
from buy_agent.ports.action_execution_store import (
    ActionExecutionStore,
    ActionStartStatus,
)
from buy_agent.ports.backend_gateway import (
    BackendGateway,
    CreatedPurchaseRequest,
    CreatePurchaseRequestCommand,
    HandlerCandidate,
)
from buy_agent.ports.lock_manager import LockManager
from buy_agent.ports.session_store import SessionStateVersionConflict

logger = logging.getLogger(__name__)


class _RejectedAction(Exception):
    def __init__(self, result: ActionResult) -> None:
        super().__init__(result.code)
        self.result = result


class ActionOrchestrator:
    def __init__(
        self,
        *,
        session_service: SessionService,
        backend_gateway: BackendGateway,
        action_execution_store: ActionExecutionStore,
        lock_manager: LockManager,
    ) -> None:
        self._sessions = session_service
        self._backend = backend_gateway
        self._executions = action_execution_store
        self._locks = lock_manager

    async def handle(self, command: ActionCommand) -> ActionResult:
        bundle = await self._sessions.get_by_conversation_id(command.conversation_id)
        if bundle is None:
            return _result(ActionResultStatus.NOT_FOUND, "CONVERSATION_NOT_FOUND", "会话不存在。")
        async with self._locks.lock(bundle.conversation.session_key):
            latest = await self._sessions.get_by_conversation_id(command.conversation_id)
            if latest is None:
                return _result(
                    ActionResultStatus.NOT_FOUND, "SESSION_NOT_FOUND", "会话状态不存在。"
                )
            started = await self._executions.try_start(
                action_token=command.action_token,
                action_type=command.action,
                conversation_id=command.conversation_id,
            )
            if started.status is not ActionStartStatus.STARTED:
                if started.status is ActionStartStatus.ALREADY_PROCESSING:
                    return _result(
                        ActionResultStatus.IN_PROGRESS,
                        "ACTION_IN_PROGRESS",
                        "操作正在处理中，请稍候。",
                    )
                if started.record.result is not None:
                    return started.record.result
                return _result(
                    ActionResultStatus.TECHNICAL_ERROR,
                    "ACTION_RESULT_UNAVAILABLE",
                    "操作结果暂不可用。",
                )
            try:
                return await self._submit(command, latest)
            except _RejectedAction as exc:
                await self._executions.mark_failed(
                    action_token=command.action_token,
                    error_code=exc.result.code,
                    result=exc.result,
                )
                return exc.result
            except Exception:
                logger.exception(
                    "submit request action failed",
                    extra={"conversation_id": command.conversation_id},
                )
                result = _result(
                    ActionResultStatus.TECHNICAL_ERROR,
                    "ACTION_EXECUTION_FAILED",
                    "提交失败，请重新生成确认操作后再试。问题编号：ACTION_EXECUTION_FAILED",
                )
                await self._executions.mark_failed(
                    action_token=command.action_token,
                    error_code=result.code,
                    result=result,
                )
                return result

    async def _submit(self, command: ActionCommand, bundle: object) -> ActionResult:
        # A local import keeps this method's signature precise without exposing store internals.
        from buy_agent.application.session_service import SessionBundle

        if not isinstance(bundle, SessionBundle):
            raise TypeError("invalid session bundle")
        conversation = bundle.conversation
        memory = bundle.memory
        if command.action != ActionType.SUBMIT_REQUEST:
            _reject(ActionResultStatus.VALIDATION_ERROR, "UNSUPPORTED_ACTION", "不支持该操作。")
        if conversation.status is not ConversationStatus.ACTIVE:
            _reject(ActionResultStatus.BUSINESS_ERROR, "CONVERSATION_NOT_ACTIVE", "会话已结束。")
        if conversation.purchase_request_id is not None or memory.purchase_request_id is not None:
            _reject(
                ActionResultStatus.BUSINESS_ERROR,
                "REQUEST_ALREADY_BOUND",
                "该会话已创建采购单。",
            )
        principal = command.principal
        if principal.user_id != conversation.employee_id:
            _reject(ActionResultStatus.PERMISSION_DENIED, "PRINCIPAL_MISMATCH", "无权操作该会话。")
        if principal.system_status != "ACTIVE" or "REQUESTER" not in principal.roles:
            _reject(
                ActionResultStatus.PERMISSION_DENIED, "PERMISSION_DENIED", "当前用户无提交权限。"
            )
        if memory.current_action != "CREATE_REQUEST":
            _reject(
                ActionResultStatus.BUSINESS_ERROR,
                "INVALID_CURRENT_ACTION",
                "当前不是采购创建流程。",
            )
        awaiting = memory.awaiting_action
        if awaiting is None:
            _reject(
                ActionResultStatus.VERSION_CONFLICT,
                "INVALID_AWAITING_ACTION",
                "采购信息已变化，请重新确认。",
            )
        if awaiting.action_type not in {"submit_request", ActionType.SUBMIT_REQUEST}:
            _reject(
                ActionResultStatus.VALIDATION_ERROR,
                "ACTION_TYPE_MISMATCH",
                "确认操作类型无效。",
            )
        if (
            awaiting.expires_at <= datetime.now(UTC)
            or command.action_token != awaiting.action_token
        ):
            _reject(
                ActionResultStatus.VALIDATION_ERROR,
                "INVALID_ACTION_TOKEN",
                "确认操作已失效，请重新确认。",
            )
        if (
            command.expected_state_version != awaiting.expected_state_version
            or command.expected_state_version != memory.state_version
        ):
            _reject(
                ActionResultStatus.VERSION_CONFLICT,
                "STATE_VERSION_CONFLICT",
                "采购信息已变化，请重新确认。",
            )
        try:
            draft = CreateRequestDraft.model_validate(memory.collected_data)
        except ValidationError:
            _reject(
                ActionResultStatus.VALIDATION_ERROR,
                "INVALID_DRAFT",
                "采购草稿字段无效，请重新填写。",
            )
        missing = resolve_create_request_missing_fields(draft)
        if missing:
            _reject(
                ActionResultStatus.VALIDATION_ERROR,
                "MISSING_REQUIRED_FIELDS",
                f"采购草稿仍缺少字段：{', '.join(missing)}。",
            )
        if draft.building_id is None:
            _reject(ActionResultStatus.VALIDATION_ERROR, "BUILDING_REQUIRED", "请选择楼宇。")
        buildings = await self._backend.list_available_buildings(principal=principal)
        building = next((item for item in buildings if item.building_id == draft.building_id), None)
        if building is None:
            _reject(ActionResultStatus.PERMISSION_DENIED, "INVALID_BUILDING", "所选楼宇已失效。")
        candidates = await self._backend.list_reviewer_candidates(
            principal=principal, building_id=draft.building_id
        )
        reviewer_id = _reviewer_id(command, awaiting.payload)
        reviewer = next((item for item in candidates if item.employee_id == reviewer_id), None)
        if reviewer is None:
            _reject(
                ActionResultStatus.BUSINESS_ERROR,
                "INVALID_REVIEWER",
                "所选处理人已失效，请重新选择并确认。",
            )
        created = await self._create(principal, draft, reviewer, command.action_token)
        try:
            await self._sessions.bind_purchase_request_and_complete(
                conversation_id=command.conversation_id,
                request_id=created.request_id,
                expected_state_version=command.expected_state_version,
            )
        except SessionStateVersionConflict:
            _reject(
                ActionResultStatus.VERSION_CONFLICT,
                "STATE_VERSION_CONFLICT",
                "采购信息已变化，请重新确认。",
            )
        interaction = InteractionView(
            view_type="request_submission_success",
            title="采购申请已提交",
            fields=(
                InteractionField("采购单编号", created.request_no),
                InteractionField("设备名称", draft.device_name or ""),
                InteractionField("数量和单位", f"{draft.quantity}{draft.unit}"),
                InteractionField("所属楼宇", building.building_name),
                InteractionField("当前状态", created.status),
                InteractionField("下一处理人", reviewer.display_label),
            ),
            fallback_text=f"采购申请 {created.request_no} 已提交。",
        )
        result = ActionResult(
            ActionResultStatus.SUCCESS,
            "REQUEST_SUBMITTED",
            "采购申请已提交。",
            {
                "request_id": created.request_id,
                "request_no": created.request_no,
                "status": created.status,
                "current_handler_employee_id": created.current_handler_employee_id,
            },
            interaction,
        )
        await self._executions.mark_completed(action_token=command.action_token, result=result)
        return result

    async def _create(
        self,
        principal: object,
        draft: CreateRequestDraft,
        reviewer: HandlerCandidate,
        action_token: str,
    ) -> CreatedPurchaseRequest:
        from buy_agent.domain.identity import CurrentPrincipal

        if not isinstance(principal, CurrentPrincipal):
            raise TypeError("invalid principal")
        assert draft.building_id is not None
        assert draft.device_profession is not None
        assert draft.device_name is not None
        assert draft.quantity is not None
        assert draft.unit is not None
        assert draft.application_reason is not None
        command = CreatePurchaseRequestCommand(
            building_id=draft.building_id,
            device_profession=draft.device_profession,
            device_name=draft.device_name,
            brand=draft.brand,
            model=draft.model,
            quantity=draft.quantity,
            unit=draft.unit,
            application_reason=draft.application_reason,
            applicant_remark=draft.applicant_remark,
            reviewer_employee_id=reviewer.employee_id,
            idempotency_key=action_token,
        )
        try:
            return await self._backend.create_purchase_request(principal=principal, command=command)
        except PermissionError:
            _reject(
                ActionResultStatus.PERMISSION_DENIED, "BACKEND_PERMISSION_DENIED", "后端拒绝提交。"
            )
        except ValueError:
            _reject(
                ActionResultStatus.BUSINESS_ERROR, "BACKEND_VALIDATION_ERROR", "提交字段校验失败。"
            )


def _reviewer_id(command: ActionCommand, awaiting_payload: Mapping[str, object]) -> int | None:
    if not isinstance(awaiting_payload, Mapping):
        return None
    awaiting_value = awaiting_payload.get("reviewer_employee_id")
    command_value = command.payload.get("reviewer_employee_id")
    value = command_value if command_value is not None else awaiting_value
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _result(status: ActionResultStatus, code: str, message: str) -> ActionResult:
    return ActionResult(status, code, message)


def _reject(status: ActionResultStatus, code: str, message: str) -> NoReturn:
    raise _RejectedAction(_result(status, code, message))
