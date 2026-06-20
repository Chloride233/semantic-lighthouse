# Frontend F2 — Guided Business Pilot Workspace

**Status**: F2A + F2B + F2C complete. Guided Pilot workspace delivered.

**F2B Review fixes**:
- Removed all `location.reload()` — use reloadProject callback instead.
- PK/pid passed as function parameters, not read from location.hash/state.
- buildPackage uses quality.status from API, not DOM query.
- FAIL blocks absolutely, WARN requires explicit user confirm + reason.
- Shared project-dialog.js with focus trap, Escape cleanup, async confirm, error display.
- Validate: errors shown inline (not swallowed with .catch([])), binding issues rendered in page (not alert()), activation checks contract OTs.
- Pilot: inline `<script>` removed, explain toggle via addEventListener, field validation (≥1 field checked), typed JSON filter serialization, scan_truncated warning.
- Container click handler uses stable delegated pattern with cleanup.

**Verification**: verify_ui 47/47, backend pytest 749 passed, E2E 13/13 (5 new F2B tests: owner full closed-loop, real member via invite, WARN/FAIL workflow, project isolation, code quality checks). Screenshots: `.tmp/f2b/` (6 files: model/validate/pilot desktop + mobile, 0 console errors).

Phase 14 established the five-stage business pilot pipeline (goal → data → model → validate → pilot). Frontend F2 gives users a guided single-path workspace to operate it, replacing the flat parallel-feature navigation with a Pilot-first information architecture.

---

## Slices

| Slice | Task | Status |
|-------|------|--------|
| F2A | Pilot entry, project creation, goal + data stage, nav restructure | ✅ Delivered |
| F2B | Model → Validate → Pilot full operation loop (modeling, review, package build, binding, query, activation) | ✅ Delivered |
| F2C | Frontend review, responsive/accessibility polish, old entry points consolidation | ✅ Delivered |

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

## F2B Delivered

Goal: Complete the model → validate → pilot loop. All tasks delivered and verified.

Tasks:
- Model stage: trigger draft generation, view drafts, batch review. ✅
- Validate stage: view quality results, build package, view contract. ✅
- Pilot stage: generate bindings, query runtime, activate pilot. ✅
- WARN/FAIL quality gate: WARN requires confirm + reason; FAIL blocks absolutely. ✅
- Member join-by-invite: real member role verified; can view/query but cannot write. ✅
- Project isolation: A/B projects in same group, no data leakage. ✅
- Code quality: no location.reload, no inline script, no alert, no empty catch. ✅

---

## F2C Delivered

Responsive, accessibility, and visual polish pass. No new features added.

### Responsive
- 1440px, 1024px, 768px, 390px all zero horizontal overflow.
- Group select constrained to max-width: 180px (desktop) / 140px (mobile).
- Checkbox/radio use stable native sizing — no longer inherit full-width input rules.
- Stage rail: horizontal on desktop, vertical on mobile (600px breakpoint).
- Long api_name/hash: `word-break: break-all` + `overflow-wrap: anywhere`.
- Tables scroll within container only — `.tableWrap` + `.queryTableWrap` patterns.
- Dialog fits 390x844 — reduced internal padding at ≤500px.
- Mobile topbar compact — navRight wraps, navContext truncates long names.
- Model review row, stageCTAs, and queryRow stack vertically on mobile.

### Accessibility
- Dialog: `aria-modal="true"`, `aria-labelledby`, focus trap (Tab wraps within dialog), Escape/overlay/cancel all clean up listeners, error has `role="alert"`, focus restored on close.
- More tools dropdown: Enter/Space/ArrowDown to open, Arrow keys to navigate items, Escape to close, `aria-controls` + `aria-labelledby` on menu.
- All profile/contract table `<th>` use `scope="col"`.
- All form controls have associated `<label>` elements.
- focus-visible: 2px solid outline with offset on buttons, links, selects.
- Skip link preserved.

### Visual
- Each stage has one primary action; secondary/danger hierarchy clear.
- Model review row stays on one line on desktop, stacks on mobile.
- Validate quality/contract/binding sections remain scan-friendly.
- Pilot query results + provenance have clear hierarchy.
- No emoji, gradients, glass effects, hero sections, or card-in-card patterns.
- Old pages preserved in "更多工具" dropdown, all functional.

### Screenshots
`.tmp/f2c/` (6 files): model/validate/pilot at desktop (1280px) + mobile (390px).
- Script waits for stage-specific elements (.draftRow for model, .stagePanel for validate, .queryForm for pilot).
- Menu closed and scrolled to top before each capture.
- Programmatic overflow checks (scrollWidth ≤ innerWidth).

### Verification
- E2E: 5 new F2C tests (responsive no-overflow, dialog focus trap + Escape, more tools keyboard nav, table th scope, form control labels).
- verify_ui: 47/47 preserved.
- Screenshot metadata: all 6 files > 0 bytes, scrollWidth ≤ innerWidth, stage elements confirmed.
