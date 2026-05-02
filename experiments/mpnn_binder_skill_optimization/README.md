# ProteinMPNN Binder Skill Optimization

This experiment uses GEPA `optimize_anything` to improve
`skills/protein-design/protein-mpnn-design/SKILL.md` for binder sequence-design
decisions after RFD3.

The optimized artifact is the ProteinMPNN skill Markdown file. The
`protein-binder-design` workflow skill is reference context only.

## What We Optimize For

The evaluator scores whether Hermes makes good ProteinMPNN decisions in binder
campaigns:

- choose the correct RFD3-generated backbone input
- inspect generated structures before chain-sensitive design
- set `designed_chains` to the binder chain, not the target chain
- use batch inputs for multiple RFD3 backbones
- use `protein_mpnn` for protein-only contexts
- use `ligand_mpnn` when ligand, ion, cofactor, DNA/RNA, or non-protein atom
  context matters
- start near `temperature=0.1`
- use `temperature=0.2-0.3` only for diversity follow-up
- pass `fixed_positions` when residues must remain unchanged
- follow ProteinMPNN with ESMFold foldability triage
- avoid claiming computational sequences are validated binders

`ligand_mpnn` is not a separate Hermes tool. It is a `model_type` value passed
to `protein_mpnn_design`.

## Simulated Tools

The optimizer runs real Hermes/model turns, but protein-design tools are
simulated. Tool calls are recorded and deterministic JSON responses are returned
from `data/scenarios.yaml`.

No Docker, RFD3, ProteinMPNN, ESMFold, or AlphaFold2 jobs run during this
optimization workflow.

## Optimize

```bash
python scripts/optimize_mpnn_binder_skill_with_gepa.py \
  --seed skills/protein-design/protein-mpnn-design/SKILL.md \
  --reference-skill skills/protein-design/protein-binder-design/SKILL.md \
  --dataset experiments/mpnn_binder_skill_optimization/data/scenarios.yaml \
  --out experiments/mpnn_binder_skill_optimization/results
```

Use `--model`, `--provider`, and `--api-mode` if your Hermes config does not
already select the desired evaluation model.

## Compare Before And After

```bash
python scripts/compare_mpnn_binder_skill_baseline.py \
  --baseline skills/protein-design/protein-mpnn-design/SKILL.md \
  --candidate experiments/mpnn_binder_skill_optimization/results/<candidate>.SKILL.md \
  --dataset experiments/mpnn_binder_skill_optimization/data/scenarios.yaml \
  --out experiments/mpnn_binder_skill_optimization/results
```

Reports:

- `baseline_report.json`
- `baseline_report.md`
- `comparison_report.json`
- `comparison_report.md`

## Manual Promotion

GEPA writes candidate skills under `results/`; it never overwrites the
production skill automatically.

Before promotion:

1. Run the comparison script.
2. Read `comparison_report.md`.
3. Review the candidate skill manually.
4. Replace `skills/protein-design/protein-mpnn-design/SKILL.md` only when the
   candidate improves binder behavior without unsafe claims.
5. Run the targeted test suite through `scripts/run_tests.sh`.

