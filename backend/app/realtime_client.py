"""Azure OpenAI Realtime WebSocket client.

Thin async wrapper around the AOAI realtime endpoint. Handles:
  - URL build + auth header (DefaultAzureCredential -> Bearer, or api-key)
  - send: session.update / input_audio_buffer.append+commit /
          conversation.item.create / response.create / response.cancel /
          response.function_call_output
  - receive: yields parsed server events to the ws_session orchestrator
  - automatic fallback to a secondary deployment on initial 4xx/connect errors
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlencode, urlparse

import websockets
from websockets.client import WebSocketClientProtocol

from app.config import Settings

logger = logging.getLogger("app.realtime")

AOAI_AUDIENCE = "https://cognitiveservices.azure.com/.default"


class RealtimeClient:
    """Manages a single AOAI realtime websocket session."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ws: WebSocketClientProtocol | None = None
        self.deployment_used: str | None = None
        self._send_lock = asyncio.Lock()
        self._token_cache: tuple[str, float] | None = None  # (token, exp_epoch)

    # --------- auth ---------
    async def _bearer_token(self) -> str | None:
        """Acquire AAD bearer token for Cognitive Services scope."""
        try:
            from azure.identity.aio import DefaultAzureCredential
        except Exception as exc:  # pragma: no cover
            logger.warning("azure-identity not available: %s", exc)
            return None
        now = time.time()
        if self._token_cache and self._token_cache[1] - 60 > now:
            return self._token_cache[0]
        cred = DefaultAzureCredential()
        try:
            tok = await cred.get_token(AOAI_AUDIENCE)
            self._token_cache = (tok.token, float(tok.expires_on))
            return tok.token
        finally:
            try:
                await cred.close()
            except Exception:
                pass

    async def _build_headers(self) -> dict[str, str]:
        s = self.settings
        if s.azure_openai_api_key:
            return {"api-key": s.azure_openai_api_key}
        tok = await self._bearer_token()
        if tok:
            return {"Authorization": f"Bearer {tok}"}
        return {}

    # --------- connect ---------
    def _build_url(self, deployment: str) -> str:
        ep = self.settings.azure_openai_endpoint.rstrip("/")
        host = urlparse(ep).netloc or ep
        scheme = "wss"
        qs = urlencode(
            {
                "api-version": self.settings.azure_openai_realtime_api_version,
                "deployment": deployment,
            }
        )
        return f"{scheme}://{host}/openai/realtime?{qs}"

    async def connect(self) -> None:
        """Open WS with primary deployment, fall back to secondary on failure."""
        s = self.settings
        candidates = [s.azure_openai_realtime_deployment]
        if s.azure_openai_realtime_fallback_deployment and (
            s.azure_openai_realtime_fallback_deployment
            != s.azure_openai_realtime_deployment
        ):
            candidates.append(s.azure_openai_realtime_fallback_deployment)

        last_err: Exception | None = None
        for dep in candidates:
            url = self._build_url(dep)
            try:
                headers = await self._build_headers()
                logger.info(
                    "Connecting AOAI realtime deployment=%s endpoint=%s", dep, url
                )
                self.ws = await websockets.connect(
                    url,
                    additional_headers=headers,
                    max_size=16 * 1024 * 1024,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                )
                self.deployment_used = dep
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("AOAI connect failed (deployment=%s): %s", dep, exc)
                last_err = exc
        raise RuntimeError(f"All AOAI realtime deployments failed: {last_err}")

    @property
    def connected(self) -> bool:
        return self.ws is not None and not self.ws.closed

    # --------- send helpers ---------
    async def send_event(self, event: dict[str, Any]) -> None:
        if not self.ws:
            raise RuntimeError("RealtimeClient not connected")
        data = json.dumps(event, ensure_ascii=False)
        async with self._send_lock:
            await self.ws.send(data)

    async def session_update(
        self,
        *,
        instructions: str,
        voice: str = "alloy",
        tools: list[dict] | None = None,
        language: str = "zh",
    ) -> None:
        event = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": instructions,
                "voice": voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.55,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                    "create_response": True,
                },
                "tools": tools or [],
                "tool_choice": "auto",
                "temperature": 0.7,
            },
        }
        # language hint via metadata key (model already follows instructions)
        if language:
            event["session"]["metadata"] = {"lang": language}
        await self.send_event(event)

    async def append_audio(self, pcm16: bytes) -> None:
        if not pcm16:
            return
        b64 = base64.b64encode(pcm16).decode("ascii")
        await self.send_event({"type": "input_audio_buffer.append", "audio": b64})

    async def commit_audio(self) -> None:
        await self.send_event({"type": "input_audio_buffer.commit"})

    async def cancel_response(self) -> None:
        await self.send_event({"type": "response.cancel"})

    async def inject_image(
        self, jpeg_bytes: bytes, *, hint: str | None = None, detail: str = "low"
    ) -> None:
        """Inject a camera frame as a user message into the conversation."""
        b64 = base64.b64encode(jpeg_bytes).decode("ascii")
        content: list[dict[str, Any]] = [
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{b64}",
                "detail": detail,
            }
        ]
        if hint:
            content.append({"type": "input_text", "text": hint})
        await self.send_event(
            {
                "type": "conversation.item.create",
                "item": {"type": "message", "role": "user", "content": content},
            }
        )

    async def inject_user_text(self, text: str) -> None:
        await self.send_event(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )

    async def trigger_response(self) -> None:
        await self.send_event({"type": "response.create"})

    async def send_tool_result(self, call_id: str, output: dict[str, Any]) -> None:
        await self.send_event(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(output, ensure_ascii=False),
                },
            }
        )

    # --------- receive ---------
    async def events(self) -> AsyncIterator[dict[str, Any]]:
        if not self.ws:
            raise RuntimeError("RealtimeClient not connected")
        async for raw in self.ws:
            if isinstance(raw, bytes):
                # AOAI realtime is JSON-text only; ignore stray binary.
                continue
            try:
                yield json.loads(raw)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Bad event from AOAI: %s", exc)

    async def close(self) -> None:
        if self.ws and not self.ws.closed:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.ws = None
