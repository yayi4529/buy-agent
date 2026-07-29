import json
from collections.abc import Mapping
from typing import Any

from buy_agent.adapters.channels.feishu.errors import ChannelEventFormatError
from buy_agent.adapters.channels.feishu.models import FeishuMessageKind, FeishuParsedEvent
from buy_agent.domain.enums import ChannelType, InboundEventType
from buy_agent.domain.events import InboundEvent
from buy_agent.domain.identity import ExternalIdentity


class FeishuEventAdapter:
    def parse(self, raw_event: object) -> FeishuParsedEvent:
        root = _mapping(raw_event, "event")
        header = _mapping(root.get("header"), "header")
        event = _mapping(root.get("event"), "event body")
        message = _mapping(event.get("message"), "message")
        sender = _mapping(event.get("sender"), "sender")
        sender_id = _mapping(sender.get("sender_id"), "sender_id")

        event_id = _required_str(header.get("event_id") or root.get("event_id"), "event_id")
        tenant = _required_str(header.get("tenant_key") or root.get("tenant_key"), "tenant_key")
        message_id = _required_str(message.get("message_id"), "message_id")
        open_id = _required_str(sender_id.get("open_id"), "sender.open_id")
        chat_id = _required_str(message.get("chat_id"), "chat_id")
        chat_type = _required_str(message.get("chat_type"), "chat_type")
        message_type = _required_str(message.get("message_type"), "message_type")
        text: str | None = None
        if message_type == "text":
            content = message.get("content")
            try:
                decoded = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError as exc:
                raise ChannelEventFormatError("invalid text content") from exc
            if not isinstance(decoded, Mapping) or not isinstance(decoded.get("text"), str):
                raise ChannelEventFormatError("text content is missing")
            text = decoded["text"].strip()
            if not text:
                raise ChannelEventFormatError("text content must not be empty")
            kind = FeishuMessageKind.TEXT
        elif message_type == "image":
            kind = FeishuMessageKind.IMAGE
        else:
            kind = FeishuMessageKind.UNSUPPORTED
        identity = ExternalIdentity(ChannelType.FEISHU, tenant, open_id)
        inbound = (
            InboundEvent(
                event_id=event_id,
                message_id=message_id,
                event_type=InboundEventType.TEXT_MESSAGE,
                identity=identity,
                conversation_id=chat_id,
                text=text,
                action=None,
                raw_payload={},
            )
            if kind is FeishuMessageKind.TEXT and chat_type == "p2p"
            else None
        )
        timestamp_raw = message.get("create_time") or header.get("create_time")
        timestamp = (
            int(timestamp_raw)
            if isinstance(timestamp_raw, (str, int))
            and not isinstance(timestamp_raw, bool)
            and str(timestamp_raw).isdigit()
            else None
        )
        return FeishuParsedEvent(
            event_id,
            message_id,
            tenant,
            open_id,
            chat_id,
            chat_type,
            kind,
            text,
            timestamp,
            inbound,
        )


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ChannelEventFormatError(f"{name} must be an object")
    return value


def _required_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChannelEventFormatError(f"{name} is required")
    return value.strip()
