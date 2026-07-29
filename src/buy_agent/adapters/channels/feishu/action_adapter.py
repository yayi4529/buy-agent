from collections.abc import Mapping
from typing import Any

from buy_agent.adapters.channels.feishu.errors import ChannelEventFormatError
from buy_agent.adapters.channels.feishu.models import FeishuActionInput
from buy_agent.domain.action import ActionCommand, ActionType
from buy_agent.domain.identity import CurrentPrincipal


class FeishuActionAdapter:
    def parse(self, raw_callback: object) -> FeishuActionInput:
        root = _mapping(raw_callback, "callback")
        header = _mapping(root.get("header"), "header")
        event = _mapping(root.get("event"), "event")
        operator = _mapping(event.get("operator"), "operator")
        operator_id = _mapping(operator.get("operator_id") or operator, "operator_id")
        action_obj = _mapping(event.get("action"), "action")
        value = _mapping(action_obj.get("value"), "action.value")
        action = _required(value.get("action"), "action").upper()
        if action not in {"SUBMIT_REQUEST", "SUBMIT_REQUEST".lower().upper()}:
            raise ChannelEventFormatError("unsupported action")
        reviewer = _optional_positive_int(value.get("reviewer_employee_id"), "reviewer_employee_id")
        return FeishuActionInput(
            callback_event_id=_required(header.get("event_id") or root.get("event_id"), "event_id"),
            tenant_key=_required(header.get("tenant_key") or root.get("tenant_key"), "tenant_key"),
            operator_open_id=_required(
                operator_id.get("open_id") or operator.get("open_id"), "operator.open_id"
            ),
            external_interaction_id=_required(
                event.get("context", {}).get("open_message_id")
                if isinstance(event.get("context"), Mapping)
                else None,
                "open_message_id",
            ),
            action=ActionType.SUBMIT_REQUEST,
            action_token=_required(value.get("action_token"), "action_token"),
            conversation_id=_positive_int(value.get("conversation_id"), "conversation_id"),
            expected_state_version=_nonnegative_int(
                value.get("expected_state_version"), "expected_state_version"
            ),
            reviewer_employee_id=reviewer,
        )

    def to_command(
        self, action_input: FeishuActionInput, principal: CurrentPrincipal
    ) -> ActionCommand:
        payload = (
            {"reviewer_employee_id": action_input.reviewer_employee_id}
            if action_input.reviewer_employee_id is not None
            else {}
        )
        return ActionCommand(
            action_input.action,
            action_input.action_token,
            action_input.conversation_id,
            action_input.expected_state_version,
            principal,
            payload,
        )


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ChannelEventFormatError(f"{name} must be an object")
    return value


def _required(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChannelEventFormatError(f"{name} is required")
    return value.strip()


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ChannelEventFormatError(f"{name} must be an integer")
    if not isinstance(value, (str, int)):
        raise ChannelEventFormatError(f"{name} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ChannelEventFormatError(f"{name} must be an integer") from exc


def _positive_int(value: object, name: str) -> int:
    parsed = _integer(value, name)
    if parsed < 1:
        raise ChannelEventFormatError(f"{name} must be positive")
    return parsed


def _nonnegative_int(value: object, name: str) -> int:
    parsed = _integer(value, name)
    if parsed < 0:
        raise ChannelEventFormatError(f"{name} must not be negative")
    return parsed


def _optional_positive_int(value: object, name: str) -> int | None:
    return None if value is None or value == "" else _positive_int(value, name)
