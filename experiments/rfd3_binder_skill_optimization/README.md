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

The optimization target is **Hermes's binder-design decision quality**, not
real binder performance. In v1, GEPA is optimizing whether the skill causes
Hermes to:

- inspect the target structure before target-conditioned RFD3 calls
- use `mode: binder`
- build valid binder contigs from actual chain/residue numbering
- keep hotspot residues in `hotspot_residues`, not inside `contig`
- start with small debug RFD3 runs before scaling
- scale only after inputs have been validated
- adapt the next RFD3 round based on observed failure mode
- inspect generated RFD3 outputs before downstream ProteinMPNN chain selection
- report outputs as computational candidates, not validated binders

This workflow does **not** optimize real binding affinity, wet-lab success,
RFD3 backbone quality, ProteinMPNN sequence quality, ESMFold pLDDT, or
AlphaFold2/Multimer interface confidence. Those require real model runs and
target-specific scoring, which belong in a future campaign-spec optimizer.

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

During eval, the agent's tool schema list is replaced with a strict simulated
protein-design surface:

- `pubmed_search`
- `uniprot_search`
- `rcsb_search`
- `inspect_structure`
- `rfd3_design`
- `protein_mpnn_design`
- `esmfold_predict`
- `alphafold2_multimer_predict`

This intentionally excludes unrelated tools such as `skill_view`. It also
bypasses local Docker availability checks, so the optimizer can score whether
Hermes chooses the right RFD3 calls without needing Foundry/RFD3 to be installed
or GPU-ready.

This checks whether the skill makes Hermes choose the right actions and
arguments without running Docker, RFD3, ProteinMPNN, ESMFold, or AF2.

## Optimize

```bash
python scripts/optimize_rfd3_binder_skill_with_gepa.py \
  --seed skills/protein-design/rfd3-design/SKILL.md \
  --reference-skill skills/protein-design/protein-binder-design/SKILL.md \
  --dataset experiments/rfd3_binder_skill_optimization/data/scenarios.yaml \
  --out experiments/rfd3_binder_skill_optimization/results \
  --max-metric-calls 24
```

Use `--model`, `--provider`, and `--api-mode` when your Hermes config does not
already select the desired evaluation model.

GEPA also needs a reflection/proposal model through LiteLLM. The script infers
one from `--provider` and `--model` when possible. For Gemini-backed runs, use:

```bash
python scripts/optimize_rfd3_binder_skill_with_gepa.py \
  --seed skills/protein-design/rfd3-design/SKILL.md \
  --reference-skill skills/protein-design/protein-binder-design/SKILL.md \
  --dataset experiments/rfd3_binder_skill_optimization/data/scenarios.yaml \
  --out experiments/rfd3_binder_skill_optimization/results \
  --max-metric-calls 24 \
  --provider google \
  --model gemini-2.5-flash \
  --reflection-lm gemini/gemini-2.5-flash
```

If LiteLLM cannot find Gemini credentials, mirror the key name used on the host:

```bash
export GEMINI_API_KEY="$GOOGLE_API_KEY"
# or
export GOOGLE_API_KEY="$GEMINI_API_KEY"
```

## Compare Before And After

```bash
python scripts/compare_rfd3_binder_skill_baseline.py \
  --baseline skills/protein-design/rfd3-design/SKILL.md \
  --candidate experiments/rfd3_binder_skill_optimization/results/<candidate>.SKILL.md \
  --dataset experiments/rfd3_binder_skill_optimization/data/scenarios.yaml \
  --out experiments/rfd3_binder_skill_optimization/results \
  --provider google \
  --model gemini-2.5-flash
```

Reports:

- `baseline_report.json`
- `baseline_report.md`
- `comparison_report.json`
- `comparison_report.md`

## Scoring

The evaluator scores tool-call transcripts from real Hermes/model turns. Each
scenario has expectations in `data/scenarios.yaml`; the scorer converts the
observed transcript into a numeric score and logs failures as feedback for GEPA.

The score answers:

```text
Did this candidate skill make Hermes choose the right binder-design workflow,
tool calls, arguments, and safety language?
```

It does not answer:

```text
Did RFD3 produce a physically good binder?
```

Scored checks include:

- inspect target structure before target-conditioned RFD3
- use `mode: binder`
- use the binder contig pattern `<binder_length>,/0,<target_chain_range>`
- do not invent continuous residue ranges across gaps
- pass hotspots through `hotspot_residues`
- use small debug settings first when appropriate
- use exploration-scale settings after validation
- inspect generated RFD3 outputs before ProteinMPNN chain selection
- avoid claiming computational binders are experimentally validated

Examples of passing behavior:

```json
{
  "name": "rfd3_design",
  "args": {
    "mode": "binder",
    "contig": "70-110,/0,A1-220",
    "target_pdb_path": "target.cif",
    "hotspot_residues": ["A55", "A88"],
    "num_designs": 2,
    "num_timesteps": 25
  }
}
```

Examples of failing behavior:

- calling `rfd3_design` before inspecting an unknown target structure
- using `mode: free_generation`, `motif_scaffold`, or `partial_diffusion`
- writing hotspots into the contig instead of `hotspot_residues`
- using a continuous range like `A1-160` when inspection shows a gap
- starting with a large production batch before a debug/validation run
- telling ProteinMPNN to design a chain before inspecting RFD3 chain remapping
- calling the result a "validated binder" without experimental data

Each failed check becomes diagnostic feedback for GEPA. For example:

```text
Target structure was not inspected before rfd3_design.
Contig used forbidden range: A1-160.
Hotspots must be passed via hotspot_residues.
```

GEPA prints optimization scores during the run. A small improvement is enough
to produce a candidate, but it is not enough to auto-promote the skill. Always
compare the candidate and inspect the generated Markdown before replacing the
production skill.

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
