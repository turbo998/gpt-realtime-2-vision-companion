"""Azure OpenAI Realtime client. Implemented in the realtime-integration step."""
from __future__ import annotations


class RealtimeClient:
    """Thin wrapper around Azure OpenAI Realtime WebSocket.

    Responsibilities (to be implemented):
      - establish WSS to {endpoint}/openai/realtime?deployment={...}&api-version={...}
      - auth: bearer token from DefaultAzureCredential, or api-key header
      - session.update with VAD config, system instructions, tools
      - inject input_audio_buffer.append chunks
      - inject conversation.item.create with image_url for vision input
      - dispatch server events back to caller
      - graceful close + response.cancel for user-driven interrupts
    """

    def __init__(self, *, endpoint: str, deployment: str, api_version: str) -> None:
        self.endpoint = endpoint
        self.deployment = deployment
        self.api_version = api_version

    async def connect(self) -> None:  # pragma: no cover
        raise NotImplementedError
