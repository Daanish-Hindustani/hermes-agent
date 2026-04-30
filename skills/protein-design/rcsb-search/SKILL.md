---
name: rcsb-search
description: Use rcsb_search to find experimental protein structures, inspect metadata, identify chains/ligands, and download target structures for design.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [protein-design, rcsb, pdb, structure]
    related_skills: [uniprot-search, rfd3-design]
---

# RCSB Search

Use `rcsb_search` when the task needs an experimental structure, PDB metadata,
chain IDs, ligand context, structure download, or a target file for RFD3/MPNN.

## Workflow

1. Search by text, sequence, UniProt accession, or ligand.
2. Prefer high-resolution structures with relevant biological assemblies and
   bound ligands/cofactors when those matter for the design goal.
3. Check experimental method and resolution before trusting a structure.
4. Download structures when they will feed RFD3, ProteinMPNN, or local parsing.
5. Extract the chain IDs and residue ranges from the actual downloaded file,
   not from paper prose.

## Design Notes

- For RFD3 contigs, chain IDs and residue numbers must match the file.
- Avoid dragging unnecessary chains into design inputs; include the minimal
  target/interface context that preserves the biology.
- For ligand-aware design, keep the ligand-containing structure and record the
  ligand three-letter code.
