from enum import StrEnum


class ChannelType(StrEnum):
    FEISHU = "FEISHU"
    WEB = "WEB"
    DINGTALK = "DINGTALK"
    WECHAT = "WECHAT"


class InboundEventType(StrEnum):
    TEXT_MESSAGE = "TEXT_MESSAGE"
    ACTION = "ACTION"
    UNSUPPORTED_MESSAGE = "UNSUPPORTED_MESSAGE"
