# Frontend F2 — Guided Business Pilot Workspace

**Status**: F2A delivered + Review passed. F2B next. F2C future.

**Review results**: verify_ui 33/33, E2E 8/8, 0 console errors.
Screenshots in `.tmp/f2a-review/`.

Phase 14 established the five-stage business pilot pipeline (goal → data → model → validate → pilot). Frontend F2 gives users a guided single-path workspace to operate it, replacing the flat parallel-feature navigation with a Pilot-first information architecture.

---

## Slices

| Slice | Task | Status |
|-------|------|--------|
| F2A | Pilot entry, project creation, goal + data stage, nav restructure | ✅ Delivered |
| F2B | Model → Validate → Pilot full operation loop (modeling, review, package build, binding, query, activation) | Next |
| F2C | Frontend review, responsive/accessibility polish, old entry points consolidation | Future |

---

## F2A Delivered

### Navigation restructure
- Primary nav: **Pilot** (default), **Ontology**, **工作区**, **更多工具** (dropdown).
- Pilot is the default landing page after login (replaces `/ask`).
- Old routes (问答, 知识库, 对话, 任务, Agent) moved into "更多工具" dropdown.
- All old routes preserved and functional.
- Group switch navigates to Pilot list, not `/ask`.
- Brand link: with group → Pilot list; without group → 工作区.

### Pilot project list (`/groups/:gid/projects`)
- Lists active projects with name, goal summary, entry mode, stage, status, timestamp.
- Stage displayed as five-phase rail (目标→数据→模型→验证→Pilot).
- Owner/admin see "新建 Pilot" button; members read-only.
- Empty state guides directly to project creation (not knowledge base).

### Pilot project detail (`/groups/:gid/projects/:pid`)
- Five-stage progress rail showing current/completed/future stages.
- Stage determined exclusively by backend — frontend never advances.
- **Goal stage**: Shows business goal, entry mode. CTA → upload first dataset.
- **Data stage**: Dataset list, CSV/XLSX upload with multipart form.
  - Upload uses existing `POST /projects/{pid}/datasets`.
  - `include_sample_values` default false with explicit checkbox.
  - After upload, re-reads project to show backend-advanced stage.
  - Dataset list shows name, format, status, row/col counts.
  - Dataset detail expand shows metadata-only profile (columns, types, PK/FK).
  - Never shows storage_path or sample_values.
- **Model/Validate/Pilot stages**: Status display only (F2B implements controls).

### First-use path fixes
- After login with groups → Pilot list.
- New user after workspace creation → Pilot empty state.
- Workspace "打开" link → Pilot list.
- console.html title/tagline updated.

### API improvements
- `api.js`: automatic FormData detection, no manual Content-Type on FormData.
- Unified error message extraction from detail/message/issues fields.
- No `[object Object]` display.

### Design
- Minimalism & Swiss Style via ui-ux-pro-max skill.
- Monochrome neutral palette, minimal gold accent for status only.
- Card border-radius ≤ 6px. No gradients, no glassmorphism, no hero sections.
- Responsive at 390px mobile — no horizontal overflow.

### Out of scope for F2A
- Model/review/package/binding/query/activation controls (F2B).
- Full responsive audit of all legacy pages (F2C).
- Old page removal or redesign.

---

## F2B (Next)

Goal: Complete the model → validate → pilot loop.

Tasks:
- Model stage: trigger draft generation, view drafts, batch review.
- Validate stage: view quality results, build package, view contract.
- Pilot stage: generate bindings, query runtime, activate pilot.

---

## F2C (Future)

- Full responsive pass on all pages.
- Keyboard navigation audit.
- Accessibility (WCAG AA).
- Consolidate old entry points.
