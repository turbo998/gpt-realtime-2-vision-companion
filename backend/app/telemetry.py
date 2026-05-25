"""Lightweight telemetry helpers.

Captures per-turn latency metrics in memory (and emits to App Insights /
OpenTelemetry when configured). Never logs raw audio or image bytes.
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("app.telemetry")

_initialized = False


def init_telemetry(connection_string: str | None) -> None:
    """Initialise Azure Monitor OpenTelemetry if connection string present."""
    global _initialized
    if _initialized:
        return
    if not connection_string:
        logger.info("Telemetry disabled (no APPLICATIONINSIGHTS_CONNECTION_STRING).")
        _initialized = True
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=connection_string)
        logger.info("Azure Monitor OpenTelemetry configured.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to configure Azure Monitor: %s", exc)
    _initialized = True


@dataclass
class TurnMetrics:
    """Per-turn latency snapshot. All times in milliseconds."""

    turn_id: str
    started_at: float = field(default_factory=time.monotonic)
    user_speech_ended_at: float | None = None
    frame_uploaded_at: float | None = None
    first_audio_at: float | None = None
    response_done_at: float | None = None
    interrupted: bool = False
    tool_calls: list[str] = field(default_factory=list)
    mode: str | None = None

    def _delta_ms(self, end: float | None, start: float | None) -> int | None:
        if end is None or start is None:
            return None
        return int(round((end - start) * 1000))

    def summary(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "first_audio_latency_ms": self._delta_ms(
                self.first_audio_at, self.user_speech_ended_at
            ),
            "response_total_ms": self._delta_ms(
                self.response_done_at, self.user_speech_ended_at
            ),
            "frame_upload_ms": self._delta_ms(
                self.frame_uploaded_at, self.started_at
            ),
            "interrupted": self.interrupted,
            "tool_calls": self.tool_calls,
            "mode": self.mode,
        }

    def emit(self) -> None:
        # Structured log (will be picked up by App Insights if configured).
        logger.info("turn_metrics %s", json.dumps(self.summary(), ensure_ascii=False))


@contextmanager
def span(name: str):  # tiny placeholder for future OTEL spans
    start = time.monotonic()
    try:
        yield
    finally:
        ms = int((time.monotonic() - start) * 1000)
        logger.debug("span %s elapsed=%dms", name, ms)
