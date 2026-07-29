from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RenderedInteraction:
    payload: dict[str, Any]
    fallback_text: str


@dataclass(frozen=True)
class ChannelDeliveryResult:
    external_interaction_id: str | None = None
    response_code: int | None = None


class ChannelPort(Protocol):
    async def send_text(self, *, conversation_id: str, text: str) -> None: ...


class ChannelClient(Protocol):
    async def reply_text(self, *, external_message_id: str, text: str) -> ChannelDeliveryResult: ...

    async def reply_interaction(
        self, *, external_message_id: str, interaction: RenderedInteraction
    ) -> ChannelDeliveryResult: ...

    async def update_interaction(
        self, *, external_interaction_id: str, interaction: RenderedInteraction
    ) -> ChannelDeliveryResult: ...
