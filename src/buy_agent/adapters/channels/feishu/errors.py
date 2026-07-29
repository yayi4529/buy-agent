class ChannelError(Exception):
    """Safe base error for channel operations."""


class ChannelEventFormatError(ChannelError):
    pass


class ChannelAuthenticationError(ChannelError):
    pass


class ChannelPermissionError(ChannelError):
    pass


class ChannelRateLimitError(ChannelError):
    pass


class ChannelTimeoutError(ChannelError):
    pass


class ChannelRequestError(ChannelError):
    pass


class ChannelResponseFormatError(ChannelError):
    pass
