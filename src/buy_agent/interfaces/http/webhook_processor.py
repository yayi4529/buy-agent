import asyncio
import importlib
import json
from collections.abc import Mapping
from typing import Any, Protocol

from buy_agent.adapters.channels.feishu.handlers import (
    FeishuActionHandler,
    FeishuMessageHandler,
)
from buy_agent.interfaces.http.models import (
    FeishuDecryptionError,
    FeishuEventFormatError,
    FeishuSignatureError,
    FeishuWebhookResponse,
)

MESSAGE_EVENT = "im.message.receive_v1"
CARD_ACTION_EVENT = "card.action.trigger"


class FeishuSecurityAdapter(Protocol):
    def decode_and_validate(
        self, *, headers: Mapping[str, str], body: bytes
    ) -> tuple[dict[str, Any] | None, FeishuWebhookResponse | None]: ...


class LarkOapiSecurityAdapter:
    """Small bridge around lark-oapi's official webhook dispatcher."""

    def __init__(self, *, encrypt_key: str, verification_token: str) -> None:
        self._encrypt_key = encrypt_key
        self._verification_token = verification_token

    def decode_and_validate(
        self, *, headers: Mapping[str, str], body: bytes
    ) -> tuple[dict[str, Any] | None, FeishuWebhookResponse | None]:
        lark = importlib.import_module("lark_oapi")
        captured: dict[str, Any] = {}

        def capture_event(value: object) -> None:
            captured["payload"] = json.loads(lark.JSON.marshal(value))

        def capture_action(value: object) -> object:
            captured["payload"] = json.loads(lark.JSON.marshal(value))
            callback = importlib.import_module(
                "lark_oapi.event.callback.model.p2_card_action_trigger"
            )
            return callback.P2CardActionTriggerResponse({})

        builder = lark.EventDispatcherHandler.builder(self._encrypt_key, self._verification_token)
        builder.register_p2_im_message_receive_v1(capture_event)
        builder.register_p2_card_action_trigger(capture_action)
        event_type = _plain_event_type(body)
        if event_type not in {None, MESSAGE_EVENT, CARD_ACTION_EVENT}:
            builder.register_p2_customized_event(event_type, capture_event)
        dispatcher = builder.build()
        raw_request = lark.RawRequest()
        raw_request.uri = "/webhooks/feishu"
        raw_request.headers = _sdk_headers(headers)
        raw_request.body = body
        response = dispatcher.do(raw_request)
        content = response.content or b"{}"
        try:
            response_body = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response_body = {"msg": "invalid Feishu response"}
        if response.status_code != 200:
            message = str(response_body.get("msg", "")).lower()
            if "decrypt" in message or "encrypt" in message:
                raise FeishuDecryptionError("Feishu payload decryption failed")
            if "sign" in message or "token" in message or "access" in message:
                raise FeishuSignatureError("Feishu request authentication failed")
            raise FeishuEventFormatError("Feishu event validation failed")
        if "challenge" in response_body:
            return None, FeishuWebhookResponse(200, {"challenge": response_body["challenge"]})
        payload = captured.get("payload")
        if not isinstance(payload, dict):
            return None, FeishuWebhookResponse()
        return payload, None


class FeishuWebhookProcessor:
    def __init__(
        self,
        *,
        security: FeishuSecurityAdapter,
        message_handler: FeishuMessageHandler,
        action_handler: FeishuActionHandler,
    ) -> None:
        self._security = security
        self._message_handler = message_handler
        self._action_handler = action_handler

    async def handle(self, *, headers: Mapping[str, str], body: bytes) -> FeishuWebhookResponse:
        try:
            payload, immediate = await asyncio.to_thread(
                self._security.decode_and_validate, headers=headers, body=body
            )
        except (FeishuSignatureError, FeishuDecryptionError, FeishuEventFormatError):
            raise
        except Exception as exc:
            raise FeishuEventFormatError("Feishu event validation failed") from exc
        if immediate is not None:
            return immediate
        if payload is None:
            return FeishuWebhookResponse()
        event_type = _event_type(payload)
        try:
            if event_type == MESSAGE_EVENT:
                await self._message_handler.handle(payload)
            elif event_type == CARD_ACTION_EVENT:
                await self._action_handler.handle(payload)
        except Exception:  # noqa: BLE001 - valid deliveries must not trigger platform retries
            # A valid event is acknowledged even if downstream business handling fails.
            return FeishuWebhookResponse(200, {"msg": "accepted"})
        return FeishuWebhookResponse()


def _event_type(payload: Mapping[str, Any]) -> str | None:
    header = payload.get("header")
    if isinstance(header, Mapping) and isinstance(header.get("event_type"), str):
        value = header["event_type"]
        return value if isinstance(value, str) else None
    return None


def _plain_event_type(body: bytes) -> str | None:
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping) or value.get("encrypt"):
        return None
    return _event_type(value)


def _sdk_headers(headers: Mapping[str, str]) -> dict[str, str]:
    result = dict(headers)
    by_lower = {name.lower(): value for name, value in headers.items()}
    for name in (
        "X-Lark-Request-Timestamp",
        "X-Lark-Request-Nonce",
        "X-Lark-Signature",
        "X-Request-Id",
    ):
        value = by_lower.get(name.lower())
        if value is not None:
            result[name] = value
    return result
