"""Function calling tool definitions exposed to the realtime model."""
from __future__ import annotations

TOOLS: list[dict] = [
    {
        "type": "function",
        "name": "set_mode",
        "description": (
            "Switch the assistant into a specialised mode for this conversation. "
            "Use sparingly only when the user's intent clearly maps to a mode."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["default", "read_text", "describe_scene", "find_object", "navigate"],
                },
                "reason": {"type": "string"},
            },
            "required": ["mode"],
        },
    },
    {
        "type": "function",
        "name": "request_high_res_frame",
        "description": (
            "Ask the client to send a high resolution frame (e.g. for reading small text). "
            "Default frames are low-res to save bandwidth; use only when needed."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "frame_quality_check",
        "description": (
            "Report image quality assessment back to the user (blur, glare, framing). "
            "Use to coach the user to adjust the camera angle."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "is_usable": {"type": "boolean"},
                "hint": {"type": "string", "description": "Short spoken hint for the user."},
            },
            "required": ["is_usable", "hint"],
        },
    },
]
