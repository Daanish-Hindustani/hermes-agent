---
name: esmfold-predict
description: Use esmfold_predict to fold designed or natural sequences locally with ESMFold and interpret pLDDT confidence.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [protein-design, esmfold, folding, validation]
    related_skills: [protein-mpnn-design, uniprot-search]
---

# ESMFold Predict

Use `esmfold_predict` to locally fold amino-acid sequences and triage designed
proteins before deeper validation.

## Workflow

1. Fold designed sequences after ProteinMPNN.
2. Use `num_recycles=4` by default; increase when the structure is large or
   borderline and runtime is acceptable.
3. Use `chunk_size` or `cpu_offload` for memory pressure.
4. Inspect mean pLDDT and local low-confidence regions.
5. Reject or redesign candidates with poor global confidence, broken topology,
   or low-confidence interface/motif regions.

## Interpretation

- pLDDT is stored in the PDB B-factor field.
- High pLDDT does not prove binding, catalysis, expression, or stability.
- Low confidence at flexible termini may be acceptable; low confidence in the
  designed core, active site, or binding interface is a serious warning.
