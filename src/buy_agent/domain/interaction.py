from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InteractionField:
    label: str
    value: str


@dataclass(frozen=True)
class SelectionOption:
    value: str
    label: str


@dataclass(frozen=True)
class SelectionGroup:
    name: str
    label: str
    options: tuple[SelectionOption, ...]


@dataclass(frozen=True)
class InteractionAction:
    action: str
    label: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InteractionView:
    view_type: str
    title: str
    fields: tuple[InteractionField, ...]
    selection_groups: tuple[SelectionGroup, ...] = ()
    actions: tuple[InteractionAction, ...] = ()
