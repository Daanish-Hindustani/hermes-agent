#!/usr/bin/env python3
"""Compare baseline and candidate RFD3 binder skill performance."""

from __future__ import annotations

import argparse
from pathlib import Path

from experiments.rfd3_binder_skill_optimization.dataset import load_scenarios
from experiments.rfd3_binder_skill_optimization.hermes_runner import load_text, run_candidate
from experiments.rfd3_binder_skill_optimization.reporting import write_json_report, write_markdown_report
from experiments.rfd3_binder_skill_optimization.scoring import score_dataset


DEFAULT_REFERENCE = "skills/protein-design/protein-binder-design/SKILL.md"


def main() -> int:
    args = _parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = load_scenarios(args.dataset)
    reference = load_text(args.reference_skill)

    baseline = _evaluate(
        skill_text=load_text(args.baseline),
        reference_skill=reference,
        scenarios=scenarios,
        model=args.model,
        provider=args.provider,
        api_mode=args.api_mode,
    )
    candidate = _evaluate(
        skill_text=load_text(args.candidate),
        reference_skill=reference,
        scenarios=scenarios,
        model=args.model,
        provider=args.provider,
        api_mode=args.api_mode,
    )
    comparison = {
        "baseline": baseline,
        "candidate": candidate,
        "delta": candidate["score"] - baseline["score"],
        "baseline_path": str(args.baseline),
        "candidate_path": str(args.candidate),
    }

    write_json_report(out_dir / "baseline_report.json", baseline)
    write_markdown_report(out_dir / "baseline_report.md", "RFD3 Binder Skill Baseline", baseline)
    write_json_report(out_dir / "comparison_report.json", comparison)
    write_markdown_report(out_dir / "comparison_report.md", "RFD3 Binder Skill Comparison", comparison)

    print(f"Baseline score:  {baseline['score']:.3f}")
    print(f"Candidate score: {candidate['score']:.3f}")
    print(f"Delta:           {comparison['delta']:.3f}")
    print(f"Reports written to {out_dir}")
    return 0


def _evaluate(*, skill_text: str, reference_skill: str, scenarios, model: str, provider: str | None, api_mode: str | None):
    transcripts = run_candidate(
        skill_text=skill_text,
        reference_skill_text=reference_skill,
        scenarios=scenarios,
        model=model,
        provider=provider,
        api_mode=api_mode,
    )
    return score_dataset(scenarios, transcripts)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--reference-skill", default=DEFAULT_REFERENCE)
    parser.add_argument("--model", default="")
    parser.add_argument("--provider")
    parser.add_argument("--api-mode")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
