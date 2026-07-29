from dataclasses import dataclass, field


@dataclass(frozen=True)
class FeishuWebhookResponse:
    status_code: int = 200
    body: dict[str, object] = field(default_factory=lambda: {"msg": "success"})


class WebhookRequestError(Exception):
    status_code = 400
    code = "INVALID_REQUEST"


class RequestBodyTooLarge(WebhookRequestError):
    status_code = 413
    code = "REQUEST_BODY_TOO_LARGE"


class UnsupportedContentType(WebhookRequestError):
    status_code = 415
    code = "UNSUPPORTED_CONTENT_TYPE"


class FeishuSignatureError(WebhookRequestError):
    status_code = 401
    code = "SIGNATURE_INVALID"


class FeishuDecryptionError(WebhookRequestError):
    code = "DECRYPTION_FAILED"


class FeishuEventFormatError(WebhookRequestError):
    code = "EVENT_FORMAT_INVALID"
