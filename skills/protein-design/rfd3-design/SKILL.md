---
name: rfd3-design
description: Use rfd3_design for RFdiffusion3 backbone generation, including binder, motif scaffold, partial diffusion, free generation, hotspots, and contig construction.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [protein-design, rfd3, rfdiffusion3, backbone, contigs]
    related_skills: [rcsb-search, protein-mpnn-design]
---

# RFdiffusion3 Design

Use `rfd3_design` for RFdiffusion3 backbone generation. RFD3 is powerful but
contigs are easy to get wrong; inspect the target structure before designing.

## Tool Inputs

`rfd3_design` accepts:

- `mode`: `free_generation`, `binder`, `motif_scaffold`, or `partial_diffusion`
- `input_path`: optional existing RFD3 JSON/YAML spec
- `output_name`
- `num_designs`
- `contig`
- `target_pdb_path`
- `hotspot_residues`
- `guide_scale`
- `num_timesteps`

## Contig Derivation Order

1. Identify the mode.
   - `free_generation`: no target; contig is a designed length like `80-120`.
   - `binder`: target is fixed; designed binder chain is placed before or after `/0`.
   - `motif_scaffold`: motif residues are fixed inside a designed scaffold.
   - `partial_diffusion`: start from an input structure and perturb/redesign selected regions.

2. Inspect the target structure before building a contig.
   - Use `rcsb_search` or local file parsing to identify chains, residue
     numbering, missing residues, ligands, and target chain IDs.
   - Confirm residue identifiers match the actual file, not paper numbering.

3. Binder design.
   - Keep the target chain fixed after a chain break.
   - Pattern: `<binder_length>,/0,<target_chain_start-end>`.
   - Example: `70-110,/0,A1-240`.
   - Put hotspots in `hotspot_residues`, not inside `contig`.

4. Motif scaffolding.
   - Place fixed motif residues in the contig and surround them with designed
     segments.
   - Example: `30-50,A45-52,40-70`.
   - Use `/0` only for an intended chain break.

5. Multi-chain or target plus ligand contexts.
   - Preserve chain breaks explicitly with `/0`.
   - Include only chains/ranges needed for conditioning.
   - Do not include the whole biological assembly unless necessary.

6. Validate before running.
   - Every chain/range in `contig` and `hotspot_residues` must exist in
     `target_pdb_path`.
   - Designed segments use bare lengths/ranges with no chain letter.
   - Fixed target/motif residues use chain-prefixed residue ranges.
   - The tool runs RFD3 with `prevalidate_inputs=True`.

## Parameter Guidance

- `num_designs`: start small, such as 8-32, before scaling.
- `guide_scale`: defaults around 1.5; higher can improve designability but may
  reduce diversity.
- `num_timesteps`: default 200; lower is faster for debugging.
- After RFD3, use `protein_mpnn_design` to design sequences and
  `esmfold_predict` to triage foldability.
