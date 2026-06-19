"""Tests for Phase 12.1 modeling draft demo pure helpers.

Covers: quality check aggregators, duplicate detection, noise indicators.
Does NOT test API, permissions, scan, or generation main logic.
"""

from scripts.run_ontology_modeling_demo import (
    count_duplicate_type_names,
    count_empty_evidence,
    count_missing_generation_keys,
    count_missing_source_pointers,
    count_properties_per_object_type,
    count_single_entity_properties,
    count_single_issue_actions,
    count_single_relation_links,
)


def _d(draft_type, name, payload=None, source_entity_id=None,
       source_relation_id=None, source_issue_id=None,
       evidence_refs=None):
    return {
        "draft_type": draft_type,
        "name": name,
        "payload": payload or {},
        "source_entity_id": source_entity_id,
        "source_relation_id": source_relation_id,
        "source_issue_id": source_issue_id,
        "source_rag_run_id": None,
        "evidence_refs": evidence_refs or [],
    }


class TestMissingGenerationKeys:
    def test_all_have_keys(self):
        drafts = [
            _d("object_type", "OT1", payload={"generation_key": "k1"}),
            _d("property", "P1", payload={"generation_key": "k2"}),
        ]
        assert count_missing_generation_keys(drafts) == 0

    def test_some_missing(self):
        drafts = [
            _d("object_type", "OT1", payload={"generation_key": "k1"}),
            _d("property", "P1", payload={}),
            _d("link_type", "L1", payload={"other": "x"}),
        ]
        assert count_missing_generation_keys(drafts) == 2


class TestMissingSourcePointers:
    def test_all_have_source(self):
        drafts = [
            _d("object_type", "OT1", source_entity_id="e1"),
            _d("link_type", "L1", source_relation_id="r1"),
            _d("action_type", "A1", source_issue_id="i1"),
        ]
        assert count_missing_source_pointers(drafts) == 0

    def test_some_missing(self):
        drafts = [
            _d("object_type", "OT1", source_entity_id="e1"),
            _d("object_type", "OT2"),
        ]
        assert count_missing_source_pointers(drafts) == 1


class TestEmptyEvidence:
    def test_all_have_evidence(self):
        drafts = [
            _d("object_type", "OT1", evidence_refs=[{"id": "x"}]),
            _d("property", "P1", evidence_refs=[{"id": "y"}]),
        ]
        assert count_empty_evidence(drafts) == 0

    def test_empty_list_evidence(self):
        drafts = [_d("object_type", "OT1", evidence_refs=[])]
        assert count_empty_evidence(drafts) == 1


class TestDuplicateTypeNames:
    def test_no_duplicates(self):
        drafts = [
            _d("object_type", "Concept"),
            _d("object_type", "Vendor"),
            _d("property", "Concept.tags"),
        ]
        assert count_duplicate_type_names(drafts) == 0

    def test_exact_duplicate(self):
        drafts = [
            _d("object_type", "Concept"),
            _d("object_type", "Concept"),
        ]
        assert count_duplicate_type_names(drafts) == 1

    def test_casefold_duplicate(self):
        drafts = [
            _d("object_type", "Concept"),
            _d("object_type", "concept"),
        ]
        assert count_duplicate_type_names(drafts) == 1


class TestNoiseIndicators:
    def test_single_entity_properties(self):
        drafts = [
            _d("property", "P1", payload={"entity_count": 1}),
            _d("property", "P2", payload={"entity_count": 5}),
            _d("object_type", "OT1"),
        ]
        assert count_single_entity_properties(drafts) == 1

    def test_single_relation_links(self):
        drafts = [
            _d("link_type", "L1", payload={"relation_count": 1}),
            _d("link_type", "L2", payload={"relation_count": 3}),
        ]
        assert count_single_relation_links(drafts) == 1

    def test_single_issue_actions(self):
        drafts = [
            _d("action_type", "A1", payload={"issue_count": 1}),
            _d("action_type", "A2", payload={"issue_count": 2}),
        ]
        assert count_single_issue_actions(drafts) == 1

    def test_properties_per_object_type(self):
        drafts = [
            _d("property", "P1", payload={"object_type": "Concept"}),
            _d("property", "P2", payload={"object_type": "Concept"}),
            _d("property", "P3", payload={"object_type": "Vendor"}),
            _d("link_type", "L1"),
        ]
        result = count_properties_per_object_type(drafts)
        assert result == {"Concept": 2, "Vendor": 1}
