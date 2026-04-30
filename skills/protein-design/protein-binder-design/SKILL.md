---
name: protein-binder-design
description: Use for end-to-end protein binder design planning across literature, target lookup, structure selection, RFD3 backbone generation, ProteinMPNN sequence design, and ESMFold validation.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [protein-design, binder-design, rfd3, proteinmpnn, esmfold]
    related_skills: [pubmed-search, uniprot-search, rcsb-search, rfd3-design, protein-mpnn-design, esmfold-predict]
---

# Protein Binder Design

Use this skill when the user wants to design a protein binder against a target
protein, domain, epitope, receptor, antigen, enzyme, or protein complex.

This is a workflow skill, not a tool wrapper. The tools are independent. Choose
only the steps needed for the task; do not run the whole pipeline blindly.

## Binder Design Workflow

1. Clarify the design objective.
   - Target protein and organism
   - Desired binding region, epitope, ligand pocket, or interface
   - Constraints: binder length, oligomeric state, disulfides, forbidden motifs,
     expression host, and whether wet-lab validation is planned

2. Gather evidence with `pubmed_search` when biology or precedent is unclear.
   - Look for known binders, complexes, epitopes, mutational scans, domain
     boundaries, and interface structures.
   - Prefer papers with direct structural or biochemical evidence.

3. Resolve the target with `uniprot_search`.
   - Get canonical sequence, domain boundaries, isoforms, features, and PDB refs.
   - Scope by organism ID when the target exists across species.

4. Select a structure with `rcsb_search`.
   - Prefer relevant experimental structures with good resolution and the right
     biological assembly.
   - Identify the actual chain IDs and residue numbering in the downloaded file.
   - Keep ligand/cofactor/context chains when they define the binding site.

5. Build the RFD3 binder contig.
   - Inspect the target file before writing the contig.
   - Use the binder pattern: `<binder_length>,/0,<target_chain_start-end>`.
   - Example: `70-110,/0,A1-240`.
   - Put epitope/interface residues in `hotspot_residues`, not in the contig.
   - Include only target chains/ranges needed for binding context.

6. Run `rfd3_design` for backbone generation.
   - Start with `num_designs=1-8` and lower `num_timesteps` for debugging.
   - Scale only after the input spec passes validation.

7. Run `protein_mpnn_design` on promising backbones.
   - Use `ligand_mpnn` if ligand, ion, DNA/RNA, or atom context matters.
   - Fix residues that must remain unchanged.
   - Sample multiple sequences for each backbone.

8. Run `esmfold_predict` for sequence-level triage.
   - Start with `num_recycles=4`.
   - Reject candidates with low-confidence cores, broken topology, or weak
     confidence in the interface/motif region.

## Tool Independence Rule

Do not assume one tool automatically calls the next. The agent must decide and
call each tool explicitly:

- `pubmed_search` does not call UniProt, RCSB, RFD3, MPNN, or ESMFold.
- `uniprot_search` does not call RCSB or download structures.
- `rcsb_search` can optionally download structures, but it does not run RFD3.
- `rfd3_design` generates backbones only; it does not design sequences.
- `protein_mpnn_design` designs sequences only; it does not fold them.
- `esmfold_predict` folds sequences only; it does not redesign failed candidates.

This separation is deliberate. It keeps each tool testable and lets the user run
partial workflows without paying for unnecessary compute.

## Reporting

When summarizing binder-design results, separate:

- Evidence from literature
- Target/structure assumptions
- RFD3 backbone generation status
- ProteinMPNN sequence design status
- ESMFold confidence
- Remaining experimental or computational validation needed

Never describe a computational binder as experimentally validated unless the user
provided real experimental data proving it.
