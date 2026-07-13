"""P3 retrieval eval integration tests — verify metrics are computable and stable."""

import json

from semantic_lighthouse.routers.rag import _keyword_terms


class TestKeywordTerms:
    def test_extracts_english_and_chinese(self):
        terms = _keyword_terms("什么是Ontology？企业为什么需要它？")
        assert "Ontology" in terms
        assert len(terms) >= 2

    def test_chinese_two_char_minimum(self):
        terms = _keyword_terms("的")
        assert "的" not in terms

    def test_deduplicates_terms(self):
        terms = _keyword_terms("Ontology Ontology")
        assert terms.count("Ontology") == 1

    def test_empty_query_returns_empty(self):
        assert _keyword_terms("") == []

    def test_max_eight_terms(self):
        terms = _keyword_terms("a b c d e f g h i j k")
        assert len(terms) <= 8


class TestEvalReport:
    def test_report_has_expected_structure(self):
        from pathlib import Path

        queries_path = Path(__file__).parent / "eval" / "queries.json"
        fixtures_dir = Path(__file__).parent / "eval" / "fixtures"

        queries = json.loads(queries_path.read_text(encoding="utf-8"))
        assert 50 <= len(queries) <= 100

        fixtures = sorted(fixtures_dir.glob("*.md"))
        assert len(fixtures) == 15

        all_titles: set[str] = set()
        for fp in fixtures:
            text = fp.read_text(encoding="utf-8")
            for line in text.split("\n"):
                if line.startswith("title:"):
                    all_titles.add(line.split(":", 1)[1].strip())
                    break

        query_ids = [q["id"] for q in queries]
        assert len(query_ids) == len(set(query_ids))

        for q in queries:
            assert q["query"].strip()
            assert q["reference_answer"].strip()
            if q.get("expected_refusal", False):
                assert q["category"] == "no_evidence"
                assert q["expected_document_titles"] == []
                assert q["evidence_sources"] == []
                continue

            assert q["evidence_sources"]

            expected_titles = set(q["expected_document_titles"])
            evidence_titles = {source["document_title"] for source in q["evidence_sources"]}
            assert evidence_titles == expected_titles

            for title in expected_titles:
                assert title in all_titles, (
                    f"q{q['id']}: expected '{title}' not in fixtures {sorted(all_titles)}"
                )

            for source in q["evidence_sources"]:
                fixture = fixtures_dir / source["fixture"]
                assert fixture.is_file(), f"{q['id']}: missing fixture {fixture.name}"
                fixture_text = fixture.read_text(encoding="utf-8")
                assert source["quote"] in fixture_text, (
                    f"{q['id']}: evidence quote not found in {fixture.name}"
                )

    def test_eval_runner_produces_valid_report(self):
        import subprocess
        import sys
        from pathlib import Path

        cwd = str(Path(__file__).resolve().parent.parent)
        result = subprocess.run(
            [sys.executable, "scripts/run_eval.py"],
            capture_output=True, text=True, cwd=cwd,
        )
        assert result.returncode == 0, f"eval failed: {result.stderr[:500]}"

        # stdout may contain deprecation warnings before the JSON block
        idx = result.stdout.find("{")
        assert idx >= 0, f"No JSON found in eval output: {result.stdout[:300]}"
        report = json.loads(result.stdout[idx:])

        assert report is not None, "No JSON in eval output"
        assert report["corpus"]["document_count"] == 15
        assert report["corpus"]["query_count"] == 65

        for method in ("keyword", "semantic", "hybrid"):
            m = report["methods"][method]
            assert 0.0 <= m["recall_at_3"] <= 1.0
            assert 0.0 <= m["recall_at_5"] <= 1.0
            assert 0.0 <= m["no_result_rate"] <= 1.0

        rag = report["rag_metrics"]
        assert rag["answerable_queries"] == 60
        assert rag["refusal_queries"] == 5
        assert 0.0 <= rag["citation_correctness"] <= 1.0
        assert 0.0 <= rag["faithfulness"] <= 1.0
        assert 0.0 <= rag["refusal_accuracy"] <= 1.0
        assert len(rag["per_query"]) == 60
        assert len(rag["refusal_results"]) == 5
        assert rag["citation_correctness"] == 0.196
        assert rag["faithfulness"] == 0.293
        assert rag["refusal_accuracy"] == 1.0

        comparison = report["comparison"]
        assert comparison["best_method"] == "keyword"
        assert comparison["ranking"] == ["keyword", "hybrid", "semantic"]
        assert comparison["hybrid_vs_keyword"] == {
            "recall_at_5_delta": 0.0,
            "mrr_delta": 0.0,
            "precision_at_5_delta": -0.048,
        }

        assert report["duration_ms"] > 0

    def test_eval_results_are_reproducible(self):
        import subprocess
        import sys
        from pathlib import Path

        cwd = str(Path(__file__).resolve().parent.parent)

        def _metrics():
            result = subprocess.run(
                [sys.executable, "scripts/run_eval.py"],
                capture_output=True, text=True, cwd=cwd,
            )
            assert result.returncode == 0
            idx = result.stdout.find("{")
            assert idx >= 0, f"No JSON in eval output: {result.stdout[:300]}"
            r = json.loads(result.stdout[idx:])
            return {m: r["methods"][m]["recall_at_5"] for m in ("keyword", "semantic", "hybrid")}
            raise AssertionError("No JSON")

        a = _metrics()
        b = _metrics()
        assert a == b, f"Metrics drift: {a} vs {b}"
