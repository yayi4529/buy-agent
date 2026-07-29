import importlib

from buy_agent.bootstrap.settings import Settings
from buy_agent.interfaces.http.app import create_app


def main() -> None:
    settings = Settings.from_env()
    uvicorn = importlib.import_module("uvicorn")
    uvicorn.run(
        create_app(settings),
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.http_log_level,
    )


if __name__ == "__main__":
    main()
