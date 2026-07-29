import logging
from typing import Protocol

from buy_agent.adapters.channels.feishu.action_adapter import FeishuActionAdapter
from buy_agent.adapters.channels.feishu.action_result_renderer import (
    FeishuActionResultRenderer,
)
from buy_agent.adapters.channels.feishu.client import FeishuChannelClient
from buy_agent.adapters.channels.feishu.errors import ChannelError, ChannelEventFormatError
from buy_agent.adapters.channels.feishu.event_adapter import FeishuEventAdapter
from buy_agent.adapters.channels.feishu.models import (
    FeishuHandlerResult,
    FeishuMessageKind,
)
from buy_agent.adapters.channels.feishu.response_renderer import FeishuResponseRenderer
from buy_agent.application.action_orchestrator import ActionOrchestrator
from buy_agent.application.chat_orchestrator import ChatOrchestrator
from buy_agent.application.identity_service import IdentityService
from buy_agent.domain.enums import ChannelType
from buy_agent.domain.identity import ExternalIdentity

logger = logging.getLogger(__name__)
IMAGE_MESSAGE = "当前暂不支持图片识别，请直接发送采购信息文字。"
UNSUPPORTED_MESSAGE = "当前暂不支持该消息类型，请直接发送采购信息文字。"
GROUP_MESSAGE = "当前仅支持机器人私聊采购业务。"
SAFE_ERROR = "处理采购消息时出现问题，请稍后重试。"


class FeishuClientPort(Protocol):
    async def reply_text(self, *, external_message_id: str, text: str) -> object: ...

    async def reply_interaction(
        self, *, external_message_id: str, interaction: object
    ) -> object: ...

    async def update_interaction(
        self, *, external_interaction_id: str, interaction: object
    ) -> object: ...


class FeishuMessageHandler:
    def __init__(
        self,
        *,
        event_adapter: FeishuEventAdapter,
        orchestrator: ChatOrchestrator,
        renderer: FeishuResponseRenderer,
        client: FeishuChannelClient,
    ) -> None:
        self._adapter = event_adapter
        self._orchestrator = orchestrator
        self._renderer = renderer
        self._client = client

    async def handle(self, raw_event: object) -> FeishuHandlerResult:
        try:
            parsed = self._adapter.parse(raw_event)
            if parsed.chat_type != "p2p":
                return FeishuHandlerResult(False, "GROUP_CHAT_UNSUPPORTED", GROUP_MESSAGE)
            if parsed.message_kind is FeishuMessageKind.IMAGE:
                await self._client.reply_text(
                    external_message_id=parsed.message_id, text=IMAGE_MESSAGE
                )
                return FeishuHandlerResult(True, "IMAGE_UNSUPPORTED", IMAGE_MESSAGE)
            if parsed.message_kind is not FeishuMessageKind.TEXT:
                await self._client.reply_text(
                    external_message_id=parsed.message_id, text=UNSUPPORTED_MESSAGE
                )
                return FeishuHandlerResult(True, "MESSAGE_TYPE_UNSUPPORTED", UNSUPPORTED_MESSAGE)
            if parsed.inbound_event is None:
                raise ChannelEventFormatError("inbound event is unavailable")
            response = await self._orchestrator.handle(parsed.inbound_event)
            if response is None:
                return FeishuHandlerResult(True, "DUPLICATE_EVENT")
            if response.interaction is not None:
                rendered = self._renderer.render_interaction(response.interaction)
                await self._client.reply_interaction(
                    external_message_id=parsed.message_id, interaction=rendered
                )
            else:
                await self._client.reply_text(
                    external_message_id=parsed.message_id,
                    text=self._renderer.render_text(response),
                )
            return FeishuHandlerResult(True, "OK")
        except ChannelError:
            raise
        except Exception:
            logger.exception("feishu message handler failed")
            return FeishuHandlerResult(False, "HANDLER_ERROR", SAFE_ERROR)


class FeishuActionHandler:
    def __init__(
        self,
        *,
        action_adapter: FeishuActionAdapter,
        identity_service: IdentityService,
        orchestrator: ActionOrchestrator,
        renderer: FeishuActionResultRenderer,
        client: FeishuChannelClient,
    ) -> None:
        self._adapter = action_adapter
        self._identities = identity_service
        self._orchestrator = orchestrator
        self._renderer = renderer
        self._client = client

    async def handle(self, raw_callback: object) -> FeishuHandlerResult:
        try:
            parsed = self._adapter.parse(raw_callback)
        except ChannelEventFormatError:
            return FeishuHandlerResult(False, "INVALID_CALLBACK", "回调格式无效。")
        principal = await self._identities.resolve(
            ExternalIdentity(ChannelType.FEISHU, parsed.tenant_key, parsed.operator_open_id)
        )
        command = self._adapter.to_command(parsed, principal)
        result = await self._orchestrator.handle(command)
        rendered = self._renderer.render(result)
        try:
            await self._client.update_interaction(
                external_interaction_id=parsed.external_interaction_id,
                interaction=rendered,
            )
        except ChannelError:
            logger.warning(
                "feishu card update failed callback_event_id=%s status=%s",
                parsed.callback_event_id,
                result.status,
            )
            return FeishuHandlerResult(True, "ACTION_COMPLETED_UPDATE_FAILED", result.message)
        return FeishuHandlerResult(True, result.code, result.message, True)
