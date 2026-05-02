"""Binder-specific scoring for RFD3 skill optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dataset import Scenario
from .transcript import ToolCall, Transcript, normalize_transcript


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
    _check_forbidden_modes(checks, transcript, expectations.get("forbidden_modes") or [])
    _check_inspect_before_rfd3(checks, transcript, bool(expectations.get("inspect_before_rfd3")))
    _check_rfd3_args(checks, transcript, expectations)
    _check_mpnn_args(checks, transcript, expectations)
    _check_failure_mode_guidance(checks, transcript, expectations)
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


def _check_forbidden_modes(checks: list[CheckResult], transcript: Transcript, forbidden: list[str]) -> None:
    for mode in forbidden:
        bad = any(call.name == "rfd3_design" and call.args.get("mode") == mode for call in transcript.tool_calls)
        _add(checks, f"forbidden_mode:{mode}", not bad, f"Used forbidden RFD3 mode: {mode}")


def _check_inspect_before_rfd3(checks: list[CheckResult], transcript: Transcript, required: bool) -> None:
    if not required:
        return
    names = [call.name for call in transcript.tool_calls]
    passed = "inspect_structure" in names and "rfd3_design" in names and names.index("inspect_structure") < names.index("rfd3_design")
    _add(checks, "inspect_before_rfd3", passed, "Target structure was not inspected before rfd3_design.")


def _check_rfd3_args(checks: list[CheckResult], transcript: Transcript, expectations: dict[str, Any]) -> None:
    rfd3 = _first_call(transcript.tool_calls, "rfd3_design")
    if not rfd3:
        return
    _add(checks, "rfd3_mode_binder", rfd3.args.get("mode") == "binder", "rfd3_design mode must be binder.")

    contig = str(rfd3.args.get("contig") or "")
    if expectations.get("binder_contig_pattern"):
        _add(
            checks,
            "binder_contig_pattern",
            ",/0," in contig and contig.split(",/0,", 1)[0][:1].isdigit(),
            "Contig must use binder pattern '<length>,/0,<target_chain_range>'.",
        )
    forbidden_contigs = expectations.get("forbidden_contigs") or []
    for forbidden in forbidden_contigs:
        _add(checks, f"forbidden_contig:{forbidden}", forbidden not in contig, f"Contig used forbidden range: {forbidden}")
    required_segments = expectations.get("required_contig_segments") or []
    for segment in required_segments:
        _add(checks, f"required_contig_segment:{segment}", str(segment) in contig, f"Contig must include target context segment: {segment}")

    if expectations.get("hotspots_separate"):
        hotspots = rfd3.args.get("hotspot_residues")
        _add(checks, "hotspots_separate", bool(hotspots), "Hotspots must be passed via hotspot_residues.")

    guide_range = expectations.get("guide_scale_range")
    if guide_range:
        guide_scale = _to_float(rfd3.args.get("guide_scale", 1.5))
        low, high = float(guide_range[0]), float(guide_range[1])
        _add(checks, "guide_scale_range", guide_scale is not None and low <= guide_scale <= high, f"guide_scale should stay in {low}-{high} for binder iteration.")

    debug = expectations.get("debug_first")
    if debug:
        num_designs = _to_int(rfd3.args.get("num_designs"))
        timesteps = _to_int(rfd3.args.get("num_timesteps"))
        _add(checks, "debug_num_designs", num_designs is not None and 1 <= num_designs <= 4, "Debug RFD3 run should use num_designs=1-4.")
        _add(checks, "debug_num_timesteps", timesteps is not None and 25 <= timesteps <= 50, "Debug RFD3 run should use num_timesteps=25-50.")

    scale = expectations.get("scale_up")
    if scale:
        num_designs = _to_int(rfd3.args.get("num_designs"))
        timesteps = _to_int(rfd3.args.get("num_timesteps"))
        _add(checks, "scale_num_designs", num_designs is not None and 8 <= num_designs <= 32, "Scale-up run should use num_designs=8-32.")
        _add(checks, "scale_num_timesteps", timesteps is not None and 100 <= timesteps <= 200, "Scale-up run should use num_timesteps=100-200.")


def _check_mpnn_args(checks: list[CheckResult], transcript: Transcript, expectations: dict[str, Any]) -> None:
    if not expectations.get("inspect_before_mpnn"):
        return
    names = [call.name for call in transcript.tool_calls]
    mpnn_indices = [idx for idx, name in enumerate(names) if name == "protein_mpnn_design"]
    if not mpnn_indices:
        return
    first_mpnn = mpnn_indices[0]
    inspected_before = any(name == "inspect_structure" for name in names[:first_mpnn])
    _add(checks, "inspect_before_mpnn", inspected_before, "Generated RFD3 output must be inspected before ProteinMPNN chain selection.")


def _check_response_claims(checks: list[CheckResult], transcript: Transcript, required: bool) -> None:
    if not required:
        return
    text = transcript.final_response.lower()
    banned = ("validated binder", "experimentally validated", "proves binding", "confirmed binder")
    passed = not any(phrase in text for phrase in banned)
    _add(checks, "avoid_validation_claims", passed, "Final response overclaimed computational binder validation.")


def _check_failure_mode_guidance(checks: list[CheckResult], transcript: Transcript, expectations: dict[str, Any]) -> None:
    mode = expectations.get("failure_mode_guidance")
    if not mode and not expectations.get("avoid_identical_rerun"):
        return
    text = transcript.final_response.lower()
    if expectations.get("avoid_identical_rerun"):
        rerun_bad = "same settings" in text or "identical settings" in text or "rerun identical" in text
        _add(checks, "avoid_identical_rerun", not rerun_bad, "Do not recommend rerunning identical RFD3 settings.")
    if mode == "invalid_inputs":
        passed = any(phrase in text for phrase in ("chain id", "chain ids", "residue numbering", "contig", "target_pdb_path", "target path"))
        _add(checks, "invalid_input_guidance", passed, "Invalid inputs should trigger chain/residue/contig/target path checks, not parameter tuning.")
    elif mode == "no_interface":
        passed = any(phrase in text for phrase in ("hotspot", "target context", "longer binder", "guide_scale", "epitope"))
        _add(checks, "no_interface_guidance", passed, "No-interface failures should revise hotspots, target context, binder length, or guide_scale.")
    elif mode == "low_diversity":
        passed = any(phrase in text for phrase in ("broaden", "binder length", "alternative hotspot", "hotspot subset", "diversity"))
        _add(checks, "low_diversity_guidance", passed, "Low diversity should broaden binder length or use alternative hotspot subsets.")


def _first_call(calls: list[ToolCall], name: str) -> ToolCall | None:
    return next((call for call in calls if call.name == name), None)


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


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
