"""Smoke tests for the FastAPI app + WS session."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_ws_session_handshake_stub() -> None:
    """Server should announce 'ready' and (with no Azure config) flag stub mode."""
    client = TestClient(app)
    with client.websocket_connect("/ws/session") as ws:
        first = ws.receive_json()
        assert first["type"] == "ready"
        second = ws.receive_json()
        assert second["type"] == "ready"
        assert second.get("stub") is True


def test_ws_session_text_in_stub_mode() -> None:
    """In stub mode, sending text triggers transcript echo + latency frame."""
    client = TestClient(app)
    with client.websocket_connect("/ws/session") as ws:
        ws.receive_json()  # ready 1
        ws.receive_json()  # ready 2 (stub)
        ws.send_text('{"type":"text","text":"你好"}')
        # Stub emits exactly 3 frames: user transcript, assistant transcript, latency
        m1 = ws.receive_json()
        m2 = ws.receive_json()
        m3 = ws.receive_json()
        types = {m1.get("type"), m2.get("type"), m3.get("type")}
        assert "transcript" in types
        assert "latency" in types
