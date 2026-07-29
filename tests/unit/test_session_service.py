from buy_agent.adapters.persistence.memory_conversation_store import (
    MemoryConversationStore,
)
from buy_agent.adapters.persistence.memory_message_store import MemoryMessageStore
from buy_agent.adapters.persistence.memory_session_store import MemorySessionStateStore
from buy_agent.application.session_service import SessionService, build_session_key
from buy_agent.domain.agent import AgentResponse, AgentRunResult
from buy_agent.domain.enums import ChannelType
from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity
from buy_agent.memory import MemoryPatch


def principal(user_id: int = 1) -> CurrentPrincipal:
    return CurrentPrincipal(user_id, "user", frozenset({"REQUESTER"}), (), (), "ACTIVE")


def service() -> SessionService:
    return SessionService(
        MemoryConversationStore(), MemorySessionStateStore(), MemoryMessageStore()
    )


async def test_get_or_create_restores_conversation_and_initial_memory() -> None:
    subject = service()
    first = await subject.get_or_create(
        session_key="key",
        principal=principal(),
        platform_type="WEB",
        external_conversation_id="chat",
    )
    second = await subject.get_or_create(
        session_key="key",
        principal=principal(),
        platform_type="WEB",
        external_conversation_id="chat",
    )
    assert first.conversation == second.conversation
    assert first.memory.current_action == "CREATE_REQUEST"
    assert first.memory.purchase_request_id is None


async def test_apply_patch_and_empty_patch_version_rules() -> None:
    subject = service()
    bundle = await subject.get_or_create(
        session_key="key",
        principal=principal(),
        platform_type="WEB",
        external_conversation_id=None,
    )
    unchanged = await subject.apply_agent_result(
        conversation=bundle.conversation,
        current_memory=bundle.memory,
        result=AgentRunResult(AgentResponse("ok"), 1, 0),
    )
    assert unchanged.state_version == 0
    changed = await subject.apply_agent_result(
        conversation=bundle.conversation,
        current_memory=bundle.memory,
        result=AgentRunResult(
            AgentResponse("ok"),
            1,
            1,
            memory_patch=MemoryPatch(collected_data_patch={"quantity": 2}),
        ),
    )
    assert changed.state_version == 1
    assert changed.collected_data["quantity"] == 2


def test_session_key_is_stable() -> None:
    identity = ExternalIdentity(ChannelType.FEISHU, "tenant", "user")
    assert build_session_key(identity) == "procurement:FEISHU:tenant:user"
