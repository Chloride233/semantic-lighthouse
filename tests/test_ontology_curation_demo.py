"""Tests for curation demo helpers — does NOT require real KB."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_ontology_curation_demo import (
    classify_wikilink, action_for_wikilink,
    priority_for_backlog, build_backlog,
)


class TestClassifyWikilink:
    def test_research(self):
        assert classify_wikilink("research/x.md") == "missing_research_doc_or_directory"

    def test_kb_dir(self):
        assert classify_wikilink("concepts/x.md") == "missing_or_renamed_entity_doc"

    def test_other(self):
        assert classify_wikilink("readme.md") == "review_link_target"


class TestActionForWikilink:
    def test_research(self):
        assert action_for_wikilink("research/x.md") == "create_missing_research_doc"

    def test_concepts(self):
        assert action_for_wikilink("concepts/x.md") == "create_or_rename_entity_doc"

    def test_other(self):
        assert action_for_wikilink("readme.md") == "review_link_target"


class TestPriority:
    def test_eval_high(self):
        assert priority_for_backlog("update_eval_gold_doc_id", 1) == "high"

    def test_identity_high(self):
        assert priority_for_backlog("resolve_identity_conflict", 1) == "high"

    def test_high_count(self):
        assert priority_for_backlog("create_missing_research_doc", 5) == "high"

    def test_medium_count(self):
        assert priority_for_backlog("create_missing_research_doc", 1) == "medium"


class FakeIssue:
    def __init__(self, status, code, details=None):
        self.triage_status = status
        self.code = code
        self.details = details or {}
        self.message = "t"
        self.source_path = "t.md"


class TestBuildBacklog:
    def test_wikilink_agg(self):
        issues = [
            FakeIssue("confirmed", "unresolved_wikilink", {"target_path": "research/x.md"}),
            FakeIssue("confirmed", "unresolved_wikilink", {"target_path": "research/x.md"}),
            FakeIssue("confirmed", "unresolved_wikilink", {"target_path": "concepts/y.md"}),
        ]
        b = build_backlog(issues)
        assert len(b) == 2
        r = [e for e in b if e["target"] == "research/x.md"][0]
        assert r["affected_count"] == 2
        assert r["action_type"] == "create_missing_research_doc"

    def test_stale(self):
        issues = [FakeIssue("confirmed", "stale_eval_gold_doc_id", {"expected_doc_id": "concepts/agent", "question_ids": ["Q1"]})]
        b = build_backlog(issues)
        assert len(b) == 1
        assert b[0]["action_type"] == "update_eval_gold_doc_id"
        assert b[0]["priority"] == "high"

    def test_pending_excluded(self):
        b = build_backlog([FakeIssue("pending", "unresolved_wikilink", {"target_path": "x.md"})])
        assert len(b) == 0

    def test_ignored_excluded(self):
        b = build_backlog([FakeIssue("ignored", "unresolved_wikilink", {"target_path": "x.md"})])
        assert len(b) == 0

    def test_priority_order(self):
        issues = [
            FakeIssue("confirmed", "stale_eval_gold_doc_id", {"expected_doc_id": "x"}),
            FakeIssue("confirmed", "unresolved_wikilink", {"target_path": "concepts/a.md"}),
        ]
        b = build_backlog(issues)
        assert b[0]["priority"] == "high"  # stale_eval first
