# Phase 3 Reliability Evidence Design

## Context

Evidence Roadmap Phase 3 is GitHub Issue #2: establish production-oriented
evidence for concurrency, latency, resource use, failure handling, and
degradation. Phase 1 RAG quality and Phase 2 Agent security remain regression
gates throughout this phase.

This is a Safety Lane phase because later slices may affect provider calls,
request admission, audit persistence, and concurrent write behavior.

## Acceptance Map

| Issue acceptance item | Evidence slice |
|---|---|
| 1, 10, and 50 concurrent load scenarios | Offline fake-provider RAG load runner |
| Throughput, P50/P95/P99, error rate, resource use | Structured JSON output and committed report |
| Timeout, cancellation, retry, idempotency, rate limit, backpressure | Focused deterministic control tests after the baseline |
| Model unavailable, quota exhausted, database failure | Fault-injection tests with bounded public error behavior |
| Load report and key traces | Phase 3 report with request IDs and before/after results |

## Selected Sequence

1. Build and run a local baseline against the real authenticated RAG route with
   temporary SQLite and fake providers at concurrency 1, 10, and 50.
2. Use the measured failures and latency distribution to select the smallest
   reliability control rather than adding speculative middleware.
3. Add deterministic fault-injection tests for provider and database failures.
4. Add only the timeout, retry, admission, idempotency, and cancellation
   controls required by those tests.
5. Rerun the same baseline for the before/after report and close the phase only
   after the Phase 1 and Phase 2 gates still pass.

## Baseline Boundary

The baseline runner exercises `POST /groups/{group_id}/rag/answer` through the
ASGI application. It creates an isolated temporary database, authenticates a
user, creates a group, uploads one document, and uses fake chat and embedding
providers. Each request receives a unique `X-Request-ID`; the response echo is
checked so error samples can be correlated without storing response content.

The runner records request throughput, nearest-rank P50/P95/P99 latency, error
rate, status counts, process CPU time, and process peak RSS. These are local
application baselines, not production capacity claims. SQLite and the fake
provider deliberately remove network variance but do not represent PostgreSQL
pooling or hosted-model latency.

## Safety Boundaries

- The runner never uses provider credentials, external data, or runtime storage.
- Temporary data is deleted after every run and is not committed.
- `group_id` and identity continue to come from authenticated server context.
- RAG runs keep their existing audit persistence and citation behavior.
- No runtime MCP, schema migration, public API, or production default changes
  are part of the baseline slice.

## Verification

The baseline slice requires:

1. Unit tests for metric calculation and error accounting.
2. A successful 1/10/50 baseline command with structured output.
3. Phase 1 and Phase 2 regression gates.
4. Full pytest, full ruff, documentation alignment, and `git diff --check`.

## Residual Risks

An in-process ASGI run does not measure reverse-proxy behavior, network sockets,
multi-process workers, PostgreSQL connection pools, or real provider quotas.
Those claims require a deployment-scoped follow-up after deterministic controls
are complete. The baseline is useful for regression and bottleneck discovery,
not for declaring production capacity.
