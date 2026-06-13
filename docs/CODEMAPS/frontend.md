<!-- Generated: 2026-06-13 | Updated: R1 redesign | Files: 20 | ~550 tokens -->

# Frontend Console (R1 Redesign)

## Stack

Vanilla JS ES Modules + Hash Router + CSS Custom Properties. Zero npm/build. Served by FastAPI StaticFiles at `/console`.

## R1 Route Map

| Hash | Page | Key API Calls | Notes |
|------|------|---------------|-------|
| `#/login` | auth.js | POST /auth/register, POST /auth/login, GET /auth/me | Tabbed Sign In / Register |
| `#/onboarding` | onboarding.js | POST /groups | First-use workspace creation |
| `#/ask` | ask.js | POST /groups/:gid/rag/answer, GET /rag/runs | **Primary home** |
| `#/groups` | groups.js | GET /auth/me, POST /groups, POST /groups/join-by-invite | Linked as "Workspace" |
| `#/groups/:gid/documents` | documents.js | GET /search, POST /upload, POST /{doc}/archive | Linked as "Knowledge" |
| `#/groups/:gid/jobs` | jobs.js | GET /search + GET /{doc}/ingestion-jobs | Not in navbar (legacy) |
| `#/groups/:gid/rag` | rag.js | POST /rag/answer, GET /rag/runs | Not in navbar (legacy) |
| `#/groups/:gid/conversations` | conversations.js | GET/POST /conversations, POST /{id}/messages | Linked as "Conversations" |

## File Map

```
static/
├── console.html              Shell (navbar#navbar + outlet#outlet) → loads js/app.js
├── styles.css                Design tokens (teal/amber) + component + page styles (506 lines)
└── js/
    ├── app.js                Entry: route() × 8, initNavbar(), initRouter()
    ├── api.js                fetch wrapper
    ├── router.js             Hash router: pattern→regex, param extraction, 401 redirect
    ├── state.js              Global store: accessToken, currentUser, groups[], currentGroupId, role
    ├── components/
    │   ├── navbar.js         R1: Ask/Knowledge/Conversations/Workspace labels
    │   ├── panel.js          Reusable card: panel(title, body), panelGrid()
    │   ├── badge.js          Badges: statusBadge(status), confidenceBadge(level)
    │   └── answer-card.js    R1: confidence bar + citations + gaps + next steps
    ├── pages/
    │   ├── auth.js           R1: Tabbed Sign In / Register with brand
    │   ├── onboarding.js     R1: First-use workspace creation
    │   ├── ask.js            R1: Primary Q&A home
    │   ├── groups.js         Workspace management (legacy, preserved)
    │   ├── documents.js      Document upload/search/archive (legacy, preserved)
    │   ├── jobs.js           Ingestion job monitor (legacy, preserved)
    │   ├── rag.js            RAG console (legacy, preserved)
    │   └── conversations.js  Multi-turn dialogue (legacy, preserved)
    └── util/
        ├── esc.js            R1: Shared HTML escape utility
        └── toast.js          Toast notifications
```

## R1 Navbar → Routes

| Nav Label | Target Route | Backed By |
|-----------|-------------|------------|
| **Ask** | `#/ask` | ask.js (new) |
| **Knowledge** | `#/groups/:gid/documents` | documents.js (preserved) |
| **Conversations** | `#/groups/:gid/conversations` | conversations.js (preserved) |
| **Workspace** | `#/groups` | groups.js (preserved) |

## State Flow (R1)

```
Login → groups.length > 0 → #/ask (home)
Login → groups.length === 0 → #/onboarding
Onboarding → POST /groups → #/groups/:gid/documents
Logout → #/login
401 → #/login
```

## CSS Design System (R1)

**Direction**: "Warm Clarity" — guidance, trust, warmth.
**Primary**: Teal `#0d9488`, **Accent**: Amber `#f59e0b`, **Bg**: `#f8faf9`.
Tokens: `--brand`, `--brand-hover`, `--brand-light`, `--accent`, `--accent-light`, `--bg`, `--panel`, `--text`, `--muted`, `--line`, `--ok`, `--warn`, `--danger`, `--info`, shadows, radius, type scale.
