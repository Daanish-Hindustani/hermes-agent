"""Report writers for binder skill optimization."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def write_json_report(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8")


def write_markdown_report(path: str | Path, title: str, payload: dict[str, Any]) -> None:
    lines = [f"# {title}", ""]
    if "baseline" in payload and "candidate" in payload:
        baseline = payload["baseline"]
        candidate = payload["candidate"]
        lines.append(f"Baseline score: **{baseline['score']:.3f}**")
        lines.append(f"Candidate score: **{candidate['score']:.3f}**")
        lines.append(f"Delta: **{payload.get('delta', 0.0):+.3f}**")
        lines.append("")
        payload = candidate
    if "score" in payload:
        lines.append(f"Overall score: **{payload['score']:.3f}**")
        lines.append("")
    for result in payload.get("scenarios", []):
        item = asdict(result) if hasattr(result, "__dataclass_fields__") else result
        max_score = item.get("max_score", 0) or 1
        lines.append(f"## {item.get('scenario_id')}")
        lines.append("")
        lines.append(f"Score: **{item.get('score', 0):.1f}/{max_score:.1f}**")
        lines.append("")
        diagnostics = item.get("diagnostics") or []
        if diagnostics:
            lines.append("Failures:")
            for diagnostic in diagnostics:
                lines.append(f"- {diagnostic}")
        else:
            lines.append("Failures: none")
        lines.append("")
    Path(path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
