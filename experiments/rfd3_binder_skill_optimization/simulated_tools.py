"""Deterministic simulated protein-design tools for evaluator runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimulatedProteinTools:
    responses: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def handle(self, function_name: str, function_args: Any, **_: Any) -> str:
        args = _coerce_args(function_args)
        self.calls.append({"name": function_name, "args": args})
        response = self.responses.get(function_name)
        if isinstance(response, list):
            response = response[min(len([c for c in self.calls if c["name"] == function_name]) - 1, len(response) - 1)]
        if response is None:
            response = {"success": True, "mock": True, "tool": function_name}
        return json.dumps(response)


def _coerce_args(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    return {}

