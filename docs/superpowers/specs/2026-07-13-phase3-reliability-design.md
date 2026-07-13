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

## Reliability Controls

### Provider Calls

Chat and embedding HTTP calls share a small retry helper. A request is retried
only for connect/transport failures, timeouts, HTTP 408, HTTP 429, and HTTP 5xx.
HTTP 4xx validation/authentication failures are never retried. The configured
attempt count includes the first call and backoff is bounded and deterministic
in tests.

Terminal errors are classified as `timeout`, `quota`, `unavailable`, or
`bad_gateway`. RAG maps them to 504, 503, 503, and 502 respectively while
preserving the existing failed-run audit. Provider response bodies remain
bounded by the existing 500-character formatter.

### Admission And Backpressure

Authenticated RAG answer requests pass through an in-process admission
controller before retrieval or Provider work. It enforces:

- a per-authenticated-user fixed-window request limit
- a process-local maximum active RAG request count
- a bounded waiting queue
- a maximum queue wait time

Rate rejection returns 429. A full queue or queue timeout returns 503. Waiting
task cancellation removes the waiter and never consumes a capacity slot. An
active request always releases its slot in dependency cleanup. This proves
safe cancellation while queued; it does not claim that cancelling a synchronous
third-party HTTP call stops work already accepted by the Provider.

### Idempotency

Clients may send `Idempotency-Key` on RAG answer requests. The server reserves a
group-scoped, user-scoped, endpoint-scoped `pending` RAG run before retrieval.
A database unique constraint makes the reservation authoritative across
concurrent workers.
Completed keys replay the stored response without another Provider call;
pending keys return 409; failed keys replay the stored terminal error. Keys are
never trusted for group or user scope and are capped at 128 visible ASCII
characters.

### Database Degradation

Unhandled SQLAlchemy failures return a bounded HTTP 503 response with the
request ID and no SQL, connection string, storage path, or exception detail.
Provider audit persistence still must not mask the original Provider failure.

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
