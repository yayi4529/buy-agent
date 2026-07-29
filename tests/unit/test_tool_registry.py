import pytest

from buy_agent.adapters.agent.fake_tool import FakeTool
from buy_agent.tools.registry import ToolRegistry


def test_registry_registers_and_resolves_explicit_tools() -> None:
    tool = FakeTool()
    registry = ToolRegistry([tool])
    assert registry.get("fake_tool") is tool
    assert registry.get("missing") is None


def test_registry_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match="already registered"):
        ToolRegistry([FakeTool(), FakeTool()])


def test_registry_only_exposes_registered_authorized_definitions() -> None:
    definitions = ToolRegistry([FakeTool()]).definitions_for(
        frozenset({"fake_tool", "not_registered"})
    )
    assert [definition["name"] for definition in definitions] == ["fake_tool"]
