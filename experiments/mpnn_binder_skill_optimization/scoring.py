"""ProteinMPNN-specific scoring for binder skill optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from experiments.rfd3_binder_skill_optimization.transcript import ToolCall, Transcript, normalize_transcript

from .dataset import Scenario


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    points: float
    max_points: float
    message: str


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    score: float
    max_score: float
    checks: list[CheckResult]
    diagnostics: list[str]
    tool_calls: list[dict[str, Any]]


def score_scenario(scenario: Scenario, transcript_value: Any) -> ScenarioResult:
    transcript = normalize_transcript(transcript_value)
    expectations = scenario.expectations
    checks: list[CheckResult] = []

    _check_required_tools(checks, transcript, expectations.get("required_tools") or [])
    _check_forbidden_tools(checks, transcript, expectations.get("forbidden_tools") or [])
    _check_mpnn_present_when_required(checks, transcript, bool(expectations.get("requires_mpnn_call")))
    _check_structure_input(checks, transcript, expectations)
    _check_chain_selection(checks, transcript, expectations)
    _check_model_type(checks, transcript, expectations)
    _check_temperature(checks, transcript, expectations)
    _check_fixed_positions(checks, transcript, expectations)
    _check_followup(checks, transcript, expectations)
    _check_response_claims(checks, transcript, bool(expectations.get("avoid_validation_claims")))

    points = sum(check.points for check in checks)
    max_points = sum(check.max_points for check in checks) or 1.0
    diagnostics = [check.message for check in checks if not check.passed]
    return ScenarioResult(
        scenario_id=scenario.id,
        score=points,
        max_score=max_points,
        checks=checks,
        diagnostics=diagnostics,
        tool_calls=[{"name": call.name, "args": call.args} for call in transcript.tool_calls],
    )


def score_dataset(scenarios: list[Scenario], transcripts: dict[str, Any]) -> dict[str, Any]:
    results = [score_scenario(scenario, transcripts.get(scenario.id, {})) for scenario in scenarios]
    weighted_score = 0.0
    weighted_max = 0.0
    for scenario, result in zip(scenarios, results):
        weighted_score += result.score * scenario.weight
        weighted_max += result.max_score * scenario.weight
    return {
        "score": weighted_score / weighted_max if weighted_max else 0.0,
        "points": weighted_score,
        "max_points": weighted_max,
        "scenarios": results,
    }


def _check_required_tools(checks: list[CheckResult], transcript: Transcript, required: list[str]) -> None:
    names = [call.name for call in transcript.tool_calls]
    for tool in required:
        _add(checks, f"required_tool:{tool}", tool in names, f"Missing required tool call: {tool}")


def _check_forbidden_tools(checks: list[CheckResult], transcript: Transcript, forbidden: list[str]) -> None:
    names = [call.name for call in transcript.tool_calls]
    for tool in forbidden:
        _add(checks, f"forbidden_tool:{tool}", tool not in names, f"Forbidden tool was called: {tool}")


def _check_mpnn_present_when_required(checks: list[CheckResult], transcript: Transcript, required: bool) -> None:
    if required:
        _add(checks, "mpnn_called", _first_call(transcript.tool_calls, "protein_mpnn_design") is not None, "Missing protein_mpnn_design call.")


def _check_structure_input(checks: list[CheckResult], transcript: Transcript, expectations: dict[str, Any]) -> None:
    mpnn = _first_call(transcript.tool_calls, "protein_mpnn_design")
    if not mpnn:
        return
    if expectations.get("requires_structure_input"):
        has_input = bool(mpnn.args.get("structure_path") or mpnn.args.get("structure_paths"))
        _add(checks, "structure_input", has_input, "protein_mpnn_design needs structure_path or structure_paths.")
    if expectations.get("batch_backbones"):
        paths = mpnn.args.get("structure_paths")
        structure_path = mpnn.args.get("structure_path")
        passed = (isinstance(paths, list) and len(paths) > 1) or (isinstance(structure_path, str) and structure_path.endswith("/"))
        _add(checks, "batch_backbone_input", passed, "Multiple RFD3 backbones should use structure_paths or a directory input.")


def _check_chain_selection(checks: list[CheckResult], transcript: Transcript, expectations: dict[str, Any]) -> None:
    mpnn = _first_call(transcript.tool_calls, "protein_mpnn_design")
    if not mpnn:
        return
    binder_chain = expectations.get("binder_chain")
    target_chain = expectations.get("target_chain")
    if expectations.get("inspect_before_mpnn"):
        names = [call.name for call in transcript.tool_calls]
        mpnn_index = names.index("protein_mpnn_design")
        inspected_before = "inspect_structure" in names[:mpnn_index]
        _add(checks, "inspect_before_mpnn", inspected_before, "Inspect generated RFD3 output before choosing designed_chains.")
    if binder_chain:
        designed = str(mpnn.args.get("designed_chains") or "")
        _add(checks, "designed_binder_chain", binder_chain in _split_chain_list(designed), f"designed_chains must include binder chain {binder_chain}.")
    if target_chain:
        designed = str(mpnn.args.get("designed_chains") or "")
        _add(checks, "target_chain_not_designed", target_chain not in _split_chain_list(designed), f"designed_chains must not include target chain {target_chain}.")


def _check_model_type(checks: list[CheckResult], transcript: Transcript, expectations: dict[str, Any]) -> None:
    mpnn = _first_call(transcript.tool_calls, "protein_mpnn_design")
    if not mpnn:
        return
    expected = expectations.get("expected_model_type")
    if expected:
        actual = str(mpnn.args.get("model_type") or "protein_mpnn")
        _add(checks, "model_type", actual == expected, f"Expected model_type {expected}, got {actual}.")


def _check_temperature(checks: list[CheckResult], transcript: Transcript, expectations: dict[str, Any]) -> None:
    mpnn = _first_call(transcript.tool_calls, "protein_mpnn_design")
    if not mpnn:
        return
    temp = _to_float(mpnn.args.get("temperature", 0.1))
    if expectations.get("initial_temperature"):
        _add(checks, "initial_temperature", temp is not None and 0.05 <= temp <= 0.12, "Initial ProteinMPNN pass should use temperature around 0.1.")
    if expectations.get("diversity_temperature"):
        _add(checks, "diversity_temperature", temp is not None and 0.2 <= temp <= 0.3, "Diversity follow-up should use temperature 0.2-0.3.")
    if expectations.get("avoid_high_initial_temperature"):
        _add(checks, "avoid_high_initial_temperature", temp is None or temp <= 0.12, "Do not jump to high temperature before initial validation.")


def _check_fixed_positions(checks: list[CheckResult], transcript: Transcript, expectations: dict[str, Any]) -> None:
    mpnn = _first_call(transcript.tool_calls, "protein_mpnn_design")
    if not mpnn or not expectations.get("requires_fixed_positions"):
        return
    _add(checks, "fixed_positions", bool(mpnn.args.get("fixed_positions")), "Required fixed residues must be passed via fixed_positions.")


def _check_followup(checks: list[CheckResult], transcript: Transcript, expectations: dict[str, Any]) -> None:
    names = [call.name for call in transcript.tool_calls]
    if expectations.get("requires_esmfold_followup"):
        has_tool = "esmfold_predict" in names
        text_mentions = "esmfold" in transcript.final_response.lower()
        _add(checks, "esmfold_followup", has_tool or text_mentions, "ProteinMPNN outputs should be followed by ESMFold foldability triage.")
    if expectations.get("fold_collapse_response"):
        text = transcript.final_response.lower()
        good_response = ("lower temperature" in text or "return to rfd3" in text or "new backbone" in text or "regenerate" in text)
        _add(checks, "fold_collapse_response", good_response, "Fold collapse should lower MPNN temperature or return to RFD3/backbone selection.")


def _check_response_claims(checks: list[CheckResult], transcript: Transcript, required: bool) -> None:
    if not required:
        return
    text = transcript.final_response.lower()
    banned = ("validated binder", "experimentally validated", "proves binding", "confirmed binder")
    passed = not any(phrase in text for phrase in banned)
    _add(checks, "avoid_validation_claims", passed, "Final response overclaimed computational binder validation.")


def _first_call(calls: list[ToolCall], name: str) -> ToolCall | None:
    return next((call for call in calls if call.name == name), None)


def _split_chain_list(value: str) -> set[str]:
    return {part.strip() for part in value.replace(";", ",").split(",") if part.strip()}


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _add(checks: list[CheckResult], name: str, passed: bool, failure_message: str, max_points: float = 1.0) -> None:
    checks.append(
        CheckResult(
            name=name,
            passed=passed,
            points=max_points if passed else 0.0,
            max_points=max_points,
            message="ok" if passed else failure_message,
        )
    )

