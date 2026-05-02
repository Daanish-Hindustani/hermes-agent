import json
import sys
import types
from pathlib import Path

import pytest

from experiments.rfd3_binder_skill_optimization.dataset import load_scenarios
from experiments.rfd3_binder_skill_optimization.gepa_adapter import optimize_skill
from experiments.rfd3_binder_skill_optimization.reporting import write_json_report, write_markdown_report
from experiments.rfd3_binder_skill_optimization.scoring import score_scenario
from experiments.rfd3_binder_skill_optimization.transcript import Transcript, ToolCall


DATASET = Path(__file__).resolve().parents[2] / "experiments" / "rfd3_binder_skill_optimization" / "data" / "scenarios.yaml"


def test_load_scenarios_are_binder_only():
    scenarios = load_scenarios(DATASET)

    assert scenarios
    assert {scenario.expectations["mode"] for scenario in scenarios} == {"binder"}
    for scenario in scenarios:
        assert {"free_generation", "motif_scaffold", "partial_diffusion"} <= set(
            scenario.expectations["forbidden_modes"]
        )


def test_load_scenarios_rejects_non_binder_modes(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
scenarios:
  - id: bad
    prompt: run free generation
    expectations:
      mode: free_generation
      forbidden_modes: [motif_scaffold, partial_diffusion]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="only binder mode"):
        load_scenarios(path)


def test_score_scenario_accepts_correct_binder_transcript():
    scenario = next(item for item in load_scenarios(DATASET) if item.id == "hotspot_binder")
    transcript = Transcript(
        tool_calls=[
            ToolCall("inspect_structure", {"structure_path": "target.pdb"}),
            ToolCall(
                "rfd3_design",
                {
                    "mode": "binder",
                    "contig": "70-110,/0,A1-200",
                    "target_pdb_path": "target.pdb",
                    "hotspot_residues": ["A45", "A47", "A90"],
                    "num_designs": 2,
                    "num_timesteps": 25,
                },
            ),
        ],
        final_response="Best computational candidate needs validation.",
    )

    result = score_scenario(scenario, transcript)

    assert result.score == result.max_score
    assert result.diagnostics == []


def test_score_scenario_flags_bad_binder_transcript():
    scenario = next(item for item in load_scenarios(DATASET) if item.id == "gapped_target_contig")
    transcript = Transcript(
        tool_calls=[
            ToolCall(
                "rfd3_design",
                {
                    "mode": "free_generation",
                    "contig": "70-110,/0,A1-160",
                    "num_designs": 16,
                    "num_timesteps": 200,
                },
            ),
        ],
        final_response="This is an experimentally validated binder.",
    )

    result = score_scenario(scenario, transcript)

    assert result.score < result.max_score
    assert any("Target structure was not inspected" in item for item in result.diagnostics)
    assert any("forbidden RFD3 mode" in item for item in result.diagnostics)
    assert any("forbidden range" in item for item in result.diagnostics)
    assert any("overclaimed" in item for item in result.diagnostics)


def test_report_writers_emit_json_and_markdown(tmp_path):
    scenario = next(item for item in load_scenarios(DATASET) if item.id == "basic_binder_setup")
    result = score_scenario(
        scenario,
        Transcript(
            tool_calls=[
                ToolCall("inspect_structure", {}),
                ToolCall(
                    "rfd3_design",
                    {"mode": "binder", "contig": "70-110,/0,A1-120", "num_designs": 1, "num_timesteps": 25},
                ),
            ],
            final_response="Computational candidate only.",
        ),
    )
    payload = {"score": 1.0, "scenarios": [result]}

    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    write_json_report(json_path, payload)
    write_markdown_report(md_path, "Report", payload)

    assert json.loads(json_path.read_text(encoding="utf-8"))["score"] == 1.0
    assert "basic_binder_setup" in md_path.read_text(encoding="utf-8")


def test_gepa_adapter_writes_candidate_with_fake_optimizer(tmp_path, monkeypatch):
    scenarios = [next(item for item in load_scenarios(DATASET) if item.id == "basic_binder_setup")]

    gepa_pkg = types.ModuleType("gepa")
    gepa_mod = types.ModuleType("gepa.optimize_anything")

    def fake_optimize_anything(seed_candidate, evaluator, dataset, objective, background):
        assert "binder design only" in objective
        score = evaluator(seed_candidate + "\n\nOptimized binder guidance.", dataset[0])
        assert score["score"] >= 0
        return {"best_candidate": seed_candidate + "\n\nOptimized binder guidance."}

    gepa_mod.optimize_anything = fake_optimize_anything
    gepa_pkg.optimize_anything = gepa_mod
    monkeypatch.setitem(sys.modules, "gepa", gepa_pkg)
    monkeypatch.setitem(sys.modules, "gepa.optimize_anything", gepa_mod)

    monkeypatch.setattr(
        "experiments.rfd3_binder_skill_optimization.gepa_adapter.run_candidate",
        lambda **_: {
            "basic_binder_setup": Transcript(
                tool_calls=[
                    ToolCall("inspect_structure", {}),
                    ToolCall(
                        "rfd3_design",
                        {"mode": "binder", "contig": "70-110,/0,A1-120", "num_designs": 1, "num_timesteps": 25},
                    ),
                ],
                final_response="Computational candidate only.",
            )
        },
    )

    result = optimize_skill(
        seed_skill="# RFdiffusion3 Design\n",
        reference_skill="# Protein Binder Design\n",
        scenarios=scenarios,
        out_dir=tmp_path,
    )

    candidate_path = Path(result["candidate_path"])
    assert candidate_path.exists()
    assert "Optimized binder guidance" in candidate_path.read_text(encoding="utf-8")


def test_compare_script_does_not_overwrite_skill(tmp_path, monkeypatch):
    import scripts.compare_rfd3_binder_skill_baseline as compare_script

    baseline = tmp_path / "baseline.SKILL.md"
    candidate = tmp_path / "candidate.SKILL.md"
    reference = tmp_path / "reference.SKILL.md"
    baseline.write_text("# baseline\n", encoding="utf-8")
    candidate.write_text("# candidate\n", encoding="utf-8")
    reference.write_text("# reference\n", encoding="utf-8")
    before = baseline.read_text(encoding="utf-8")

    monkeypatch.setattr(
        compare_script,
        "run_candidate",
        lambda **_: {
            "basic_binder_setup": Transcript(
                tool_calls=[
                    ToolCall("inspect_structure", {}),
                    ToolCall(
                        "rfd3_design",
                        {"mode": "binder", "contig": "70-110,/0,A1-120", "num_designs": 1, "num_timesteps": 25},
                    ),
                ],
                final_response="Computational candidate only.",
            )
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--reference-skill",
            str(reference),
            "--dataset",
            str(DATASET),
            "--out",
            str(tmp_path / "out"),
        ],
    )

    assert compare_script.main() == 0
    assert baseline.read_text(encoding="utf-8") == before
    assert (tmp_path / "out" / "comparison_report.json").exists()

