"""OpenTelemetry / Application Insights setup. Implemented in the observability step."""
from __future__ import annotations

import logging

logger = logging.getLogger("app.telemetry")


def init_telemetry(connection_string: str | None) -> None:
    """No-op placeholder; wired up in `observability` todo."""
    if not connection_string:
        logger.info("Telemetry disabled (no APPLICATIONINSIGHTS_CONNECTION_STRING).")
        return
    logger.info("Telemetry init deferred to observability step.")
