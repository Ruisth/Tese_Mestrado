"""Entry point: ``python -m egw_controller`` runs the API on ``EGW_HTTP_PORT``."""

from __future__ import annotations

import uvicorn

from .config import Settings
from .logging_config import configure_logging


def main() -> None:
    configure_logging()
    settings = Settings.from_env()
    # log_config=None makes uvicorn inherit the root JSON handler on stderr.
    uvicorn.run(
        "egw_controller.app:create_app_from_env",
        factory=True,
        host="0.0.0.0",
        port=settings.http_port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
