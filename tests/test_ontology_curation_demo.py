"""Tests for Phase 10.2 curation demo helpers.

Tests pure functions for triage classification, priority calculation,
and backlog aggregation. Does NOT read F:\\ontology-kb\\knowledge-graph.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_ontology_curation_demo import (
    KB_ENTITY_DIRS,
    aggregate_backlog,
    calculate_priority,
    classify_unresolved_wikilink,
    determine_action_type,
)


class TestClassifyUnresolvedWikilink:
    def test_research_prefix(self):
        assert classify_unresolved_wikilink("research/vendor-comparison-matrix.md") == "missing_research_doc_or_directory"
        assert classify_unresolved_wikilink("research/ai-trends.md") == "missing_research_doc_or_directory"

    def test_kb_entity_dir_concepts(self):
        assert classify_unresolved_wikilink("concepts/ontology.md") == "missing_or_renamed_entity_doc"

    def test_kb_entity_dir_vendors(self):
        assert classify_unresolved_wikilink("vendors/palantir-foundry.md") == "missing_or_renamed_entity_doc"

    def test_kb_entity_dir_products(self):
        assert classify_unresolved_wikilink("products/foundry.md") == "missing_or_renamed_entity_doc"

    def test_kb_entity_dir_methodologies(self):
        assert classify_unresolved_wikilink("methodologies/ai-transformation-roadmap.md") == "missing_or_renamed_entity_doc"

    def test_kb_entity_dir_cases(self):
        assert classify_unresolved_wikilink("cases/banking-knowledge-graph-customer-360.md") == "missing_or_renamed_entity_doc"

    def test_kb_entity_dir_persons(self):
        assert classify_unresolved_wikilink("persons/john-doe.md") == "missing_or_renamed_entity_doc"

    def test_kb_entity_dir_proposals(self):
        assert classify_unresolved_wikilink("proposals/new-idea.md") == "missing_or_renamed_entity_doc"

    def test_kb_entity_dir_faqs(self):
        assert classify_unresolved_wikilink("faqs/client-faq.md") == "missing_or_renamed_entity_doc"

    def test_other_target(self):
        assert classify_unresolved_wikilink("some/random/path.md") == "review_link_target"
        assert classify_unresolved_wikilink("healthcare-patient-view-palantir.md") == "review_link_target"
        assert classify_unresolved_wikilink("writeback-dataset.md") == "review_link_target"

    def test_empty_path(self):
        assert classify_unresolved_wikilink("") == "review_link_target"

    def test_kb_entity_dirs_are_complete(self):
        assert "concepts" in KB_ENTITY_DIRS
        assert "vendors" in KB_ENTITY_DIRS
        assert "products" in KB_ENTITY_DIRS
        assert "methodologies" in KB_ENTITY_DIRS
        assert "cases" in KB_ENTITY_DIRS
        assert "persons" in KB_ENTITY_DIRS
        assert "proposals" in KB_ENTITY_DIRS
        assert "faqs" in KB_ENTITY_DIRS


class TestDetermineActionType:
    def test_stale_eval(self):
        assert determine_action_type("stale_eval_gold_doc_id", "update_eval_gold_or_add_missing_doc") == "update_eval_gold_doc_id"

    def test_duplicate_title(self):
        assert determine_action_type("duplicate_title", "resolve_identity_conflict") == "resolve_identity_conflict"

    def test_duplicate_alias(self):
        assert determine_action_type("duplicate_alias", "resolve_identity_conflict") == "resolve_identity_conflict"

    def test_unresolved_research(self):
        assert determine_action_type("unresolved_wikilink", "missing_research_doc_or_directory") == "create_missing_research_doc"

    def test_unresolved_kb_entity(self):
        assert determine_action_type("unresolved_wikilink", "missing_or_renamed_entity_doc") == "create_or_rename_entity_doc"

    def test_unresolved_other(self):
        assert determine_action_type("unresolved_wikilink", "review_link_target") == "review_link_target"

    def test_fallback(self):
        assert determine_action_type("unknown_code", "anything") == "review_link_target"


class TestCalculatePriority:
    def test_stale_eval_high(self):
        assert calculate_priority("stale_eval_gold_doc_id") == "high"
        assert calculate_priority("stale_eval_gold_doc_id", 1) == "high"

    def test_duplicate_high(self):
        assert calculate_priority("duplicate_title") == "high"
        assert calculate_priority("duplicate_alias") == "high"

    def test_unresolved_wikilink_high_with_count_3(self):
        assert calculate_priority("unresolved_wikilink", 3) == "high"
        assert calculate_priority("unresolved_wikilink", 5) == "high"
        assert calculate_priority("unresolved_wikilink", 10) == "high"

    def test_unresolved_wikilink_medium_with_count_1_2(self):
        assert calculate_priority("unresolved_wikilink", 1) == "medium"
        assert calculate_priority("unresolved_wikilink", 2) == "medium"

    def test_unresolved_wikilink_default_count(self):
        assert calculate_priority("unresolved_wikilink") == "medium"

    def test_fallback_medium(self):
        assert calculate_priority("unknown_code") == "medium"
        assert calculate_priority("unknown_code", 5) == "medium"


class TestAggregateBacklog:
    def test_empty_issues(self):
        assert aggregate_backlog([]) == []

    def test_single_unresolved_wikilink(self):
        issues = [
            {
                "code": "unresolved_wikilink",
                "triage_note": "review_link_target",
                "source_path": "cases/test.md",
                "details": {"target_path": "some/target.md"},
            },
        ]
        result = aggregate_backlog(issues)
        assert len(result) == 1
        entry = result[0]
        assert entry["action_type"] == "review_link_target"
        assert entry["priority"] == "medium"
        assert entry["issue_code"] == "unresolved_wikilink"
        assert entry["target"] == "some/target.md"
        assert entry["affected_count"] == 1
        assert "cases/test.md" in entry["examples"]

    def test_aggregates_by_target_path(self):
        issues = [
            {
                "code": "unresolved_wikilink",
                "triage_note": "review_link_target",
                "source_path": "a.md",
                "details": {"target_path": "same/target.md"},
            },
            {
                "code": "unresolved_wikilink",
                "triage_note": "review_link_target",
                "source_path": "b.md",
                "details": {"target_path": "same/target.md"},
            },
            {
                "code": "unresolved_wikilink",
                "triage_note": "review_link_target",
                "source_path": "c.md",
                "details": {"target_path": "same/target.md"},
            },
        ]
        result = aggregate_backlog(issues)
        assert len(result) == 1
        entry = result[0]
        assert entry["affected_count"] == 3
        assert entry["priority"] == "high"

    def test_separate_targets_create_separate_entries(self):
        issues = [
            {
                "code": "unresolved_wikilink",
                "triage_note": "review_link_target",
                "source_path": "a.md",
                "details": {"target_path": "target-a.md"},
            },
            {
                "code": "unresolved_wikilink",
                "triage_note": "review_link_target",
                "source_path": "b.md",
                "details": {"target_path": "target-b.md"},
            },
        ]
        result = aggregate_backlog(issues)
        assert len(result) == 2

    def test_stale_eval_grouped_by_expected_doc_id(self):
        issues = [
            {
                "code": "stale_eval_gold_doc_id",
                "triage_note": "update_eval_gold_or_add_missing_doc",
                "source_path": "eval.json",
                "details": {"expected_doc_id": "concepts/agent"},
            },
            {
                "code": "stale_eval_gold_doc_id",
                "triage_note": "update_eval_gold_or_add_missing_doc",
                "source_path": "eval.json",
                "details": {"expected_doc_id": "concepts/agent"},
            },
        ]
        result = aggregate_backlog(issues)
        assert len(result) == 1
        entry = result[0]
        assert entry["action_type"] == "update_eval_gold_doc_id"
        assert entry["priority"] == "high"
        assert entry["affected_count"] == 2

    def test_duplicate_title_grouped_by_normalized(self):
        issues = [
            {
                "code": "duplicate_title",
                "triage_note": "resolve_identity_conflict",
                "source_path": "a.md",
                "details": {"normalized_title": "same title"},
            },
            {
                "code": "duplicate_title",
                "triage_note": "resolve_identity_conflict",
                "source_path": "b.md",
                "details": {"normalized_title": "same title"},
            },
        ]
        result = aggregate_backlog(issues)
        assert len(result) == 1
        entry = result[0]
        assert entry["action_type"] == "resolve_identity_conflict"
        assert entry["priority"] == "high"

    def test_duplicate_alias_grouped_by_normalized(self):
        issues = [
            {
                "code": "duplicate_alias",
                "triage_note": "resolve_identity_conflict",
                "source_path": "x.md",
                "details": {"normalized_alias": "shared"},
            },
            {
                "code": "duplicate_alias",
                "triage_note": "resolve_identity_conflict",
                "source_path": "y.md",
                "details": {"normalized_alias": "shared"},
            },
        ]
        result = aggregate_backlog(issues)
        assert len(result) == 1
        entry = result[0]
        assert entry["target"] == "shared"

    def test_mixed_issue_types(self):
        issues = [
            {
                "code": "stale_eval_gold_doc_id",
                "triage_note": "update_eval_gold_or_add_missing_doc",
                "source_path": "eval.json",
                "details": {"expected_doc_id": "concepts/agent"},
            },
            {
                "code": "unresolved_wikilink",
                "triage_note": "missing_research_doc_or_directory",
                "source_path": "src.md",
                "details": {"target_path": "research/ai.md"},
            },
        ]
        result = aggregate_backlog(issues)
        assert len(result) == 2
        types = {e["action_type"] for e in result}
        assert "update_eval_gold_doc_id" in types
        assert "create_missing_research_doc" in types

    def test_examples_capped(self):
        issues = []
        for i in range(10):
            issues.append({
                "code": "unresolved_wikilink",
                "triage_note": "review_link_target",
                "source_path": f"doc{i}.md",
                "details": {"target_path": "shared/target.md"},
            })
        result = aggregate_backlog(issues)
        assert len(result) == 1
        entry = result[0]
        assert entry["affected_count"] == 10
        assert len(entry["examples"]) <= 6

    def test_suggested_human_action_for_each_entry(self):
        issues = [
            {
                "code": "stale_eval_gold_doc_id",
                "triage_note": "update_eval_gold_or_add_missing_doc",
                "source_path": "eval.json",
                "details": {"expected_doc_id": "concepts/agent"},
            },
        ]
        result = aggregate_backlog(issues)
        entry = result[0]
        assert entry["suggested_human_action"]
        assert isinstance(entry["suggested_human_action"], str)
        assert len(entry["suggested_human_action"]) > 10
