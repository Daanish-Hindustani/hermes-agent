# RFD3 Binder Skill Optimization

This experiment uses GEPA `optimize_anything` to improve the binder-design
behavior of `skills/protein-design/rfd3-design/SKILL.md`.

The scope is intentionally narrow: **protein binders only**. The evaluator does
not reward free generation, motif scaffolding, or partial diffusion behavior.

## What GEPA Optimizes

The optimized artifact is the RFD3 skill Markdown file. GEPA receives the
current `rfd3-design/SKILL.md` as the seed candidate and tries to produce a
better candidate skill.

`protein-binder-design/SKILL.md` is passed as reference context. It is not
rewritten by this workflow.

GEPA writes candidates under `results/`, for example:

```text
experiments/rfd3_binder_skill_optimization/results/rfd3-design.binder-optimized.20260502T120000Z.SKILL.md
```

The production skill is never overwritten automatically. Review the candidate
and compare reports before promoting it.

## Required Data

The dataset lives in `data/scenarios.yaml`. Each scenario defines:

- a binder-design user prompt
- deterministic simulated tool responses
- expected tool calls and argument constraints
- failure diagnostics used as GEPA Actionable Side Information

The v1 dataset covers:

- basic binder setup
- gapped target residue numbering
- hotspot-guided binder design
- scale-up after a validated debug run
- RFD3 output chain remapping before ProteinMPNN
- safe reporting without experimental overclaims

Every scenario must explicitly forbid non-binder RFD3 modes:

```yaml
forbidden_modes: [free_generation, motif_scaffold, partial_diffusion]
```

This keeps the optimization pressure pointed at binder behavior.

## Simulated Protein-Design Tools

The evaluator runs a real Hermes/model turn, but protein-design tools are
simulated. When Hermes calls `inspect_structure`, `rfd3_design`,
`protein_mpnn_design`, `esmfold_predict`, or `alphafold2_multimer_predict`, the
evaluator records the call and returns deterministic JSON from the scenario.

This checks whether the skill makes Hermes choose the right actions and
arguments without running Docker, RFD3, ProteinMPNN, ESMFold, or AF2.

## Optimize

```bash
python scripts/optimize_rfd3_binder_skill_with_gepa.py \
  --seed skills/protein-design/rfd3-design/SKILL.md \
  --reference-skill skills/protein-design/protein-binder-design/SKILL.md \
  --dataset experiments/rfd3_binder_skill_optimization/data/scenarios.yaml \
  --out experiments/rfd3_binder_skill_optimization/results
```

Use `--model`, `--provider`, and `--api-mode` when your Hermes config does not
already select the desired evaluation model.

## Compare Before And After

```bash
python scripts/compare_rfd3_binder_skill_baseline.py \
  --baseline skills/protein-design/rfd3-design/SKILL.md \
  --candidate experiments/rfd3_binder_skill_optimization/results/<candidate>.SKILL.md \
  --dataset experiments/rfd3_binder_skill_optimization/data/scenarios.yaml \
  --out experiments/rfd3_binder_skill_optimization/results
```

Reports:

- `baseline_report.json`
- `baseline_report.md`
- `comparison_report.json`
- `comparison_report.md`

## Scoring

The evaluator scores binder-specific behavior:

- inspect target structure before target-conditioned RFD3
- use `mode: binder`
- use the binder contig pattern `<binder_length>,/0,<target_chain_range>`
- do not invent continuous residue ranges across gaps
- pass hotspots through `hotspot_residues`
- use small debug settings first when appropriate
- use exploration-scale settings after validation
- inspect generated RFD3 outputs before ProteinMPNN chain selection
- avoid claiming computational binders are experimentally validated

Failures become diagnostic feedback for GEPA.

## Manual Promotion

After GEPA writes a candidate:

1. Run the comparison script.
2. Read `comparison_report.md`.
3. Inspect the candidate skill manually.
4. Replace `skills/protein-design/rfd3-design/SKILL.md` only if the candidate
   is better and still production-safe.
5. Run the protein-design tests with `scripts/run_tests.sh`.

## Future Campaign-Spec Optimization

This v1 does not optimize live RFD3 campaign specs. A future workflow can reuse
the same structure with a different artifact, such as:

```yaml
mode: binder
contig: 70-110,/0,A1-220
hotspot_residues: [A55, A88]
guide_scale: 1.5
num_timesteps: 100
num_designs: 16
```

That future evaluator should score actual RFD3, ProteinMPNN, ESMFold, and
AF2/Multimer outputs. Keep it separate from this skill-file optimizer because
live campaign scoring is expensive and target-specific.

