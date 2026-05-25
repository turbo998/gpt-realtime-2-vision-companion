"""Function calling tool definitions exposed to the realtime model.

These tools are *control-plane* hints; most of them just report state back so
the model can adapt its behaviour. The frontend reacts to a subset
(request_high_res_frame, frame_quality_check) via downstream events.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Tool schemas (must match Azure OpenAI Realtime "tools" format).
# ---------------------------------------------------------------------------
TOOLS: list[dict] = [
    {
        "type": "function",
        "name": "set_mode",
        "description": (
            "Switch the assistant into a specialised mode. Call ONCE when the "
            "user intent or scene clearly maps to one of the modes; stay silent "
            "otherwise."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": [
                        "default",
                        "read_text",
                        "describe_scene",
                        "find_object",
                        "navigate",
                        "money",
                        "traffic",
                        "transit",
                    ],
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason (<=20 chars) shown in UI badge.",
                },
            },
            "required": ["mode"],
        },
    },
    {
        "type": "function",
        "name": "request_high_res_frame",
        "description": (
            "Ask the client to send a HIGH-resolution frame (1280x960) for "
            "reading small text or fine detail. Default frames are low-res."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "purpose": {
                    "type": "string",
                    "description": "Why HD is needed (e.g. '药盒小字')",
                }
            },
        },
    },
    {
        "type": "function",
        "name": "frame_quality_check",
        "description": (
            "Coach the user when the current frame is unusable (too dark, "
            "blurry, blocked, off-target). Returns a short spoken hint."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "is_usable": {"type": "boolean"},
                "issue": {
                    "type": "string",
                    "enum": [
                        "too_dark",
                        "too_bright",
                        "blurry",
                        "blocked",
                        "off_target",
                        "ok",
                    ],
                },
                "hint": {
                    "type": "string",
                    "description": "Short spoken hint for the user (zh or en).",
                },
            },
            "required": ["is_usable", "issue", "hint"],
        },
    },
    {
        "type": "function",
        "name": "raise_safety_alert",
        "description": (
            "Raise an immediate safety alert (steps, vehicle, obstacle). "
            "Frontend will trigger a strong haptic + audio cue."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "step",
                        "vehicle",
                        "obstacle",
                        "traffic_light",
                        "hot_or_sharp",
                    ],
                },
                "message": {
                    "type": "string",
                    "description": "One-sentence spoken warning.",
                },
            },
            "required": ["category", "message"],
        },
    },
    {
        "type": "function",
        "name": "set_language",
        "description": "Switch active speaking language.",
        "parameters": {
            "type": "object",
            "properties": {"lang": {"type": "string", "enum": ["zh", "en"]}},
            "required": ["lang"],
        },
    },
]


# ---------------------------------------------------------------------------
# Handlers — return a JSON-able dict; ws_session forwards back via
# response.function_call_output and emits a frontend "tool" event for UI.
# ---------------------------------------------------------------------------
def handle_set_mode(args: dict[str, Any]) -> dict[str, Any]:
    mode = args.get("mode", "default")
    reason = args.get("reason", "")
    return {"ok": True, "mode": mode, "reason": reason}


def handle_request_high_res_frame(args: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "purpose": args.get("purpose", "")}


def handle_frame_quality_check(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "is_usable": bool(args.get("is_usable", False)),
        "issue": args.get("issue", "ok"),
        "hint": args.get("hint", ""),
    }


def handle_raise_safety_alert(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "category": args.get("category", "obstacle"),
        "message": args.get("message", ""),
    }


def handle_set_language(args: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "lang": args.get("lang", "zh")}


HANDLERS = {
    "set_mode": handle_set_mode,
    "request_high_res_frame": handle_request_high_res_frame,
    "frame_quality_check": handle_frame_quality_check,
    "raise_safety_alert": handle_raise_safety_alert,
    "set_language": handle_set_language,
}


def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    fn = HANDLERS.get(name)
    if not fn:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        return fn(args or {})
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
