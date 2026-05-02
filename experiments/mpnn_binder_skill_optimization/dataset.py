"""Dataset loading for binder-only ProteinMPNN skill optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


ALLOWED_TOOL_NAMES = {
    "inspect_structure",
    "rfd3_design",
    "protein_mpnn_design",
    "esmfold_predict",
    "alphafold2_multimer_predict",
}


@dataclass(frozen=True)
class Scenario:
    """One ProteinMPNN binder sequence-design evaluation case."""

    id: str
    name: str
    prompt: str
    mock_tools: dict[str, Any] = field(default_factory=dict)
    expectations: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


def load_scenarios(path: str | Path) -> list[Scenario]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Scenario file must contain a mapping.")
    items = raw.get("scenarios")
    if not isinstance(items, list) or not items:
        raise ValueError("Scenario file must define a non-empty 'scenarios' list.")

    scenarios: list[Scenario] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each scenario must be a mapping.")
        scenario = Scenario(
            id=_require_str(item, "id"),
            name=str(item.get("name") or item["id"]),
            prompt=_require_str(item, "prompt"),
            mock_tools=dict(item.get("mock_tools") or {}),
            expectations=dict(item.get("expectations") or {}),
            weight=float(item.get("weight", 1.0)),
        )
        validate_scenario(scenario)
        scenarios.append(scenario)
    return scenarios


def validate_scenario(scenario: Scenario) -> None:
    expectations = scenario.expectations
    if expectations.get("target_skill", "protein_mpnn_design") != "protein_mpnn_design":
        raise ValueError(f"{scenario.id}: target_skill must be protein_mpnn_design.")
    if expectations.get("binder_only") is not True:
        raise ValueError(f"{scenario.id}: ProteinMPNN optimization scenarios must be binder_only.")

    for key in ("required_tools", "forbidden_tools"):
        value = expectations.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"{scenario.id}: {key} must be a list.")
        unknown = set(value) - ALLOWED_TOOL_NAMES
        if unknown:
            raise ValueError(f"{scenario.id}: unknown tools in {key}: {sorted(unknown)}")


def _require_str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Scenario is missing required string field: {key}")
    return value

