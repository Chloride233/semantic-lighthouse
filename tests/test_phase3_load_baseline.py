from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.run_phase3_load_baseline import (
    RequestResult,
    ResourceSnapshot,
    nearest_rank,
    summarize_results,
)


ROOT = Path(__file__).resolve().parents[1]


def test_nearest_rank_percentiles_use_observed_values():
    values = [float(value) for value in range(1, 101)]

    assert nearest_rank(values, 50) == 50.0
    assert nearest_rank(values, 95) == 95.0
    assert nearest_rank(values, 99) == 99.0


def test_summary_counts_http_and_transport_errors():
    usage = ResourceSnapshot(1.0, 2.0, 100.0)
    results = [
        RequestResult(10.0, 200, "ok"),
        RequestResult(20.0, 503, "provider", None),
        RequestResult(30.0, None, "transport", "TimeoutError: timed out"),
    ]

    summary = summarize_results(10, results, 1.0, usage, usage)

    assert summary["successes"] == 1
    assert summary["errors"] == 2
    assert summary["error_rate"] == 0.6667
    assert summary["latency_ms"] == {
        "p50": 20.0,
        "p95": 30.0,
        "p99": 30.0,
        "min": 10.0,
        "max": 30.0,
    }
    assert summary["status_counts"] == {"200": 1, "503": 1, "exception": 1}
    assert [trace["request_id"] for trace in summary["trace_samples"]] == [
        "provider",
        "transport",
    ]


def test_cli_entrypoint_loads_without_editable_install():
    result = subprocess.run(
        [sys.executable, "scripts/run_phase3_load_baseline.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--requests-per-level" in result.stdout
