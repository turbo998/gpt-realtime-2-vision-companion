"""Smoke tests for the FastAPI app skeleton."""
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


def test_ws_session_handshake() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws/session") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        ws.send_text("ping")
        echo = ws.receive_json()
        assert echo == {"type": "echo", "data": "ping"}
