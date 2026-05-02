#!/usr/bin/env python3
"""Optimize the ProteinMPNN binder-design skill with GEPA."""

from __future__ import annotations

import argparse

from experiments.mpnn_binder_skill_optimization.dataset import load_scenarios
from experiments.mpnn_binder_skill_optimization.gepa_adapter import optimize_skill
from experiments.mpnn_binder_skill_optimization.hermes_runner import load_text


def main() -> int:
    args = _parse_args()
    result = optimize_skill(
        seed_skill=load_text(args.seed),
        reference_skill=load_text(args.reference_skill),
        scenarios=load_scenarios(args.dataset),
        out_dir=args.out,
        model=args.model,
        provider=args.provider,
        api_mode=args.api_mode,
    )
    print(f"Optimized candidate written to {result['candidate_path']}")
    return 0


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--reference-skill", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--provider")
    parser.add_argument("--api-mode")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

