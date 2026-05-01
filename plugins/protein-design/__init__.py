"""Protein design plugin for Hermes.

The plugin keeps domain tools out of Hermes core while exposing a single
`protein_design` toolset for literature, target lookup, backbone generation,
sequence design, and folding validation.
"""

from __future__ import annotations

from .schemas import (
    ESMFOLD_PREDICT_SCHEMA,
    INSPECT_STRUCTURE_SCHEMA,
    PROTEIN_MPNN_DESIGN_SCHEMA,
    PUBMED_SEARCH_SCHEMA,
    RCSB_SEARCH_SCHEMA,
    RFD3_DESIGN_SCHEMA,
    ROSETTA_INTERFACE_ANALYZER_SCHEMA,
    UNIPROT_SEARCH_SCHEMA,
)
from .tools import (
    check_docker_requirements,
    handle_esmfold_predict,
    handle_inspect_structure,
    handle_protein_mpnn_design,
    handle_pubmed_search,
    handle_rcsb_search,
    handle_rfd3_design,
    handle_rosetta_interface_analyzer,
    handle_uniprot_search,
)


_TOOLS = (
    ("pubmed_search", PUBMED_SEARCH_SCHEMA, handle_pubmed_search, None, "📚"),
    ("uniprot_search", UNIPROT_SEARCH_SCHEMA, handle_uniprot_search, None, "🧬"),
    ("rcsb_search", RCSB_SEARCH_SCHEMA, handle_rcsb_search, None, "🏛️"),
    ("inspect_structure", INSPECT_STRUCTURE_SCHEMA, handle_inspect_structure, None, "🔍"),
    ("rfd3_design", RFD3_DESIGN_SCHEMA, handle_rfd3_design, check_docker_requirements, "🧪"),
    ("protein_mpnn_design", PROTEIN_MPNN_DESIGN_SCHEMA, handle_protein_mpnn_design, check_docker_requirements, "🔬"),
    ("rosetta_interface_analyzer", ROSETTA_INTERFACE_ANALYZER_SCHEMA, handle_rosetta_interface_analyzer, check_docker_requirements, "⚖️"),
    ("esmfold_predict", ESMFOLD_PREDICT_SCHEMA, handle_esmfold_predict, check_docker_requirements, "🧫"),
)


def register(ctx) -> None:
    """Register protein design tools under the `protein_design` toolset."""
    for name, schema, handler, check_fn, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="protein_design",
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            emoji=emoji,
        )
