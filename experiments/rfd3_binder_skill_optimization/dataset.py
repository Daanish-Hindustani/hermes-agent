"""Dataset loading for binder-only RFD3 skill optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


BINDER_MODE = "binder"
ALLOWED_TOOL_NAMES = {
    "inspect_structure",
    "rfd3_design",
    "protein_mpnn_design",
    "esmfold_predict",
    "alphafold2_multimer_predict",
    "rcsb_search",
    "uniprot_search",
    "pubmed_search",
}


@dataclass(frozen=True)
class Scenario:
    """One binder-design evaluation case."""

    id: str
    name: str
    prompt: str
    mock_tools: dict[str, Any] = field(default_factory=dict)
    expectations: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


def load_scenarios(path: str | Path) -> list[Scenario]:
    """Load and validate binder-only scenarios from YAML."""

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Scenario file must contain a mapping.")
    scenarios_raw = raw.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise ValueError("Scenario file must define a non-empty 'scenarios' list.")

    scenarios: list[Scenario] = []
    for item in scenarios_raw:
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
    """Reject non-binder scenarios and malformed expectations early."""

    expected_mode = scenario.expectations.get("mode", BINDER_MODE)
    if expected_mode != BINDER_MODE:
        raise ValueError(f"{scenario.id}: only binder mode scenarios are allowed.")

    forbidden_modes = set(scenario.expectations.get("forbidden_modes") or [])
    if forbidden_modes & {BINDER_MODE}:
        raise ValueError(f"{scenario.id}: binder cannot be a forbidden mode.")
    non_binder_modes = {"free_generation", "motif_scaffold", "partial_diffusion"}
    if not non_binder_modes <= forbidden_modes:
        raise ValueError(
            f"{scenario.id}: binder-only scenarios must forbid free_generation, "
            "motif_scaffold, and partial_diffusion."
        )

    for key in ("required_tools", "forbidden_tools"):
        value = scenario.expectations.get(key, [])
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

