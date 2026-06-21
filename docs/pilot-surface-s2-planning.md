# Pilot Surface S2 Planning

Status: planning ready. No implementation in this document.

## Goal

Turn the Pilot workspace into the primary FDE operating surface without hiding old tools prematurely.

The user path should feel ordered:

```text
create Pilot -> add data/evidence -> ask scoped questions -> model -> validate -> query runtime -> track actions
```

This is not a new backend phase. S2.4 already closed the backend consolidation:

- project summary: `GET /groups/{gid}/projects/{pid}/summary`
- project evidence: `POST|GET|DELETE /groups/{gid}/projects/{pid}/evidence-links`
- project RAG: `POST /groups/{gid}/projects/{pid}/rag/answer`
- project context: Conversations, Tasks, and Agent runs already support `project_id`

Do not expand S2.4D/E/F unless implementation discovers a concrete API gap.

## Product Decision

Pilot becomes the user's workbench. The old pages remain available as full tools.

| Surface | Role |
|---------|------|
| Pilot | Guided FDE workflow for one business problem |
| Ontology | Group-level semantic governance and reusable semantic assets |
| More Tools | Full-power supporting tools: Ask, Knowledge Base, Conversations, Tasks, Agent |

No page hiding until replacement parity is proven by UI smoke/E2E.

## Information Architecture

### Project Header

Show project identity and stage once:

- project name, status, entry mode, updated time
- five-stage rail
- compact business goal
- small project summary counts from `/summary`

Avoid making the page a dashboard. Summary exists to orient the user, not to become another parallel workspace.

### Goal Stage

Purpose: define the business problem and collect supporting context.

Allowed additions:

- project-bounded Ask panel using `POST /groups/{gid}/projects/{pid}/rag/answer`
- evidence summary using `/summary.recent_evidence`
- link to full Knowledge Base for document management

Rules:

- If no project evidence exists, Ask must show an empty-evidence state, not a generic failure.
- Do not auto-link RAG answers as project evidence.
- Do not hide standalone Ask.

### Data Stage

Purpose: upload and inspect datasets.

Keep the current F2 flow:

- upload CSV/XLSX
- profile metadata
- generate model drafts

Do not add knowledge management here; evidence belongs to Goal.

### Model Stage

Purpose: review deterministic ontology drafts.

Keep the existing F2B controls:

- generate drafts
- batch accept/reject
- show evidence and quality hints

Do not introduce automatic ontology publishing.

### Validate Stage

Purpose: prove the accepted model can compile into a package.

Keep:

- quality check
- WARN override reason
- FAIL absolute block
- contract/package inspection

### Pilot Stage

Purpose: run the semantic runtime and capture follow-up work.

Allowed additions after the first implementation slice:

- project task summary and create action using existing Tasks API with `project_id`
- scoped conversation starter using existing Conversations API with `project_id`
- Agent run summary only; full HITL stays in standalone Agent until parity exists

Do not embed full Agent HITL in the first frontend slice.

## Recommended Slices

### S2.5A — Project Overview And Scoped Ask

Lane: Standard.

Scope:

- Load `GET /groups/{gid}/projects/{pid}/summary` in `static/js/pages/project.js`.
- Add a compact summary strip or aside block.
- Add Goal-stage project Ask panel that calls `POST /groups/{gid}/projects/{pid}/rag/answer`.
- Render answer, confidence, citations, knowledge gaps, and no-evidence state.

Do not:

- modify backend
- hide old pages
- auto-create evidence links
- redesign all stages
- add Agent/Task/Conversation embedding

Verification:

- related frontend smoke via `scripts/verify_ui.py`
- related E2E for owner/member/no-evidence if practical
- `git diff --check`

### S2.5B — Project Actions Summary

Lane: Standard.

Scope:

- Add Pilot-stage task summary using existing project-scoped task list/filter.
- Add minimal "create task" action only if existing API supports the required `project_id` contract.
- Keep standalone Tasks page.

Do not add backend unless a concrete API gap is documented first.

### S2.5C — Scoped Conversation Starter

Lane: Standard.

Scope:

- Add a lightweight "start scoped conversation" action from Goal or Pilot.
- Reuse existing Conversations API with `project_id`.
- Navigate to the standalone conversation page after creation if full chat embedding is too large.

This is a bridge, not a full chat rewrite.

### S2.5D — Navigation Parity Review

Lane: Fast for docs, Standard if code changes.

Scope:

- Compare Pilot replacement coverage against standalone pages.
- Decide whether More Tools can be reduced.

No hiding unless tests prove the replacement workflow.

## First CC Implementation Prompt Shape

Keep the prompt short:

```text
Implement S2.5A only: Project Overview + scoped Ask inside Pilot Goal stage.
Read docs/project-status.toml, docs/development-workflow.md, docs/pilot-surface-s2-planning.md, and relevant project.js/api.js files.
Lane: Standard.
Do not modify backend, routes, database, or old standalone pages.
Use GET /groups/{gid}/projects/{pid}/summary and POST /groups/{gid}/projects/{pid}/rag/answer.
Render project summary counts, recent evidence, scoped Ask answer/citations/confidence/knowledge gaps/no-evidence.
No auto evidence linking. No page hiding. No Agent/Task/Conversation embedding.
Run scripts/verify_ui.py, related E2E if touched/needed, git diff --check, git status --short.
Update docs/project-status.toml with S2.5A status and commit.
```

