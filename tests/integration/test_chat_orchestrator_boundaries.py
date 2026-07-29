from buy_agent.bootstrap.fake_application import build_fake_application
from buy_agent.domain.enums import ChannelType, InboundEventType
from buy_agent.domain.events import InboundEvent
from buy_agent.domain.identity import ExternalIdentity


def event(event_id: str, user: str = "requester") -> InboundEvent:
    return InboundEvent(
        event_id,
        f"m-{event_id}",
        InboundEventType.TEXT_MESSAGE,
        ExternalIdentity(ChannelType.FEISHU, "tenant", user),
        f"chat-{user}",
        "采购服务器",
        None,
        {},
    )


async def test_identity_error_is_controlled_and_marks_no_agent_call() -> None:
    app = build_fake_application()
    await app.orchestrator.handle(event("missing", "missing"))
    assert app.agent.calls == []
    assert "未找到您的用户身份" in app.channel.sent_messages[0].text


async def test_unexpected_error_is_controlled() -> None:
    app = build_fake_application()

    async def fail(identity: ExternalIdentity) -> None:
        raise RuntimeError("secret failure")

    app.identity_service.resolve = fail  # type: ignore[method-assign]
    response = await app.orchestrator.handle(event("failure"))
    assert response is not None
    assert response.text == "处理采购消息时出现问题，请稍后重试。"
    assert "secret failure" not in app.channel.sent_messages[0].text
