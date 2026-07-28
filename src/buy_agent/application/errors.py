from typing import ClassVar


class ApplicationError(Exception):
    error_code: ClassVar[str] = "APPLICATION_ERROR"


class IdentityNotFoundError(ApplicationError):
    error_code = "IDENTITY_NOT_FOUND"


class UserDisabledError(ApplicationError):
    error_code = "USER_DISABLED"


class UserRoleMissingError(ApplicationError):
    error_code = "USER_ROLE_MISSING"


class RequirementNotFoundError(ApplicationError):
    error_code = "REQUIREMENT_NOT_FOUND"


class RequirementAccessDeniedError(ApplicationError):
    error_code = "REQUIREMENT_ACCESS_DENIED"


_ERROR_MESSAGES: dict[type[ApplicationError], str] = {
    IdentityNotFoundError: "未找到您的用户身份，请联系管理员。",
    UserDisabledError: "当前用户已被禁用，请联系管理员。",
    UserRoleMissingError: "当前用户未配置采购角色，请联系管理员。",
    RequirementNotFoundError: "未找到指定采购单，请确认编号后重试。",
    RequirementAccessDeniedError: "您无权访问该采购单。",
}


def map_application_error(error: ApplicationError) -> str:
    return _ERROR_MESSAGES[type(error)]
