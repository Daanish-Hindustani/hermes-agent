---
name: rosetta-interface-analyzer
description: Use rosetta_interface_analyzer to score designed binder-target complexes with Rosetta InterfaceAnalyzer metrics such as dG_separated and buried surface area.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [protein-design, rosetta, interface, scoring, affinity]
    related_skills: [inspect-structure, rfd3-design, protein-mpnn-design, esmfold-predict]
---

# Rosetta InterfaceAnalyzer

Use `rosetta_interface_analyzer` after a candidate binder-target complex has
been generated and sequence-designed. This tool estimates interface quality; it
does not prove experimental affinity.

The tool expects a PDB complex and a Rosetta interface string such as `A_B`,
where the left side is one partner and the right side is the other partner. For
RFD3 outputs, inspect the generated structure first because chain IDs may be
remapped: the binder is often `A`, while target segments may become `B`, `C`,
or later chains.

## Workflow

1. Use `inspect_structure` on the candidate complex.
2. Identify binder and target chain IDs.
3. Call `rosetta_interface_analyzer` with:
   - `structure_path` or `structure_paths`
   - `interface`, e.g. `A_B`
   - `output_name`
4. Rank candidates using the parsed scorefile metrics, especially
   `dG_separated`, interface buried surface area metrics, and unsatisfied polar
   metrics when present.

## Interpretation

- More negative `dG_separated` is generally better, but compare only structures
  prepared and scored the same way.
- Large buried surface area with poor energy can indicate a bad or strained
  interface.
- Rosetta scores are computational triage, not measured binding affinity.
- Keep ESMFold confidence, RFD3 geometry, ProteinMPNN diversity, and Rosetta
  interface metrics together in the candidate table.

## Practical Notes

- Use PDB inputs. Convert CIF outputs to PDB before scoring if the Rosetta
  executable in the image cannot read CIF.
- Set `compute_packstat=true` only when needed; it can make scoring slower.
- If the container uses a nonstandard executable name, pass `executable`.
