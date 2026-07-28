from dataclasses import dataclass


@dataclass(frozen=True)
class SentMessage:
    conversation_id: str
    text: str


class FakeChannel:
    def __init__(self) -> None:
        self.sent_messages: list[SentMessage] = []

    async def send_text(self, *, conversation_id: str, text: str) -> None:
        self.sent_messages.append(SentMessage(conversation_id, text))
