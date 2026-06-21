# Phase 15 Planning — Evidence-to-Ontology Feedback Loop v1

Status: 15.1 implemented. 15.2/15.3 not started.

## Decision

Phase 15 starts with the gap left intentionally by S2.4C and exposed by S2.5A:

```text
project-scoped RAG answer
-> user confirms it is worth keeping
-> ProjectEvidenceLink records it as durable project evidence
-> later ontology/modeling work can use the reviewed evidence
```

This phase is not MCP runtime, not Graph RAG, not a full ontology modeling studio, and not Agent auto-writing Ontology.

## Why This Is Next

S2.4C made project-scoped RAG runs persist `RagRun.project_id` but deliberately did **not** auto-create `ProjectEvidenceLink`.

That distinction is correct:

- `RagRun.project_id` proves where an answer was generated.
- `ProjectEvidenceLink` proves a human intentionally attached that answer as project evidence.

S2.5A now lets users ask scoped questions inside Pilot. The next product step is a user-confirmed bridge from useful scoped answers into durable project evidence.

## Boundaries

Allowed:

- user-confirmed save of a project-scoped RAG run as project evidence
- reuse of existing `POST /groups/{gid}/projects/{pid}/evidence-links`
- clear UI state for already-linked answers, saved answers, and save failures
- later use of saved evidence as input to modeling draft proposals

Not allowed:

- automatic evidence linking
- Agent-created evidence links
- Agent accepting, publishing, or modifying Ontology
- MCP runtime, SDK, server, or client
- Graph RAG
- external KB writes or repairs
- full modeling studio
- hiding standalone pages

## Slices

### 15.1 — Save Scoped RAG Answer As Project Evidence

Lane: Standard. Delivered.

Goal: In the Pilot scoped Ask panel, let owner/admin intentionally save the generated project RAG answer as durable project evidence.

Implemented shape:

- Use the existing project-scoped RAG answer result from S2.5A.
- Add a secondary action: "保存为项目证据".
- Call existing `POST /groups/{gid}/projects/{pid}/evidence-links` with:
  - `evidence_type = "rag_run"`
  - `evidence_id = run_id`
  - `role = "decision"`
  - bounded note
- Show saved/already-linked state.
- Do not auto-create links after answer generation.

Owner/admin only. Members can ask but do not see the write action.

Verification:

- related frontend smoke via `scripts/verify_ui.py`
- `node --check` on changed JS files
- `git diff --check`

### 15.2 — Project Evidence Review Surface

Lane: Standard.

Goal: Make saved RAG answers visible in the Pilot evidence summary, distinct from document evidence.

Expected implementation shape:

- Reuse `GET /groups/{gid}/projects/{pid}/summary` and/or evidence-link list.
- Show evidence type, role, saved time, and unavailable state.
- Do not show raw prompts, raw answer text, file paths, storage paths, secrets, or stack traces.

### 15.3 — Evidence-Backed Modeling Draft Candidate Design

Lane: Fast if design only; Safety if backend draft generation changes.

Goal: Decide whether and how reviewed project evidence can feed modeling draft proposals.

Rules:

- no LLM-only draft generation
- no auto-accept
- no publish
- no external KB write
- generated proposals must carry `source_rag_run_id`, `project_id`, and bounded `evidence_refs`

This slice should likely be design-first.

## First CC Prompt

```text
Implement Phase 15.1 only: Save scoped RAG answer as project evidence.

Read:
- docs/project-status.toml
- docs/development-workflow.md
- docs/phase15-planning.md
- static/js/pages/project.js
- static/js/api.js
- src/semantic_lighthouse/routers/evidence_links.py only if endpoint contract is unclear

Lane: Standard.

Scope:
- In the Pilot Goal scoped Ask panel, add a secondary action to save the current project RAG answer as project evidence.
- Reuse existing POST /groups/{gid}/projects/{pid}/evidence-links.
- Use evidence_type=rag_run and evidence_id=run_id from the scoped RAG answer.
- Show saved/already-linked/failure state.
- Owner/admin only if the endpoint requires it; members should not see a write action.

Hard boundaries:
- Do not modify backend, DB, migrations, routes, or auth unless the existing API cannot support the flow.
- Do not auto-link answers.
- Do not create tasks automatically.
- Do not add Agent/MCP/Graph RAG behavior.
- Do not hide or alter standalone pages/navigation.

Verify:
- node --check on changed JS files
- .\\.venv\\Scripts\\python scripts\\verify_ui.py
- git diff --check
- git status --short

At the end:
- Update docs/project-status.toml with Phase 15.1 result.
- Commit with message: feat: save scoped answer as project evidence
```
