from typing import Protocol


class ChannelPort(Protocol):
    async def send_text(self, *, conversation_id: str, text: str) -> None: ...
