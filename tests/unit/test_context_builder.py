from buy_agent.adapters.backend.fake_backend_gateway import fake_requirement
from buy_agent.application.context_builder import ContextBuilder
from buy_agent.domain.conversation import SessionState
from buy_agent.domain.identity import CurrentPrincipal


def test_builds_complete_context() -> None:
    principal = CurrentPrincipal(1, "u", frozenset({"REQUESTER"}), (), (), "ACTIVE")
    session = SessionState("key", 1)
    requirement = fake_requirement(101)
    context = ContextBuilder().build(
        principal=principal,
        session=session,
        requirement=requirement,
        available_tool_names={"save_requester_fields"},
    )
    assert context.principal is principal
    assert context.session is session
    assert context.requirement is requirement
    assert context.available_tool_names == frozenset({"save_requester_fields"})


def test_builds_context_without_requirement() -> None:
    principal = CurrentPrincipal(1, "u", frozenset({"REQUESTER"}), (), (), "ACTIVE")
    context = ContextBuilder().build(
        principal=principal,
        session=SessionState("key", 1),
        requirement=None,
        available_tool_names={"create_requirement_draft"},
    )
    assert context.requirement is None
