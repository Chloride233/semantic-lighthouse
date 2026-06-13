# Frontend Redesign Plan: Semantic Lighthouse

**Date**: 2026-06-13
**Status**: Plan — Round 1 scope defined, awaiting approval
**Complexity**: Small (6 phases, 4 new files, 4 modified files, 0 deletions)

## Summary — Round 1

Deliver the minimum viable product experience: a warm, professional auth page with brand identity, guided first-use onboarding, a primary "Ask" home page with improved RAG answer display, and a user-task nav bar — all on a new CSS visual system. Keep every existing page intact; add new pages alongside them.

---

## 1. Round 1 Scope Boundary

### ✅ In Scope

| # | Deliverable | Detail |
|---|-------------|--------|
| 1 | **CSS visual system** | New design tokens, typography, spacing, component styles. All existing pages inherit new look automatically. |
| 2 | **Auth page productized** | Tabbed Sign In / Register, brand mark + tagline, success feedback, post-login routing |
| 3 | **Onboarding page** | Guided "create your first workspace" for 0-group users |
| 4 | **Ask page (HOME)** | New `ask.js` — primary Q&A experience with improved answer display. Replaces `/groups/:gid/rag` as the home destination. |
| 5 | **Navbar relabeled** | Ask / Knowledge / Conversations / Workspace — but each links to an existing page that already works |
| 6 | **`esc.js` utility** | Shared HTML escape, imported by all pages (dedup from 7 copies) |

### ❌ Out of Scope (Round 2+)

| Item | Why deferred |
|------|-------------|
| Delete rag.js / groups.js / jobs.js | Keep as fallback; may add redirects if needed |
| Knowledge page merge (docs + jobs) | Jobs stays its own page, Knowledge = existing documents page |
| Conversations two-panel | Current list → chat flow stays; only gets new styles |
| Full Workspace member management | Workspace nav item links to existing groups page |
| Backend API changes | Zero |
| Dark mode, animations beyond CSS transitions | Deferred |

### Old Pages: Compatibility Strategy

| Old Route | Round 1 Action |
|-----------|----------------|
| `#/groups/:gid/rag` | Still works via rag.js. Not linked from navbar. |
| `#/groups/:gid/jobs` | Still works via jobs.js. Not linked from navbar (accessible from Knowledge page if needed). |
| `#/groups` | Still works via groups.js. Linked from "Workspace" nav. |
| `#/groups/:gid/documents` | Still works via documents.js. Linked from "Knowledge" nav. |
| `#/groups/:gid/conversations` | Still works via conversations.js. Linked from "Conversations" nav. |
| `#/login` | Rewritten (auth.js). |

The old routes remain functional — they just lose their navbar prominence in favor of the new user-task labels.

---

## 2. Route Map — Round 1

```
#/login          → Auth (NEW: tabbed, branded)
#/onboarding     → NEW: first-use workspace creation
#/ask            → NEW: primary Q&A experience (HOME)

#/groups         → Existing groups page (linked as "Workspace")
#/groups/:gid/documents → Existing documents page (linked as "Knowledge")
#/groups/:gid/conversations → Existing conversations page (linked as "Conversations")
#/groups/:gid/rag → Existing rag page (not linked — superseded by /ask)
#/groups/:gid/jobs → Existing jobs page (not linked — accessible from documents if needed)
```

### Navbar Labels → Route Mapping

| Nav Label | Target Route | Backed By |
|-----------|-------------|-----------|
| **Ask** | `#/ask` | NEW `ask.js` |
| **Knowledge** | `#/groups/:gid/documents` | Existing `documents.js` |
| **Conversations** | `#/groups/:gid/conversations` | Existing `conversations.js` |
| **Workspace** | `#/groups` | Existing `groups.js` |

No "Jobs" or "RAG" in the nav. The Jobs page is accessible as a sub-view from the Knowledge page if the user navigates there explicitly. RAG is superseded by Ask.

---

## 3. Post-Login Flow

```
Login success → GET /auth/me
                       ↓
              ┌─ groups.length === 0 ─→ #/onboarding
              │                              ↓
              │                    create group → #/knowledge
              │                    (with "upload first doc" prompt)
              │
              └─ groups.length > 0 ─→ #/ask  ← PRIMARY HOME
                                         ↓
                                   KB empty? → inline prompt:
                                   "Upload documents to start asking"
```

Old flow (login → `/groups`) is replaced. The Groups page still exists under Workspace but is no longer the first destination.

---

## 4. Page Designs

### 4.1 Auth Page (`#/login`) — Rewritten

**Goal**: Product identity, warm welcome, clear action.

```
┌────────────────────────────────────────────┐
│                                            │
│              🔦  (lighthouse)              │
│                                            │
│        Semantic Lighthouse                 │
│     Enterprise AI Knowledge Advisor        │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  [ Sign In ]    [ Register ]         │  │
│  │  ───────────────────────────────     │  │
│  │                                      │  │
│  │  Email                               │  │
│  │  [____________________________]     │  │
│  │                                      │  │
│  │  Password                            │  │
│  │  [____________________________]     │  │
│  │                                      │  │
│  │  [ Sign In → ]                       │  │
│  │                                      │  │
│  │  No account? Switch to Register tab. │  │
│  └──────────────────────────────────────┘  │
│                                            │
└────────────────────────────────────────────┘
```

- Register tab adds Display Name field, shows success toast + auto-switches to Sign In.
- Form errors display inline below fields, not at the bottom.
- Tagline replaces "Enterprise RAG & Agent Console".

### 4.2 Onboarding Page (`#/onboarding`) — New

**Goal**: One thing only — create first workspace.

```
┌────────────────────────────────────────────┐
│                                            │
│          👋 Welcome!                       │
│                                            │
│     Create a workspace to organize         │
│     your knowledge and start asking        │
│     questions grounded in your documents.  │
│                                            │
│     Workspace Name                         │
│     [  My Team Workspace            ]     │
│                                            │
│     [  Create Workspace  →  ]              │
│                                            │
└────────────────────────────────────────────┘
```

On success: set `currentGroupId` + `currentRole`, navigate to `#/groups/:gid/documents` (Knowledge).

### 4.3 Ask Page (`#/ask`) — New (HOME)

**Goal**: Primary experience. Type question → get answer → see citations, confidence, gaps, next steps.

**With documents:**
```
┌────────────────────────────────────────────┐
│  Ask anything about your knowledge base    │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  [Type your question...        ] [Ask]│  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ── Answer ────────────────────────────── │
│                                            │
│  ████████████░░░░  High confidence (0.89)  │
│                                            │
│  The ETL pipeline processes documents      │
│  through five stages: Extract, Parse,      │
│  Clean, Chunk, and Embed...                │
│                                            │
│  ┌─ Citations ───────────────────────────┐ │
│  │ [1] etl-architecture.md    score 0.92 │ │
│  │     "The ETL pipeline uses a..."      │ │
│  │ [2] ingestion-guide.md     score 0.87 │ │
│  └────────────────────────────────────────┘ │
│                                            │
│  ⚠️ Knowledge Gaps                         │
│  • DOCX table extraction not yet covered   │
│                                            │
│  💡 Suggested Next Steps                   │
│  • Upload data-pipeline.docx               │
│                                            │
│  ── Recent Questions ──────────────────── │
│  • What is the chunking strategy?     🟢  │
│  • How does auth work?                🟡  │
└────────────────────────────────────────────┘
```

**Empty knowledge base:**
```
┌────────────────────────────────────────────┐
│                                            │
│            📄 No documents yet              │
│                                            │
│       Upload documents to your             │
│       knowledge base to get started.       │
│                                            │
│       [ Go to Knowledge → ]                │
│                                            │
└────────────────────────────────────────────┘
```

**Key differences from current rag.js:**
- No method selector — defaults to `hybrid`.
- Answer text at readable size, comfortable line-height.
- Confidence as a visual bar, not a tiny badge.
- Citations as styled expandable cards, not hidden behind `<details>`.
- Knowledge gaps and next steps both visible but distinct.
- Recent questions quick-access list from `/rag/runs`.
- Uses `state.currentGroupId` — no route param needed.

### 4.4 Existing Pages — Visual Only

These pages keep their current JS logic. They get new styles from the updated `styles.css` and a new nav bar. No JS rewrite.

| Page | File | Changes |
|------|------|---------|
| Documents | `documents.js` | None (CSS only) |
| Jobs | `jobs.js` | None (CSS only) |
| Conversations | `conversations.js` | None (CSS only) |
| Groups | `groups.js` | None (CSS only) |
| RAG | `rag.js` | None (CSS only, still functional at old route) |

---

## 5. CSS Visual System — "Warm Clarity"

### 5.1 Design Direction

A lighthouse doesn't feel like a cold server room — it feels like a warm, reliable beacon. The visual direction reflects: guidance, clarity, warmth, trust.

### 5.2 Color Tokens

```css
:root {
  --brand:        #0d9488;  /* teal-600 — fresh, trustworthy */
  --brand-hover:  #0f766e;  /* teal-700 */
  --brand-light:  #f0fdfa;  /* teal-50 */
  --accent:       #f59e0b;  /* amber-500 — lighthouse warmth */
  --accent-light: #fffbeb;  /* amber-50 */
  --bg:           #f8faf9;  /* warm white */
  --panel:        #ffffff;
  --text:         #1e293b;  /* slate-800 */
  --muted:        #64748b;  /* slate-500 */
  --line:         #e2e8f0;  /* slate-200 */
  --ok:           #059669;  /* emerald-600 */
  --warn:         #d97706;  /* amber-600 */
  --danger:       #dc2626;  /* red-600 */
  --info:         #0284c7;  /* sky-600 */
  --shadow-sm:    0 1px 2px rgba(0,0,0,0.04);
  --shadow-md:    0 4px 12px rgba(0,0,0,0.06);
  --shadow-glow:  0 0 0 3px rgba(13,148,136,0.15);
  --radius-sm:    6px;
  --radius-md:    10px;
  --radius-lg:    16px;
}
```

**Why teal**: Not blue (enterprise cliché). Not purple (AI hype). Fresh, healthy, trustworthy. Amber accent adds warmth — like a lighthouse beam.

### 5.3 Typography

```css
--font-sans: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
--text-xs:   0.75rem;   /* badges, meta */
--text-sm:   0.875rem;  /* body, labels */
--text-base: 1rem;      /* default */
--text-lg:   1.125rem;  /* answer text */
--text-xl:   1.25rem;   /* page titles */
--text-2xl:  1.5rem;    /* hero */
--text-3xl:  2rem;      /* brand on auth page */
```

### 5.4 What Changes in styles.css

- Replace all `:root` tokens (colors, shadows, radius).
- Add typography scale CSS variables.
- Update `body` background and font.
- Update `.topbar`, `.navLinks`, `.navBrand` for new brand color.
- Update `button`, `input`, `select` for new tokens.
- Update `.badge*` colors to new palette.
- Update `.chatMsg-*`, `.ragAnswer`, `.citationItem` backgrounds.
- Add `.confidenceBar` for the new confidence display.
- Add `.authPage`, `.authCard`, `.authTabs` for the new auth layout.
- Add `.onboardingPage`, `.askPage`, `.answerCard`, `.citationCard`, `.emptyState` (improved).
- Keep all existing class names working — additive only.

### 5.5 Anti-Patterns Avoided

- ❌ Sidebar layout
- ❌ Dark surfaces
- ❌ Gradient backgrounds on buttons
- ❌ Purple/indigo brand
- ❌ `<details>` as primary citation display

---

## 6. Files Changed — Round 1

### 6.1 New Files

| File | Purpose | ~Lines |
|------|---------|--------|
| `static/js/pages/ask.js` | Primary Q&A home page | ~130 |
| `static/js/pages/onboarding.js` | First-use workspace creation | ~60 |
| `static/js/util/esc.js` | Shared HTML escape utility | ~8 |
| `static/js/components/answer-card.js` | Reusable answer + citations + gaps display | ~60 |

### 6.2 Modified Files

| File | Changes | ~Diff |
|------|---------|-------|
| `static/styles.css` | New tokens, typography, auth/ask/onboarding styles (~300→~480 lines) | +180 |
| `static/js/app.js` | Add 2 routes (`/ask`, `/onboarding`), import new pages + esc | +10 |
| `static/js/components/navbar.js` | New labels: Ask / Knowledge / Conversations / Workspace. No Jobs/RAG. Active highlighting. | ~15 |
| `static/js/pages/auth.js` | Tabbed layout, brand identity, post-login routing to `/ask` or `/onboarding` | ~30 |
| `static/console.html` | Update `<title>` | ~1 |

### 6.3 Unchanged Files

| File | Why |
|------|-----|
| `static/js/pages/rag.js` | Preserved — still works at old route |
| `static/js/pages/groups.js` | Preserved — linked from Workspace nav |
| `static/js/pages/documents.js` | Preserved — linked from Knowledge nav |
| `static/js/pages/jobs.js` | Preserved — not in nav, accessible from documents |
| `static/js/pages/conversations.js` | Preserved — linked from Conversations nav |
| `static/js/router.js` | No changes needed |
| `static/js/state.js` | No changes needed |
| `static/js/api.js` | No changes needed |
| `static/js/components/badge.js` | No changes needed |
| `static/js/components/panel.js` | No changes needed |
| `static/js/util/toast.js` | No changes needed |

---

## 7. What NOT to Do — Round 1

1. No deleting old pages (rag.js, groups.js, jobs.js)
2. No rewriting conversations.js (two-panel layout deferred)
3. No full Workspace page (Workspace nav → existing groups.js)
4. No merging Jobs into Knowledge
5. No backend API changes
6. No npm / build tools / frameworks
7. No dark mode
8. No new MCP servers

---

## 8. Implementation Order — Round 1

| Phase | What | Files | Verify |
|-------|------|-------|--------|
| **1. Foundation** | CSS tokens + typography + `esc.js` | `styles.css`, `util/esc.js` | All existing pages still render correctly with new tokens |
| **2. Auth** | Tabbed Sign In / Register, brand, post-login routing | `auth.js`, `console.html` | Register → success toast → sign in → navigate to correct destination |
| **3. Onboarding** | New onboarding page | `onboarding.js`, `app.js` | 0-group user sees onboarding, creates group, lands on Knowledge |
| **4. Ask (Home)** | New Q&A page + answer-card component | `ask.js`, `answer-card.js`, `app.js` | Question → answer + citations + confidence + gaps + next steps |
| **5. Navbar** | New labels, no Jobs/RAG, active state | `navbar.js` | All nav links work, active highlighting correct |
| **6. Verify** | Run tests, manual walkthrough, visual check | All | 109 tests pass, manual walkthrough green, no visual regressions on old pages |

Each phase is independently verifiable. No phase blocks on a later phase.

---

## 9. Verification

### 9.1 Browser Walkthrough

```
1. Open /console → redirect to #/login
   → See lighthouse brand, tagline, tabbed form

2. Register tab → fill + submit
   → Toast: "Account created! Sign in below."
   → Auto-switches to Sign In tab

3. Sign In → 0 groups → #/onboarding
   → Create workspace → #/groups/:gid/documents
   → Empty state: "Upload your first document"

4. Nav: click "Ask" → #/ask
   → Empty state: "Go to Knowledge"

5. Upload a doc on Knowledge → return to Ask
   → Question input visible, type question
   → Answer renders with confidence bar, citations, gaps, next steps

6. Nav: click "Conversations" → existing conversations page works

7. Nav: click "Workspace" → existing groups page works

8. Switch group via navbar selector → active page updates

9. Logout → #/login

10. Sign in again (has groups) → #/ask (home)
```

### 9.2 Automated Checks

```bash
# Backend tests — must still pass
.\.venv\Scripts\python -m pytest -p no:cacheprovider

# Ruff — must still be clean
.\.venv\Scripts\ruff check src tests

# Old routes still functional
curl -s http://127.0.0.1:8000/console → returns HTML with new title
```

### 9.3 Visual Smoke (Manual)

| # | Check |
|---|-------|
| 1 | Auth page has brand personality, not Swagger-form look |
| 2 | Navbar uses teal brand color, warm white background |
| 3 | Ask page is visually calm and readable |
| 4 | Confidence bar is immediately visible |
| 5 | Citations are styled, not raw `<details>` |
| 6 | Empty states have a clear next action |
| 7 | Old pages (documents, jobs, conversations, groups) still look correct |
| 8 | No "RAG", "Jobs", "Console" in nav labels |
| 9 | Responsive at 768px |
