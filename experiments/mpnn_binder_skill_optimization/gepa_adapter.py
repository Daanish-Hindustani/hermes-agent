"""GEPA adapter for binder-only ProteinMPNN skill optimization."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dataset import Scenario
from .hermes_runner import run_candidate
from .scoring import score_dataset


OBJECTIVE = (
    "Optimize the Hermes protein-mpnn-design SKILL.md for protein binder "
    "sequence design after RFD3. Improve generated-backbone selection, binder "
    "chain detection, designed_chains, protein_mpnn versus ligand_mpnn model "
    "choice, temperature strategy, fixed_positions, ESMFold follow-up, and "
    "conservative computational-binder reporting."
)


def optimize_skill(
    *,
    seed_skill: str,
    reference_skill: str,
    scenarios: list[Scenario],
    out_dir: str | Path,
    model: str = "",
    provider: str | None = None,
    api_mode: str | None = None,
) -> dict[str, Any]:
    import gepa.optimize_anything as oa

    def evaluator(candidate: Any, data_inst: Any = None, **_: Any) -> dict[str, Any]:
        selected = _select_scenarios(scenarios, data_inst)
        transcripts = run_candidate(
            skill_text=str(candidate),
            reference_skill_text=reference_skill,
            scenarios=selected,
            model=model,
            provider=provider,
            api_mode=api_mode,
        )
        scored = score_dataset(selected, transcripts)
        diagnostics = []
        for result in scored["scenarios"]:
            diagnostics.extend(result.diagnostics)
        return {
            "score": scored["score"],
            "feedback": "\n".join(diagnostics) if diagnostics else "All ProteinMPNN binder checks passed.",
            "details": scored,
        }

    result = oa.optimize_anything(
        seed_candidate=seed_skill,
        evaluator=evaluator,
        dataset=[{"scenario_id": scenario.id} for scenario in scenarios],
        objective=OBJECTIVE,
        background=reference_skill,
    )
    candidate_text = _extract_candidate_text(result)
    output_path = _write_candidate(out_dir, candidate_text)
    return {"candidate_path": str(output_path), "gepa_result": result}


def _select_scenarios(scenarios: list[Scenario], data_inst: Any) -> list[Scenario]:
    if not data_inst:
        return scenarios
    scenario_id = data_inst.get("scenario_id") if isinstance(data_inst, dict) else None
    if not scenario_id:
        return scenarios
    return [scenario for scenario in scenarios if scenario.id == scenario_id]


def _extract_candidate_text(result: Any) -> str:
    for attr in ("best_candidate", "optimized_candidate", "candidate"):
        value = getattr(result, attr, None)
        if value:
            return str(value)
    if isinstance(result, dict):
        for key in ("best_candidate", "optimized_candidate", "candidate"):
            if result.get(key):
                return str(result[key])
    return str(result)


def _write_candidate(out_dir: str | Path, candidate_text: str) -> Path:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = target / f"protein-mpnn-design.binder-optimized.{stamp}.SKILL.md"
    path.write_text(candidate_text, encoding="utf-8")
    return path

