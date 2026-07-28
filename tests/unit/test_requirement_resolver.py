import pytest

from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway, fake_requirement
from buy_agent.application.requirement_resolver import RequirementResolver
from buy_agent.domain.conversation import SessionState
from buy_agent.domain.identity import CurrentPrincipal

PRINCIPAL = CurrentPrincipal(1, "user", frozenset({"REQUESTER"}), (), (), "ACTIVE")


async def resolve(requirements: list, text: str = "", active_id: int | None = None):
    backend = FakeBackendGateway(requirements={1: requirements})
    return await RequirementResolver(backend).resolve(
        user_message=text,
        principal=PRINCIPAL,
        session=SessionState("key", 1, active_requirement_id=active_id),
    )


@pytest.mark.asyncio
async def test_explicit_number_has_priority() -> None:
    result = await resolve(
        [fake_requirement(101), fake_requirement(102)], "查看 PR-2026-102", active_id=101
    )
    assert result.requirement and result.requirement.requirement_id == 102


@pytest.mark.asyncio
async def test_explicit_id_formats() -> None:
    result = await resolve([fake_requirement(101), fake_requirement(102)], "采购单101")
    assert result.requirement and result.requirement.requirement_id == 101


@pytest.mark.asyncio
async def test_active_requirement_is_second_priority() -> None:
    result = await resolve([fake_requirement(101), fake_requirement(102)], active_id=102)
    assert result.requirement and result.requirement.requirement_id == 102


@pytest.mark.asyncio
async def test_unique_active_requirement_is_selected() -> None:
    result = await resolve([fake_requirement(101)])
    assert result.requirement and result.requirement.requirement_id == 101


@pytest.mark.asyncio
async def test_multiple_requirements_need_selection_without_guessing() -> None:
    requirements = [fake_requirement(101), fake_requirement(102)]
    result = await resolve(requirements)
    assert result.requirement is None
    assert result.needs_selection is True
    assert result.candidates == tuple(requirements)


@pytest.mark.asyncio
async def test_no_active_requirement_returns_none() -> None:
    result = await resolve([])
    assert result.requirement is None
    assert result.needs_selection is False
