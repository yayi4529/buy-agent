import asyncio

from buy_agent.bootstrap.fake_application import build_fake_application
from buy_agent.domain.enums import ChannelType, InboundEventType
from buy_agent.domain.events import InboundEvent
from buy_agent.domain.identity import ExternalIdentity


async def main() -> None:
    application = build_fake_application()
    event = InboundEvent(
        event_id="demo-event-1",
        message_id="demo-message-1",
        event_type=InboundEventType.TEXT_MESSAGE,
        identity=ExternalIdentity(
            channel=ChannelType.FEISHU,
            external_tenant_id="demo-tenant",
            external_user_id="requester",
        ),
        conversation_id="demo-conversation",
        text="查看我的采购单",
        action=None,
        raw_payload={},
    )
    await application.orchestrator.handle(event)
    for message in application.channel.sent_messages:
        print(message.text)


if __name__ == "__main__":
    asyncio.run(main())
