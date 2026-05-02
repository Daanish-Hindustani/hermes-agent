"""Transcript normalization helpers for binder skill evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class Transcript:
    tool_calls: list[ToolCall]
    final_response: str = ""


def normalize_transcript(value: Any) -> Transcript:
    """Convert run results, message lists, or simple dicts into a Transcript."""

    if isinstance(value, Transcript):
        return value
    if isinstance(value, list):
        return Transcript(tool_calls=_calls_from_messages(value), final_response=_last_text(value))
    if isinstance(value, dict):
        if "tool_calls" in value:
            return Transcript(
                tool_calls=[_tool_call_from_any(call) for call in value.get("tool_calls") or []],
                final_response=str(value.get("final_response") or value.get("response") or ""),
            )
        if "messages" in value:
            return Transcript(
                tool_calls=_calls_from_messages(value.get("messages") or []),
                final_response=str(value.get("final_response") or _last_text(value.get("messages") or [])),
            )
    raise TypeError(f"Unsupported transcript type: {type(value).__name__}")


def _calls_from_messages(messages: list[Any]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        for call in msg.get("tool_calls") or []:
            calls.append(_tool_call_from_any(call))
    return calls


def _tool_call_from_any(call: Any) -> ToolCall:
    if isinstance(call, ToolCall):
        return call
    if not isinstance(call, dict):
        raise TypeError(f"Unsupported tool call type: {type(call).__name__}")
    if "function" in call:
        fn = call.get("function") or {}
        name = str(fn.get("name") or "")
        args = _parse_args(fn.get("arguments"))
    else:
        name = str(call.get("name") or "")
        args = _parse_args(call.get("args", call.get("arguments", {})))
    return ToolCall(name=name, args=args)


def _parse_args(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        if not value.strip():
            return {}
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    return {}


def _last_text(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("content"):
            return str(msg["content"])
    return ""

