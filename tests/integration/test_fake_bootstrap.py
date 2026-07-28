from buy_agent.bootstrap.fake_application import build_fake_application
from buy_agent.domain.enums import ChannelType, InboundEventType
from buy_agent.domain.events import InboundEvent
from buy_agent.domain.identity import ExternalIdentity


async def test_fake_application_assembles_and_runs_pipeline() -> None:
    application = build_fake_application()
    event = InboundEvent(
        event_id="bootstrap-event",
        message_id="bootstrap-message",
        event_type=InboundEventType.TEXT_MESSAGE,
        identity=ExternalIdentity(ChannelType.FEISHU, "tenant", "requester"),
        conversation_id="bootstrap-conversation",
        text="查看我的采购单",
        action=None,
        raw_payload={},
    )

    await application.orchestrator.handle(event)

    assert len(application.agent.calls) == 1
    assert len(application.channel.sent_messages) == 1
    assert application.agent.calls[0][1].principal.user_id == 1
    assert "requirement_id=101" in application.channel.sent_messages[0].text
