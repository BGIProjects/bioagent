from __future__ import annotations

from xvirmind.mcp.annotation_server import capability as ann_cap
from xvirmind.mcp.annotation_server import list_families
from xvirmind.mcp.taxonomy_server import capability, family_info, search_kb


def test_taxonomy_capability_lists_families():
    data = capability({})
    assert data["capability_id"] == "virus_taxonomy.classify"
    assert "Coronaviridae" in data["families"]
    assert data["kb_records"] > 0


def test_taxonomy_family_info_has_citation():
    data = family_info({"family_name": "Coronaviridae"})
    assert data["status"] == "ok"
    assert data["knowledge_release"].endswith("kb.jsonl")
    assert data["family_name"] == "Coronaviridae"


def test_taxonomy_search_empty_is_insufficient():
    data = search_kb({"query": "NotARealVirusidae999"})
    assert data["status"] == "KNOWLEDGE_INSUFFICIENT"


def test_annotation_families():
    data = ann_cap({})
    assert data["family_count"] >= 10
    listed = list_families({"query": "Flavi"})
    assert "Flaviviridae" in listed["families"]
