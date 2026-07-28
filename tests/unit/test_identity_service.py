import pytest

from buy_agent.adapters.backend.fake_backend_gateway import FakeBackendGateway
from buy_agent.application.errors import (
    IdentityNotFoundError,
    UserDisabledError,
    UserRoleMissingError,
)
from buy_agent.application.identity_service import IdentityService
from buy_agent.domain.enums import ChannelType
from buy_agent.domain.identity import ExternalIdentity


def identity(user: str) -> ExternalIdentity:
    return ExternalIdentity(ChannelType.FEISHU, "tenant", user)


async def test_identity_not_found_is_application_error() -> None:
    with pytest.raises(IdentityNotFoundError):
        await IdentityService(FakeBackendGateway()).resolve(identity("missing"))


async def test_disabled_user_is_application_error() -> None:
    with pytest.raises(UserDisabledError):
        await IdentityService(FakeBackendGateway()).resolve(identity("disabled"))


async def test_user_without_roles_is_application_error() -> None:
    with pytest.raises(UserRoleMissingError):
        await IdentityService(FakeBackendGateway()).resolve(identity("no_role"))
