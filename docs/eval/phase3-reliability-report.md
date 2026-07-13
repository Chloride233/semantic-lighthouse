# Phase 3 Reliability Report

## Status

Evidence Roadmap Phase 3 is in progress. This report currently covers the
repeatable local baseline for the first two GitHub Issue #2 acceptance items.
Timeout, cancellation, retry, idempotency, rate limiting, backpressure, and
fault degradation remain open and must not be presented as delivered behavior.

## Baseline Command

Run from the repository root:

```bash
.venv/bin/python scripts/run_phase3_load_baseline.py
```

The command writes structured evidence to `.tmp/phase3-load-baseline.json`.
It uses a temporary SQLite database, fake providers, the authenticated RAG API,
and request-ID correlation. It does not need external credentials.

## Baseline Results

Environment: macOS arm64, Python 3.14.6, temporary SQLite, fake chat and
embedding providers, in-process `httpx` ASGI transport. Each scenario sent 100
authenticated keyword RAG requests after one warm-up request.

| Concurrency | Requests | Throughput | P50 | P95 | P99 | Errors | Peak RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 100 | 333.45 req/s | 2.78 ms | 4.01 ms | 4.39 ms | 0% | 126.20 MB |
| 10 | 100 | 317.29 req/s | 20.91 ms | 72.07 ms | 127.10 ms | 0% | 129.95 MB |
| 50 | 100 | 297.49 req/s | 100.16 ms | 257.98 ms | 297.00 ms | 0% | 135.55 MB |

All 300 measured requests returned HTTP 200 and echoed their unique request ID.
The first correlated IDs were `phase3-c1-r0`, `phase3-c10-r0`, and
`phase3-c50-r0`; no error traces were produced. At 50 concurrency, throughput
was 10.8% below the single-request baseline and P95 was 64 times higher. This
is the optimization baseline, not a pass threshold.

CPU use remained below 0.42 combined user/system seconds per scenario. Peak RSS
rose by 9.35 MB from the first to the final scenario. Because RSS is a
process-level high-water mark, it is useful for before/after comparison but not
per-request attribution.

## Slice Verification

- Phase 3 load-runner tests: 3 passed
- Phase 1 RAG evaluation gate: all thresholds passed
- Phase 2 Agent security gate: 12 passed
- Browser E2E with system Chrome: 18 passed
- Full regression: 1,138 passed, 3 skipped
- Ruff: clean across `src`, `tests`, and the Phase 3 runner
- Documentation alignment and `git diff --check`: passed

## Claim Boundary

This baseline measures the application in-process through ASGI. It is suitable
for deterministic regression and optimization comparisons, but it is not a
production capacity claim. It excludes reverse proxies, network sockets,
multi-process workers, PostgreSQL pool behavior, and hosted-model latency or
quota behavior.

## Open Acceptance Items

- Verify timeout, cancellation, retry, idempotency, rate limiting, and queue
  backpressure.
- Verify degradation under model unavailability, quota exhaustion, and database
  errors.
- Rerun the same scenarios after controls are implemented and record the
  before/after comparison and key traces.
