import json
import sys
import types
from pathlib import Path

import pytest

from experiments.mpnn_binder_skill_optimization.dataset import load_scenarios
from experiments.mpnn_binder_skill_optimization.gepa_adapter import optimize_skill
from experiments.mpnn_binder_skill_optimization.scoring import score_scenario
from experiments.rfd3_binder_skill_optimization.reporting import write_json_report, write_markdown_report
from experiments.rfd3_binder_skill_optimization.transcript import Transcript, ToolCall


DATASET = Path(__file__).resolve().parents[2] / "experiments" / "mpnn_binder_skill_optimization" / "data" / "scenarios.yaml"


def test_load_scenarios_are_binder_only_mpnn():
    scenarios = load_scenarios(DATASET)

    assert scenarios
    for scenario in scenarios:
        assert scenario.expectations["target_skill"] == "protein_mpnn_design"
        assert scenario.expectations["binder_only"] is True


def test_load_scenarios_rejects_non_mpnn_target(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
scenarios:
  - id: bad
    prompt: optimize RFD3 instead
    expectations:
      target_skill: rfd3_design
      binder_only: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="target_skill"):
        load_scenarios(path)


def test_score_accepts_correct_chain_remap_transcript():
    scenario = next(item for item in load_scenarios(DATASET) if item.id == "chain_remap_binder_not_target")
    transcript = Transcript(
        tool_calls=[
            ToolCall("inspect_structure", {"structure_path": "/mock/rfd3/remap/model_0.cif.gz"}),
            ToolCall(
                "protein_mpnn_design",
                {
                    "structure_path": "/mock/rfd3/remap/model_0.cif.gz",
                    "output_name": "remap_mpnn",
                    "designed_chains": "A",
                    "temperature": 0.1,
                    "num_sequences": 16,
                    "model_type": "protein_mpnn",
                },
            ),
        ],
        final_response="Computational sequence candidates only.",
    )

    result = score_scenario(scenario, transcript)

    assert result.score == result.max_score
    assert result.diagnostics == []


def test_score_flags_target_chain_design_and_wrong_model():
    scenario = next(item for item in load_scenarios(DATASET) if item.id == "chain_remap_binder_not_target")
    transcript = Transcript(
        tool_calls=[
            ToolCall(
                "protein_mpnn_design",
                {
                    "structure_path": "/mock/rfd3/remap/model_0.cif.gz",
                    "designed_chains": "B",
                    "temperature": 0.3,
                    "model_type": "ligand_mpnn",
                },
            ),
        ],
        final_response="This is a validated binder.",
    )

    result = score_scenario(scenario, transcript)

    assert result.score < result.max_score
    assert any("Inspect generated RFD3 output" in item for item in result.diagnostics)
    assert any("binder chain A" in item for item in result.diagnostics)
    assert any("target chain B" in item for item in result.diagnostics)
    assert any("Expected model_type protein_mpnn" in item for item in result.diagnostics)
    assert any("overclaimed" in item for item in result.diagnostics)


def test_score_accepts_ligand_context_model_type():
    scenario = next(item for item in load_scenarios(DATASET) if item.id == "ligand_context")
    transcript = Transcript(
        tool_calls=[
            ToolCall("inspect_structure", {"structure_path": "/mock/rfd3/ligand/model_0.cif.gz"}),
            ToolCall(
                "protein_mpnn_design",
                {
                    "structure_path": "/mock/rfd3/ligand/model_0.cif.gz",
                    "designed_chains": "A",
                    "temperature": 0.1,
                    "model_type": "ligand_mpnn",
                },
            ),
        ],
        final_response="Computational candidate only.",
    )

    result = score_scenario(scenario, transcript)

    assert result.score == result.max_score


def test_score_accepts_batch_and_fixed_position_cases():
    scenarios = {scenario.id: scenario for scenario in load_scenarios(DATASET)}
    batch = score_scenario(
        scenarios["batch_backbone_design"],
        Transcript(
            tool_calls=[
                ToolCall(
                    "protein_mpnn_design",
                    {
                        "structure_paths": ["/mock/rfd3/batch/model_0.cif.gz", "/mock/rfd3/batch/model_1.cif.gz"],
                        "designed_chains": "A",
                        "temperature": 0.1,
                        "model_type": "protein_mpnn",
                    },
                )
            ],
            final_response="Computational candidates only.",
        ),
    )
    fixed = score_scenario(
        scenarios["fixed_interface_positions"],
        Transcript(
            tool_calls=[
                ToolCall(
                    "protein_mpnn_design",
                    {
                        "structure_path": "/mock/rfd3/fixed/model_0.cif.gz",
                        "designed_chains": "A",
                        "temperature": 0.1,
                        "model_type": "protein_mpnn",
                        "fixed_positions": "A12,A15,A18",
                    },
                )
            ],
            final_response="Computational candidates only.",
        ),
    )

    assert batch.diagnostics == []
    assert fixed.diagnostics == []


def test_score_flags_missing_esmfold_followup():
    scenario = next(item for item in load_scenarios(DATASET) if item.id == "basic_rfd3_backbone_to_mpnn")
    transcript = Transcript(
        tool_calls=[
            ToolCall("inspect_structure", {}),
            ToolCall(
                "protein_mpnn_design",
                {
                    "structure_path": "/mock/rfd3/basic/model_0.cif.gz",
                    "designed_chains": "A",
                    "temperature": 0.1,
                    "model_type": "protein_mpnn",
                },
            ),
        ],
        final_response="Sequence candidates generated.",
    )

    result = score_scenario(scenario, transcript)

    assert any("ESMFold" in item for item in result.diagnostics)


def test_score_accepts_fold_collapse_guidance():
    scenario = next(item for item in load_scenarios(DATASET) if item.id == "fold_collapse_after_mpnn")
    transcript = Transcript(
        tool_calls=[],
        final_response="Lower temperature or return to RFD3 for a new backbone before spending more compute.",
    )

    result = score_scenario(scenario, transcript)

    assert result.diagnostics == []


def test_report_writers_work_with_mpnn_results(tmp_path):
    scenario = next(item for item in load_scenarios(DATASET) if item.id == "safe_reporting")
    result = score_scenario(scenario, Transcript(tool_calls=[], final_response="Computational candidates only."))
    payload = {"score": 1.0, "scenarios": [result]}
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    write_json_report(json_path, payload)
    write_markdown_report(md_path, "Report", payload)

    assert json.loads(json_path.read_text(encoding="utf-8"))["score"] == 1.0
    assert "safe_reporting" in md_path.read_text(encoding="utf-8")


def test_gepa_adapter_writes_candidate_with_fake_optimizer(tmp_path, monkeypatch):
    scenarios = [next(item for item in load_scenarios(DATASET) if item.id == "safe_reporting")]
    gepa_pkg = types.ModuleType("gepa")
    gepa_mod = types.ModuleType("gepa.optimize_anything")

    def fake_optimize_anything(seed_candidate, evaluator, dataset, objective, background):
        assert "protein-mpnn-design" in objective
        score = evaluator(seed_candidate + "\n\nOptimized MPNN guidance.", dataset[0])
        assert score["score"] >= 0
        return {"best_candidate": seed_candidate + "\n\nOptimized MPNN guidance."}

    gepa_mod.optimize_anything = fake_optimize_anything
    gepa_pkg.optimize_anything = gepa_mod
    monkeypatch.setitem(sys.modules, "gepa", gepa_pkg)
    monkeypatch.setitem(sys.modules, "gepa.optimize_anything", gepa_mod)
    monkeypatch.setattr(
        "experiments.mpnn_binder_skill_optimization.gepa_adapter.run_candidate",
        lambda **_: {"safe_reporting": Transcript(tool_calls=[], final_response="Computational candidates only.")},
    )

    result = optimize_skill(
        seed_skill="# ProteinMPNN Design\n",
        reference_skill="# Protein Binder Design\n",
        scenarios=scenarios,
        out_dir=tmp_path,
    )

    candidate_path = Path(result["candidate_path"])
    assert candidate_path.exists()
    assert "Optimized MPNN guidance" in candidate_path.read_text(encoding="utf-8")


def test_compare_script_does_not_overwrite_skill(tmp_path, monkeypatch):
    import scripts.compare_mpnn_binder_skill_baseline as compare_script

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
        lambda **_: {"safe_reporting": Transcript(tool_calls=[], final_response="Computational candidates only.")},
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

