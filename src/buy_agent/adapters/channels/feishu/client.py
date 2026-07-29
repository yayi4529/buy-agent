import asyncio
import importlib
import json
from typing import Protocol

from buy_agent.adapters.channels.feishu.errors import (
    ChannelAuthenticationError,
    ChannelError,
    ChannelPermissionError,
    ChannelRateLimitError,
    ChannelRequestError,
    ChannelTimeoutError,
)
from buy_agent.bootstrap.settings import Settings
from buy_agent.ports.channel import ChannelDeliveryResult, RenderedInteraction


class FeishuTransport(Protocol):
    async def reply(
        self, message_id: str, message_type: str, content: str, timeout: float
    ) -> tuple[str | None, int | None]: ...

    async def update_card(
        self, message_id: str, content: str, timeout: float
    ) -> tuple[str | None, int | None]: ...


class FeishuChannelClient:
    def __init__(self, settings: Settings, transport: FeishuTransport | None = None) -> None:
        if not settings.feishu_app_id or not settings.feishu_app_secret:
            raise ValueError("Feishu app id and app secret are required")
        self._timeout = settings.feishu_request_timeout_seconds
        self._transport = transport or _LarkOapiTransport(
            settings.feishu_app_id, settings.feishu_app_secret
        )

    async def reply_text(self, *, external_message_id: str, text: str) -> ChannelDeliveryResult:
        return await self._reply(external_message_id, "text", json.dumps({"text": text}))

    async def reply_interaction(
        self, *, external_message_id: str, interaction: RenderedInteraction
    ) -> ChannelDeliveryResult:
        return await self._reply(
            external_message_id,
            "interactive",
            json.dumps(interaction.payload, ensure_ascii=False),
        )

    async def update_interaction(
        self, *, external_interaction_id: str, interaction: RenderedInteraction
    ) -> ChannelDeliveryResult:
        try:
            identifier, code = await self._transport.update_card(
                external_interaction_id,
                json.dumps(interaction.payload, ensure_ascii=False),
                self._timeout,
            )
        except Exception as exc:
            raise _map_error(exc) from exc
        return ChannelDeliveryResult(identifier, code)

    async def _reply(
        self, message_id: str, message_type: str, content: str
    ) -> ChannelDeliveryResult:
        try:
            identifier, code = await self._transport.reply(
                message_id, message_type, content, self._timeout
            )
        except Exception as exc:
            raise _map_error(exc) from exc
        return ChannelDeliveryResult(identifier, code)


class FakeFeishuClient:
    def __init__(self) -> None:
        self.reply_text_calls: list[tuple[str, str]] = []
        self.reply_interaction_calls: list[tuple[str, RenderedInteraction]] = []
        self.update_interaction_calls: list[tuple[str, RenderedInteraction]] = []
        self.failure: ChannelError | None = None

    @property
    def last_text(self) -> str | None:
        return self.reply_text_calls[-1][1] if self.reply_text_calls else None

    @property
    def last_interaction(self) -> RenderedInteraction | None:
        if self.update_interaction_calls:
            return self.update_interaction_calls[-1][1]
        return self.reply_interaction_calls[-1][1] if self.reply_interaction_calls else None

    async def reply_text(self, *, external_message_id: str, text: str) -> ChannelDeliveryResult:
        self._raise()
        self.reply_text_calls.append((external_message_id, text))
        return ChannelDeliveryResult(f"reply:{external_message_id}", 0)

    async def reply_interaction(
        self, *, external_message_id: str, interaction: RenderedInteraction
    ) -> ChannelDeliveryResult:
        self._raise()
        self.reply_interaction_calls.append((external_message_id, interaction))
        return ChannelDeliveryResult(f"card:{external_message_id}", 0)

    async def update_interaction(
        self, *, external_interaction_id: str, interaction: RenderedInteraction
    ) -> ChannelDeliveryResult:
        self._raise()
        self.update_interaction_calls.append((external_interaction_id, interaction))
        return ChannelDeliveryResult(external_interaction_id, 0)

    def _raise(self) -> None:
        if self.failure is not None:
            raise self.failure


class _LarkOapiTransport:
    def __init__(self, app_id: str, app_secret: str) -> None:
        try:
            lark = importlib.import_module("lark_oapi")
        except ImportError as exc:
            raise RuntimeError("lark-oapi is required for the production Feishu client") from exc
        self._lark = lark
        self._client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    async def reply(
        self, message_id: str, message_type: str, content: str, timeout: float
    ) -> tuple[str | None, int | None]:
        return await asyncio.to_thread(self._reply_sync, message_id, message_type, content, timeout)

    def _reply_sync(
        self, message_id: str, message_type: str, content: str, timeout: float
    ) -> tuple[str | None, int | None]:
        del timeout
        im = importlib.import_module("lark_oapi.api.im.v1")

        request = (
            im.ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                im.ReplyMessageRequestBody.builder().msg_type(message_type).content(content).build()
            )
            .build()
        )
        response = self._client.im.v1.message.reply(request)
        if not response.success():
            raise ChannelRequestError(f"Feishu reply failed with code {response.code}")
        return getattr(getattr(response, "data", None), "message_id", None), response.code

    async def update_card(
        self, message_id: str, content: str, timeout: float
    ) -> tuple[str | None, int | None]:
        return await asyncio.to_thread(self._update_sync, message_id, content, timeout)

    def _update_sync(
        self, message_id: str, content: str, timeout: float
    ) -> tuple[str | None, int | None]:
        del timeout
        im = importlib.import_module("lark_oapi.api.im.v1")

        request = (
            im.PatchMessageRequest.builder()
            .message_id(message_id)
            .request_body(im.PatchMessageRequestBody.builder().content(content).build())
            .build()
        )
        response = self._client.im.v1.message.patch(request)
        if not response.success():
            raise ChannelRequestError(f"Feishu update failed with code {response.code}")
        return message_id, response.code


def _map_error(exc: Exception) -> ChannelError:
    if isinstance(exc, ChannelError):
        return exc
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return ChannelTimeoutError("Feishu request timed out")
    text = str(exc).lower()
    if "401" in text or "authentication" in text:
        return ChannelAuthenticationError("Feishu authentication failed")
    if "403" in text or "permission" in text:
        return ChannelPermissionError("Feishu permission denied")
    if "429" in text or "rate" in text:
        return ChannelRateLimitError("Feishu rate limit exceeded")
    return ChannelRequestError("Feishu request failed")
