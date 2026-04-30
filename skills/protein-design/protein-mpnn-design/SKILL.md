---
name: protein-mpnn-design
description: Use protein_mpnn_design for fixed-backbone sequence design after RFD3 or with existing structures.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [protein-design, proteinmpnn, ligandmpnn, sequence-design]
    related_skills: [rfd3-design, esmfold-predict]
---

# ProteinMPNN Design

Use `protein_mpnn_design` to design amino-acid sequences for fixed protein
backbones. It is typically run after RFD3 generates candidate backbones.

## Workflow

1. Start from a valid PDB/CIF backbone.
2. Choose `model_type`:
   - `protein_mpnn` for protein-only fixed-backbone design.
   - `ligand_mpnn` when ligand, ion, DNA/RNA, or other atom context matters.
   - `soluble_mpnn` when soluble expression is a priority.
3. Set `designed_chains` when only some chains should change.
4. Set `fixed_positions` when catalytic/interface residues must remain fixed.
5. Generate multiple sequences and keep diversity.
6. Validate outputs with `esmfold_predict`.

## Temperature Guidance

- `0.05-0.1`: conservative, higher confidence, less diverse.
- `0.2-0.3`: more diverse, useful after initial candidates pass validation.
- Avoid presenting high-scoring sequences as experimentally validated.
