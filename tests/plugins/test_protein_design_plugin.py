import json
import sys
from pathlib import Path

import yaml

from hermes_cli.plugins import PluginManager, PluginManifest


PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins" / "protein-design"
SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "protein-design"


def _load_plugin_modules():
    manifest = PluginManifest(
        name="protein-design",
        source="bundled",
        path=str(PLUGIN_DIR),
        key="protein-design",
    )
    mgr = PluginManager()
    mgr._load_plugin(manifest)
    return sys.modules["hermes_plugins.protein_design.tools"], mgr


def _write_pdb(path: Path):
    lines = []
    atom_id = 1
    for chain, residues in {"A": range(1, 6), "B": range(10, 13)}.items():
        for resi in residues:
            lines.append(
                f"ATOM  {atom_id:5d}  CA  ALA {chain}{resi:4d}    "
                f"{0.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           C\n"
            )
            atom_id += 1
    path.write_text("".join(lines), encoding="utf-8")


def test_plugin_registers_all_tools():
    _, mgr = _load_plugin_modules()
    loaded = mgr._plugins["protein-design"]
    assert loaded.enabled is True
    assert set(loaded.tools_registered) >= {
        "pubmed_search",
        "uniprot_search",
        "rcsb_search",
        "rfd3_design",
        "protein_mpnn_design",
        "esmfold_predict",
    }


def test_rfd3_contig_validation_accepts_binder_and_motif(tmp_path):
    tools, _ = _load_plugin_modules()
    pdb = tmp_path / "target.pdb"
    _write_pdb(pdb)

    assert tools.validate_rfd3_contig(
        mode="binder",
        contig="70-110,/0,A1-5",
        target_pdb_path=str(pdb),
        hotspot_residues=["A2", "A3-4"],
    ) == []

    assert tools.validate_rfd3_contig(
        mode="motif_scaffold",
        contig="30-50,A2-4,40-70",
        target_pdb_path=str(pdb),
        hotspot_residues=[],
    ) == []


def test_rfd3_contig_validation_rejects_bad_chain_and_range(tmp_path):
    tools, _ = _load_plugin_modules()
    pdb = tmp_path / "target.pdb"
    _write_pdb(pdb)

    errors = tools.validate_rfd3_contig(
        mode="binder",
        contig="70-110,/0,C1-5",
        target_pdb_path=str(pdb),
        hotspot_residues=["A99"],
    )

    assert any("missing chain C" in err for err in errors)
    assert any("missing residues" in err for err in errors)


def test_rfd3_free_generation_uses_bare_lengths():
    tools, _ = _load_plugin_modules()
    assert tools.validate_rfd3_contig(
        mode="free_generation",
        contig="80-120",
        target_pdb_path="",
        hotspot_residues=[],
    ) == []
    assert tools.validate_rfd3_contig(
        mode="free_generation",
        contig="A1-20,80",
        target_pdb_path="",
        hotspot_residues=[],
    )


def test_rfd3_argument_translation():
    tools, _ = _load_plugin_modules()
    command = tools.build_rfd3_docker_args(
        input_path="/work/in.json",
        out_dir="/work/out",
        output_name="run1",
        num_designs=12,
        guide_scale=2.0,
        num_timesteps=50,
    )
    assert "diffusion_batch_size=12" in command
    assert "inference_sampler.step_scale=2.0" in command
    assert "inference_sampler.num_timesteps=50" in command
    assert "prevalidate_inputs=True" in command
    assert "global_prefix=run1" in command


def test_pubmed_query_variants_are_multi_query():
    tools, _ = _load_plugin_modules()
    clients = sys.modules["hermes_plugins.protein_design.clients"]
    variants = clients.build_pubmed_query_variants("KRAS binder", article_types=["Review"])
    assert len(variants) >= 5
    assert any("review[Publication Type]" in variant for variant in variants)
    assert any('"KRAS binder"' == variant for variant in variants)


def test_rcsb_empty_response_returns_empty_results(monkeypatch):
    _tools, _ = _load_plugin_modules()
    clients = sys.modules["hermes_plugins.protein_design.clients"]

    monkeypatch.setattr(clients, "_get_json", lambda *args, **kwargs: {})

    result = clients.search_rcsb("ZFC3H1 no matching structure", max_results=5)

    assert result["results"] == []


def test_esmfold_payload_includes_num_recycles():
    tools, _ = _load_plugin_modules()
    payload = tools.build_esmfold_input_payload(
        {"num_recycles": 8, "chunk_size": 64, "max_tokens_per_batch": 1024},
        sequence=None,
        fasta_container_path="/work/in.fasta",
        output_container_dir="/work/out",
    )
    assert payload["fasta_path"] == "/work/in.fasta"
    assert payload["output_dir"] == "/work/out"
    assert payload["num_recycles"] == 8
    assert payload["chunk_size"] == 64


def test_esmfold_requires_sequence_or_fasta():
    tools, _ = _load_plugin_modules()
    result = json.loads(tools.handle_esmfold_predict({"output_name": "empty"}))

    assert result["success"] is False
    assert "sequence or fasta_path" in result["error"]


def test_each_tool_has_associated_skill_with_valid_frontmatter():
    expected = {
        "protein-binder-design",
        "pubmed-search",
        "uniprot-search",
        "rcsb-search",
        "rfd3-design",
        "protein-mpnn-design",
        "esmfold-predict",
    }
    found = {path.parent.name for path in SKILL_DIR.glob("*/SKILL.md")}
    assert expected <= found

    for skill_file in SKILL_DIR.glob("*/SKILL.md"):
        content = skill_file.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        _, frontmatter, body = content.split("---", 2)
        parsed = yaml.safe_load(frontmatter)
        assert parsed["name"] == skill_file.parent.name
        assert parsed["description"]
        assert body.strip()
