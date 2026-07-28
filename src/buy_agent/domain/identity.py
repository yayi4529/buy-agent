from dataclasses import dataclass
from typing import Any

from buy_agent.domain.enums import ChannelType


@dataclass(frozen=True)
class ExternalIdentity:
    channel: ChannelType
    external_tenant_id: str
    external_user_id: str


@dataclass(frozen=True)
class CurrentPrincipal:
    user_id: int
    name: str
    roles: frozenset[str]
    department_ids: tuple[str, ...]
    data_scopes: tuple[dict[str, Any], ...]
    system_status: str
