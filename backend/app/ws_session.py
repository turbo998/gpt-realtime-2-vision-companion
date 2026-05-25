"""WebSocket session orchestration.

Frontend <-> FastAPI WebSocket protocol (JSON text frames + binary frames):

  Client -> Server text:
    {"type":"hello","lang":"zh"}
    {"type":"audio_end"}                 # mark end of user speech (optional)
    {"type":"interrupt"}                 # user manually cuts the assistant off
    {"type":"text","text":"..."}         # text-only injection (debug / chips)
    {"type":"frame_meta","quality":"low|high","ts":<ms>}

  Client -> Server binary:
    audio chunk  -> raw PCM16 mono 24kHz (sent right after every ~20-40ms)
    image chunk  -> JPEG bytes; preceded by a "frame_meta" text frame

  Server -> Client text:
    {"type":"ready","model":"gpt-realtime-2"}
    {"type":"state","state":"listening|thinking|speaking|idle"}
    {"type":"transcript","role":"user|assistant","text":"...","final":bool}
    {"type":"tool","name":"...","args":{...}}                 # tool call begin
    {"type":"mode","mode":"read_text",...}
    {"type":"safety","category":"vehicle","message":"..."}
    {"type":"request_frame","quality":"high","purpose":"..."}
    {"type":"latency","first_audio_ms":420,"total_ms":1800,...}
    {"type":"error","message":"..."}

  Server -> Client binary:
    PCM16 mono 24kHz audio chunks for playback
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app import __version__
from app.config import get_settings
from app.prompts import default_system_prompt
from app.realtime_client import RealtimeClient
from app.telemetry import TurnMetrics
from app.tools import TOOLS, dispatch

logger = logging.getLogger("app.ws_session")
router = APIRouter()


class Session:
    """One client websocket <-> one AOAI realtime websocket."""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.client = RealtimeClient(get_settings())
        self.lang = "zh"
        self.pending_frame_meta: dict[str, Any] | None = None
        self.last_frame_jpeg: bytes | None = None
        self.last_frame_meta: dict[str, Any] | None = None
        self.frame_injected_for_response = False
        self.current_turn: TurnMetrics | None = None
        self.assistant_speaking = False

    # ---------- frontend send helpers ----------
    async def send_json(self, payload: dict[str, Any]) -> None:
        if self.ws.application_state == WebSocketState.CONNECTED:
            await self.ws.send_text(json.dumps(payload, ensure_ascii=False))

    async def send_audio(self, pcm16: bytes) -> None:
        if self.ws.application_state == WebSocketState.CONNECTED:
            await self.ws.send_bytes(pcm16)

    # ---------- lifecycle ----------
    async def run(self) -> None:
        await self.ws.accept()
        await self.send_json(
            {"type": "ready", "backend_version": __version__, "ts": int(time.time() * 1000)}
        )

        # Try to connect to AOAI. If config is missing or connect fails,
        # downgrade to stub mode so the UI still works for a screenshot demo.
        stub_mode = False
        try:
            if not self.client.settings.azure_openai_endpoint:
                raise RuntimeError("AZURE_OPENAI_ENDPOINT not configured")
            await self.client.connect()
            await self.client.session_update(
                instructions=default_system_prompt(self.lang),
                voice="alloy",
                tools=TOOLS,
                language=self.lang,
            )
            await self.send_json(
                {
                    "type": "ready",
                    "model": self.client.deployment_used,
                    "stub": False,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falling back to stub mode: %s", exc)
            stub_mode = True
            await self.send_json(
                {
                    "type": "ready",
                    "model": "stub",
                    "stub": True,
                    "reason": str(exc)[:200],
                }
            )

        try:
            if stub_mode:
                await self._run_stub()
            else:
                await asyncio.gather(
                    self._pump_client_to_aoai(),
                    self._pump_aoai_to_client(),
                )
        except WebSocketDisconnect:
            logger.info("client disconnected")
        except Exception as exc:  # noqa: BLE001
            logger.exception("session crashed: %s", exc)
            with suppress():
                await self.send_json({"type": "error", "message": str(exc)[:300]})
        finally:
            await self.client.close()

    # ---------- stub mode (no AOAI) ----------
    async def _run_stub(self) -> None:
        """Echo-style demo so the frontend can be tested without AOAI."""
        while True:
            msg = await self.ws.receive()
            if msg.get("type") == "websocket.disconnect":
                return
            if "text" in msg and msg["text"] is not None:
                data = self._safe_json(msg["text"])
                if data.get("type") == "text":
                    text = data.get("text", "")
                    await self.send_json(
                        {
                            "type": "transcript",
                            "role": "user",
                            "text": text,
                            "final": True,
                        }
                    )
                    await asyncio.sleep(0.4)
                    reply = (
                        f"(stub) 我收到了:「{text}」。真实 Azure OpenAI Realtime "
                        "未配置或连接失败,请在后端 .env 设 AZURE_OPENAI_ENDPOINT。"
                    )
                    await self.send_json(
                        {
                            "type": "transcript",
                            "role": "assistant",
                            "text": reply,
                            "final": True,
                        }
                    )
                    await self.send_json(
                        {"type": "latency", "first_audio_ms": 400, "total_ms": 800}
                    )

    # ---------- pumps ----------
    async def _pump_client_to_aoai(self) -> None:
        while True:
            msg = await self.ws.receive()
            if msg.get("type") == "websocket.disconnect":
                return
            text = msg.get("text")
            data: bytes | None = msg.get("bytes")
            if text is not None:
                await self._handle_client_text(self._safe_json(text))
            elif data is not None:
                await self._handle_client_binary(data)

    async def _handle_client_text(self, data: dict[str, Any]) -> None:
        mtype = data.get("type")
        if mtype == "hello":
            self.lang = data.get("lang", self.lang)
            await self.client.session_update(
                instructions=default_system_prompt(self.lang),
                tools=TOOLS,
                language=self.lang,
            )
        elif mtype == "frame_meta":
            self.pending_frame_meta = data
        elif mtype == "audio_end":
            try:
                await self.client.commit_audio()
            except Exception as exc:  # noqa: BLE001
                logger.warning("commit_audio failed: %s", exc)
        elif mtype == "interrupt":
            if self.assistant_speaking:
                try:
                    await self.client.cancel_response()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("cancel failed: %s", exc)
                if self.current_turn:
                    self.current_turn.interrupted = True
        elif mtype == "text":
            await self.client.inject_user_text(data.get("text", ""))
            await self.client.trigger_response()
        else:
            logger.debug("unknown client text: %s", mtype)

    async def _handle_client_binary(self, data: bytes) -> None:
        meta = self.pending_frame_meta
        # JPEG frame upload: client sends frame_meta then binary
        if meta is not None:
            self.pending_frame_meta = None
            self.last_frame_jpeg = data
            self.last_frame_meta = meta
            # Inject immediately so the model has it for the next response.
            quality = meta.get("quality", "low")
            try:
                await self.client.inject_image(
                    data,
                    detail="high" if quality == "high" else "low",
                )
                if self.current_turn and self.current_turn.frame_uploaded_at is None:
                    self.current_turn.frame_uploaded_at = time.monotonic()
            except Exception as exc:  # noqa: BLE001
                logger.warning("inject_image failed: %s", exc)
            return
        # Otherwise treat as raw PCM16 audio chunk.
        try:
            await self.client.append_audio(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("append_audio failed: %s", exc)

    async def _pump_aoai_to_client(self) -> None:
        async for event in self.client.events():
            etype = event.get("type", "")
            try:
                await self._handle_aoai_event(etype, event)
            except Exception as exc:  # noqa: BLE001
                logger.warning("event handle error (%s): %s", etype, exc)

    async def _handle_aoai_event(self, etype: str, event: dict[str, Any]) -> None:
        # ---------- VAD / turn lifecycle ----------
        if etype == "input_audio_buffer.speech_started":
            # If the assistant is currently speaking, user is interrupting.
            if self.assistant_speaking:
                await self.client.cancel_response()
                if self.current_turn:
                    self.current_turn.interrupted = True
            await self.send_json({"type": "state", "state": "listening"})

        elif etype == "input_audio_buffer.speech_stopped":
            self.current_turn = TurnMetrics(turn_id=str(uuid.uuid4())[:8])
            self.current_turn.user_speech_ended_at = time.monotonic()
            await self.send_json({"type": "state", "state": "thinking"})

        elif etype == "conversation.item.input_audio_transcription.completed":
            text = event.get("transcript", "")
            await self.send_json(
                {"type": "transcript", "role": "user", "text": text, "final": True}
            )

        # ---------- assistant audio ----------
        elif etype == "response.audio.delta":
            import base64

            b64 = event.get("delta", "")
            if b64:
                pcm = base64.b64decode(b64)
                if not self.assistant_speaking:
                    self.assistant_speaking = True
                    if self.current_turn and self.current_turn.first_audio_at is None:
                        self.current_turn.first_audio_at = time.monotonic()
                    await self.send_json({"type": "state", "state": "speaking"})
                await self.send_audio(pcm)

        elif etype == "response.audio_transcript.delta":
            await self.send_json(
                {
                    "type": "transcript",
                    "role": "assistant",
                    "text": event.get("delta", ""),
                    "final": False,
                }
            )

        elif etype == "response.audio_transcript.done":
            await self.send_json(
                {
                    "type": "transcript",
                    "role": "assistant",
                    "text": event.get("transcript", ""),
                    "final": True,
                }
            )

        elif etype == "response.done":
            self.assistant_speaking = False
            if self.current_turn:
                self.current_turn.response_done_at = time.monotonic()
                summary = self.current_turn.summary()
                self.current_turn.emit()
                await self.send_json({"type": "latency", **summary})
                self.current_turn = None
            await self.send_json({"type": "state", "state": "idle"})

        # ---------- tool calling ----------
        elif etype == "response.function_call_arguments.done":
            name = event.get("name", "")
            call_id = event.get("call_id", "")
            try:
                args = json.loads(event.get("arguments") or "{}")
            except Exception:
                args = {}
            result = dispatch(name, args)
            if self.current_turn:
                self.current_turn.tool_calls.append(name)
            await self._broadcast_tool(name, args, result)
            await self.client.send_tool_result(call_id, result)
            # Allow model to continue generating after tool result.
            await self.client.trigger_response()

        elif etype == "error":
            err = event.get("error", {})
            await self.send_json(
                {"type": "error", "message": err.get("message", "AOAI error")}
            )

    async def _broadcast_tool(
        self, name: str, args: dict[str, Any], result: dict[str, Any]
    ) -> None:
        await self.send_json({"type": "tool", "name": name, "args": args, "result": result})
        if name == "set_mode":
            self.current_turn and setattr(self.current_turn, "mode", args.get("mode"))
            await self.send_json(
                {"type": "mode", "mode": args.get("mode"), "reason": args.get("reason", "")}
            )
        elif name == "request_high_res_frame":
            await self.send_json(
                {
                    "type": "request_frame",
                    "quality": "high",
                    "purpose": args.get("purpose", ""),
                }
            )
        elif name == "frame_quality_check":
            await self.send_json(
                {
                    "type": "quality",
                    "is_usable": args.get("is_usable"),
                    "issue": args.get("issue"),
                    "hint": args.get("hint"),
                }
            )
        elif name == "raise_safety_alert":
            await self.send_json(
                {
                    "type": "safety",
                    "category": args.get("category"),
                    "message": args.get("message", ""),
                }
            )
        elif name == "set_language":
            self.lang = args.get("lang", self.lang)

    # ---------- utils ----------
    @staticmethod
    def _safe_json(text: str) -> dict[str, Any]:
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


class suppress:  # tiny inline context manager (avoid extra import)
    def __enter__(self):  # noqa: D401
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401
        return True


@router.websocket("/ws/session")
async def ws_session(ws: WebSocket) -> None:
    session = Session(ws)
    await session.run()
