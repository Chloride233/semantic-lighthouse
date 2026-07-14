# Phase 3 Reliability Report

## Status

Evidence Roadmap Phase 3 is complete. The deterministic gate covers all GitHub
Issue #2 reliability and degradation controls; the same load runner provides
before/after evidence.

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

## After Controls

The same command and 100-request scenarios were rerun after Provider retry,
admission control, and DB-backed idempotency were enabled. The load runner lifts
only its per-user rate limit so the performance measurement itself is not
rejected; the active-request limit remains 20 and the bounded queue remains 40.

| Concurrency | Throughput after | P50 after | P95 before | P95 after | P99 after | Errors after | Peak RSS after |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 294.80 req/s | 3.07 ms | 4.01 ms | 4.79 ms | 6.96 ms | 0% | 126.64 MB |
| 10 | 334.01 req/s | 16.92 ms | 72.07 ms | 75.83 ms | 131.05 ms | 0% | 130.56 MB |
| 50 | 249.82 req/s | 126.50 ms | 257.98 ms | 247.48 ms | 299.12 ms | 0% | 135.91 MB |

At concurrency 50, P95 improved by 4.1% while throughput fell by 16.0%. The
throughput reduction is the intentional cost of limiting active RAG work to 20
requests instead of letting all 50 enter Provider/database work at once. P99
was effectively flat (297.00 ms before, 299.12 ms after), and all 300 requests
still completed successfully.

Combined user/system CPU time after controls was 0.292, 0.391, and 0.385
seconds for the 1, 10, and 50 concurrency scenarios respectively.

## Reliability And Degradation Evidence

Run the deterministic gate:

```bash
.venv/bin/python scripts/run_phase3_reliability_gate.py
```

The gate currently passes 22 tests: 19 reliability/degradation cases and 3 load
runner metric/entrypoint cases.

| Control | Deterministic evidence |
|---|---|
| Provider timeout | Retries to the configured attempt bound, then RAG returns 504 and stores an error run |
| Provider retry | HTTP 408/429/5xx and transport errors retry; non-transient HTTP 400 does not |
| Quota exhaustion | RAG returns 503 with bounded `Retry-After` and an audited `quota` error |
| Model unavailable | RAG returns 503 with request ID and an audited `unavailable` error |
| Rate limiting | A second request beyond the per-user fixed-window limit returns 429 |
| Queue backpressure | Full queue and queue timeout return 503 without entering RAG work |
| Cancellation | Cancelling a queued waiter frees its queue position and does not leak active capacity |
| Idempotency | DB unique reservation prevents repeat Provider work; completed/error results replay, conflicts and pending requests return 409 |
| Database failure | SQLAlchemy failure returns bounded 503 with no SQL, password, connection string, or internal exception text |

Correlated fault traces use `phase3-db-trace`, `phase3-unavailable-trace`,
`phase3-quota-trace`, and `phase3-timeout-trace`. Tests verify each response
echoes its request ID and that the matching error classification is persisted.

SQLite migration smoke upgraded an empty database through
`0030_v30_rag_idempotency (head)`.

## Slice Verification

- Phase 3 load-runner tests: 3 passed
- Phase 3 reliability/degradation tests: 19 passed
- Phase 3 combined gate: 22 passed
- Phase 1 RAG evaluation gate: all thresholds passed
- Phase 2 Agent security gate: 12 passed
- Browser E2E with system Chrome: 18 passed
- Full regression: 1,157 passed, 3 skipped
- Migration smoke: `0030` upgrade, downgrade to `0029`, and re-upgrade passed
- Ruff: clean across `src`, `tests`, Phase 3 scripts, and migration
- Documentation alignment and `git diff --check`: passed
- Implementation commit: `66467ea`

## Claim Boundary

This baseline measures the application in-process through ASGI. It is suitable
for deterministic regression and optimization comparisons, but it is not a
production capacity claim. It excludes reverse proxies, network sockets,
multi-process workers, PostgreSQL pool behavior, and hosted-model latency or
quota behavior.

## Residual Risks

- Admission and rate limits are process-local. The production example defaults
  to one API worker; a multi-worker deployment needs a shared limiter before
  claiming a global limit.
- Cancellation is proven while waiting in the bounded queue. A synchronous
  Provider call already in progress may finish after a client disconnects.
- Retrying an inference POST can create duplicate Provider billing if a remote
  service completes a request but loses the response.
- Local fake-provider SQLite latency does not represent PostgreSQL pooling or
  hosted-model latency and quota behavior.
