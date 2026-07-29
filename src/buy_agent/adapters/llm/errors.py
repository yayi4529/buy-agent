class LLMError(RuntimeError):
    """Base class for provider-neutral model failures."""


class LLMAuthenticationError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMConnectionError(LLMError):
    pass


class LLMServiceUnavailableError(LLMError):
    pass


class LLMResponseFormatError(LLMError):
    pass


class LLMToolArgumentsError(LLMResponseFormatError):
    pass


class LLMUnexpectedError(LLMError):
    pass
