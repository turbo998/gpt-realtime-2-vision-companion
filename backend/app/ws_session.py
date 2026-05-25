"""WebSocket session orchestration. Implemented in the realtime-integration step."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/session")
async def ws_session(ws: WebSocket) -> None:
    """Placeholder WebSocket endpoint.

    Real implementation (next todos):
      - accept connection
      - bridge client audio frames <-> Azure OpenAI Realtime
      - on user-turn-start: inject latest frame from client as input_image
      - relay server events back to client (audio.delta, response.done, tool_call, ...)
    """
    await ws.accept()
    try:
        await ws.send_json({"type": "hello", "message": "ws_session scaffold ready"})
        while True:
            msg = await ws.receive_text()
            await ws.send_json({"type": "echo", "data": msg})
    except WebSocketDisconnect:
        return
