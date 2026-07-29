"""Manual Feishu smoke-test entry point; never collected by pytest.

Mount FeishuMessageHandler and FeishuActionHandler in an HTTP server that passes
SDK-verified/decrypted callback dictionaries to ``handle``. This repository does
not choose a web framework. MockBackendGateway remains the business backend.
"""

from buy_agent.bootstrap.settings import Settings


def main() -> None:
    settings = Settings.from_env()
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        print("Skipped: BUY_AGENT_FEISHU_APP_ID/APP_SECRET are not configured.")
        return
    print("Feishu configuration is present. Mount the handlers in the deployment HTTP entry.")


if __name__ == "__main__":
    main()
