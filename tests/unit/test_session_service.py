import pytest

from buy_agent.adapters.persistence.memory_session_store import MemorySessionStore
from buy_agent.application.session_service import SessionService, build_session_key
from buy_agent.domain.enums import ChannelType
from buy_agent.domain.identity import CurrentPrincipal, ExternalIdentity


def identity(user: str) -> ExternalIdentity:
    return ExternalIdentity(ChannelType.FEISHU, "tenant", user)


def principal(user_id: int) -> CurrentPrincipal:
    return CurrentPrincipal(user_id, "user", frozenset({"REQUESTER"}), (), (), "ACTIVE")


@pytest.mark.asyncio
async def test_first_load_creates_default_session() -> None:
    store = MemorySessionStore()
    service = SessionService(store)
    session = await service.load_or_create(identity("u1"), principal(1))
    assert session.session_key == "procurement:FEISHU:tenant:u1"
    assert session.user_id == 1
    assert await store.get(session.session_key) is not None


@pytest.mark.asyncio
async def test_existing_session_is_loaded() -> None:
    service = SessionService(MemorySessionStore())
    first = await service.load_or_create(identity("u1"), principal(1))
    first.summary = "remember me"
    await service.save(first)
    loaded = await service.load_or_create(identity("u1"), principal(1))
    assert loaded.summary == "remember me"


def test_different_users_have_different_keys() -> None:
    assert build_session_key(identity("u1")) != build_session_key(identity("u2"))
