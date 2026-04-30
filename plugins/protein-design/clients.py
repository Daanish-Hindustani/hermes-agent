"""HTTP clients for protein-design knowledge sources."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx


PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA_ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
RCSB_CIF_URL = "https://files.rcsb.org/download/{pdb_id}.cif"


def _get_json(url: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _get_text(url: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> str:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.text


def build_pubmed_query_variants(
    query: str,
    *,
    date_range: str = "",
    article_types: list[str] | None = None,
) -> list[str]:
    base = " ".join(query.split())
    variants = [
        base,
        f'"{base}"',
        f"({base}) AND review[Publication Type]",
        f"({base}) AND protein design",
        f"({base}) AND structure OR binding OR enzyme",
    ]
    if date_range:
        variants = [f"({v}) AND {date_range}" for v in variants]
    for article_type in article_types or []:
        clean = str(article_type).strip()
        if clean:
            variants.append(f"({base}) AND {clean}[Publication Type]")
    deduped: list[str] = []
    for item in variants:
        if item not in deduped:
            deduped.append(item)
    return deduped


def search_pubmed(
    query: str,
    *,
    max_results: int = 20,
    date_range: str = "",
    article_types: list[str] | None = None,
    query_variations: bool = True,
) -> dict[str, Any]:
    variants = (
        build_pubmed_query_variants(query, date_range=date_range, article_types=article_types)
        if query_variations
        else [query]
    )
    api_key = os.getenv("NCBI_API_KEY") or os.getenv("HERMES_PROTEIN_NCBI_API_KEY")
    email = os.getenv("NCBI_TOOL_EMAIL") or os.getenv("HERMES_PROTEIN_NCBI_EMAIL")
    ids: list[str] = []
    seen: set[str] = set()
    per_query: list[dict[str, Any]] = []

    for variant in variants:
        params = {
            "db": "pubmed",
            "term": variant,
            "retmode": "json",
            "retmax": max(1, min(max_results, 100)),
            "sort": "relevance",
        }
        if api_key:
            params["api_key"] = api_key
        if email:
            params["email"] = email
        data = _get_json(f"{PUBMED_BASE}/esearch.fcgi", params=params)
        found = data.get("esearchresult", {}).get("idlist", []) or []
        per_query.append({"query": variant, "count": len(found)})
        for pmid in found:
            if pmid not in seen:
                seen.add(pmid)
                ids.append(pmid)
            if len(ids) >= max_results:
                break
        if len(ids) >= max_results:
            break

    papers = fetch_pubmed_records(ids)
    return {"query": query, "query_variants": variants, "per_query": per_query, "results": papers}


def fetch_pubmed_records(pmids: list[str]) -> list[dict[str, Any]]:
    if not pmids:
        return []
    xml_text = _get_text(
        f"{PUBMED_BASE}/efetch.fcgi",
        params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
    )
    root = ET.fromstring(xml_text)
    results: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        article_node = medline.find("Article") if medline is not None else None
        pmid = (medline.findtext("PMID") if medline is not None else "") or ""
        title = "".join(article_node.findtext("ArticleTitle") or "").strip() if article_node is not None else ""
        abstract = " ".join(
            " ".join(node.itertext()).strip()
            for node in article.findall(".//AbstractText")
            if " ".join(node.itertext()).strip()
        )
        authors = []
        for author in article.findall(".//Author"):
            last = author.findtext("LastName") or ""
            initials = author.findtext("Initials") or ""
            collective = author.findtext("CollectiveName") or ""
            name = collective or " ".join(part for part in (last, initials) if part)
            if name:
                authors.append(name)
        doi = ""
        for aid in article.findall(".//ArticleId"):
            if aid.attrib.get("IdType") == "doi":
                doi = aid.text or ""
                break
        journal = article.findtext(".//Journal/Title") or article.findtext(".//ISOAbbreviation") or ""
        year = article.findtext(".//PubDate/Year") or ""
        mesh_terms = [mh.findtext("DescriptorName") for mh in article.findall(".//MeshHeading")]
        results.append({
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "journal": journal,
            "year": year,
            "doi": doi,
            "mesh_terms": [m for m in mesh_terms if m],
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        })
    return results


def search_uniprot(
    query: str,
    *,
    organism_id: str = "",
    gene: str = "",
    reviewed_only: bool = True,
    max_results: int = 25,
    include_sequence: bool = True,
) -> dict[str, Any]:
    clauses = [f"({query})"]
    if organism_id:
        clauses.append(f"(organism_id:{organism_id})")
    if gene:
        clauses.append(f"(gene:{gene})")
    if reviewed_only:
        clauses.append("(reviewed:true)")
    fields = [
        "accession", "id", "protein_name", "gene_names", "organism_name",
        "length", "cc_function", "ft_domain", "xref_pdb",
    ]
    if include_sequence:
        fields.append("sequence")
    params = {
        "query": " AND ".join(clauses),
        "format": "json",
        "fields": ",".join(fields),
        "size": max(1, min(max_results, 100)),
    }
    data = _get_json(UNIPROT_SEARCH_URL, params=params)
    return {
        "query": query,
        "results": [normalize_uniprot_entry(item) for item in data.get("results", [])],
    }


def normalize_uniprot_entry(item: dict[str, Any]) -> dict[str, Any]:
    genes = []
    for gene in item.get("genes", []) or []:
        name = (gene.get("geneName") or {}).get("value")
        if name:
            genes.append(name)
    comments = []
    for comment in item.get("comments", []) or []:
        if comment.get("commentType") == "FUNCTION":
            texts = [t.get("value", "") for t in comment.get("texts", [])]
            comments.extend(t for t in texts if t)
    features = [
        {
            "type": f.get("type"),
            "description": f.get("description"),
            "location": f.get("location"),
        }
        for f in item.get("features", []) or []
    ]
    pdb_refs = [
        x.get("id")
        for x in item.get("uniProtKBCrossReferences", []) or []
        if x.get("database") == "PDB" and x.get("id")
    ]
    return {
        "accession": item.get("primaryAccession"),
        "id": item.get("uniProtkbId"),
        "protein_name": (((item.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName") or {}).get("value"),
        "genes": genes,
        "organism": (item.get("organism") or {}).get("scientificName"),
        "length": (item.get("sequence") or {}).get("length"),
        "sequence": (item.get("sequence") or {}).get("value"),
        "function": " ".join(comments),
        "features": features,
        "pdb_refs": pdb_refs,
    }


def search_rcsb(
    query: str,
    *,
    search_type: str = "text",
    max_results: int = 25,
    return_type: str = "entry",
    download: bool = False,
    output_dir: str = "",
) -> dict[str, Any]:
    payload = build_rcsb_query(query, search_type=search_type, return_type=return_type, max_results=max_results)
    data = _get_json(RCSB_SEARCH_URL, params={"json": json.dumps(payload)})
    identifiers = [item.get("identifier") for item in data.get("result_set", []) if item.get("identifier")]
    entries = []
    for ident in identifiers[:max_results]:
        pdb_id = ident.split("_")[0].split(".")[0].split("-")[0].upper()
        entry = {"identifier": ident, "pdb_id": pdb_id}
        try:
            meta = _get_json(RCSB_DATA_ENTRY_URL.format(pdb_id=pdb_id))
            entry.update(normalize_rcsb_entry(meta))
        except Exception as exc:
            entry["metadata_error"] = str(exc)
        if download:
            target_dir = Path(output_dir or "protein_design_rcsb").expanduser().resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            cif_path = target_dir / f"{pdb_id}.cif"
            cif_path.write_text(_get_text(RCSB_CIF_URL.format(pdb_id=pdb_id)), encoding="utf-8")
            entry["local_path"] = str(cif_path)
        entries.append(entry)
    return {"query": query, "search_type": search_type, "results": entries}


def build_rcsb_query(query: str, *, search_type: str, return_type: str, max_results: int) -> dict[str, Any]:
    if search_type == "sequence":
        node = {
            "type": "terminal",
            "service": "sequence",
            "parameters": {
                "evalue_cutoff": 1,
                "identity_cutoff": 0.3,
                "sequence_type": "protein",
                "value": query,
            },
        }
    elif search_type == "uniprot":
        node = {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                "operator": "exact_match",
                "value": query,
            },
        }
    elif search_type == "ligand":
        node = {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id",
                "operator": "exact_match",
                "value": query.upper(),
            },
        }
    else:
        node = {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": query},
        }
    return {
        "query": node,
        "return_type": return_type,
        "request_options": {"paginate": {"start": 0, "rows": max(1, min(max_results, 100))}},
    }


def normalize_rcsb_entry(meta: dict[str, Any]) -> dict[str, Any]:
    citation = (meta.get("citation") or [{}])[0]
    methods = [m.get("method") for m in meta.get("exptl", []) or [] if m.get("method")]
    resolution = None
    for refine in meta.get("refine", []) or []:
        if refine.get("ls_d_res_high") is not None:
            resolution = refine.get("ls_d_res_high")
            break
    return {
        "title": (meta.get("struct") or {}).get("title"),
        "experimental_methods": methods,
        "resolution": resolution,
        "release_date": ((meta.get("rcsb_accession_info") or {}).get("initial_release_date")),
        "doi": citation.get("pdbx_database_id_DOI"),
        "pubmed_id": citation.get("pdbx_database_id_PubMed"),
    }


_PDB_ATOM_RE = re.compile(r"^(ATOM  |HETATM).{15}(.).{4}([A-Za-z0-9 ])(.{4})")


def parse_pdb_residues(path: Path) -> dict[str, set[int]]:
    """Parse chain/residue IDs from legacy PDB ATOM/HETATM records."""
    residues: dict[str, set[int]] = {}
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            chain = (line[21].strip() or "_")
            try:
                resi = int(line[22:26].strip())
            except ValueError:
                continue
            residues.setdefault(chain, set()).add(resi)
    return residues
