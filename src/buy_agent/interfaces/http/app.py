import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from buy_agent.bootstrap.settings import Settings
from buy_agent.interfaces.http.application_container import (
    ApplicationContainer,
    build_application,
)
from buy_agent.interfaces.http.models import WebhookRequestError

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    container: ApplicationContainer | None = None,
) -> FastAPI:
    configured = settings or (container.settings if container is not None else Settings.from_env())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        active = container or build_application(configured)
        app.state.container = active
        try:
            yield
        finally:
            await active.aclose()

    app = FastAPI(title="buy-agent", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(WebhookRequestError)
    async def webhook_error_handler(request: Request, error: WebhookRequestError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": "webhook request rejected"},
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
        reference = request.headers.get("x-request-id", "unavailable")[:64]
        logger.exception("unexpected HTTP error reference=%s", reference, exc_info=error)
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "reference": reference},
        )

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    async def ready(request: Request) -> JSONResponse:
        current: ApplicationContainer = request.app.state.container
        missing = _missing_feishu_settings(current.settings)
        ready_state = not current.settings.feishu_enabled or not missing
        return JSONResponse(
            status_code=200 if ready_state else 503,
            content={
                "status": "ready" if ready_state else "not_ready",
                "feishu": (
                    "disabled"
                    if not current.settings.feishu_enabled
                    else ("configured" if not missing else "configuration_missing")
                ),
            },
        )

    async def feishu_webhook(request: Request) -> JSONResponse:
        current: ApplicationContainer = request.app.state.container
        if not current.settings.feishu_enabled:
            return JSONResponse({"code": "FEISHU_DISABLED"}, status_code=503)
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            from buy_agent.interfaces.http.models import UnsupportedContentType

            raise UnsupportedContentType()
        content_length = request.headers.get("content-length")
        if (
            content_length
            and content_length.isdigit()
            and int(content_length) > current.settings.feishu_webhook_max_body_bytes
        ):
            from buy_agent.interfaces.http.models import RequestBodyTooLarge

            raise RequestBodyTooLarge()
        body = await request.body()
        if len(body) > current.settings.feishu_webhook_max_body_bytes:
            from buy_agent.interfaces.http.models import RequestBodyTooLarge

            raise RequestBodyTooLarge()
        if not body:
            from buy_agent.interfaces.http.models import FeishuEventFormatError

            raise FeishuEventFormatError("empty body")
        result = await current.webhook_processor.handle(headers=request.headers, body=body)
        return JSONResponse(result.body, status_code=result.status_code)

    app.add_api_route(
        configured.feishu_webhook_path,
        feishu_webhook,
        methods=["POST"],
        name="feishu-webhook",
    )
    return app


def _missing_feishu_settings(settings: Settings) -> tuple[str, ...]:
    required = {
        "app_id": settings.feishu_app_id,
        "app_secret": settings.feishu_app_secret,
        "verification_token": settings.feishu_verification_token,
        "encrypt_key": settings.feishu_encrypt_key,
    }
    return tuple(name for name, value in required.items() if not value)
