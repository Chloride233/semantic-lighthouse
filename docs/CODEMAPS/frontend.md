<!-- Updated: 2026-07-08 | Current snapshot, not generated -->

# Frontend Console

## Stack

Vanilla JavaScript ES modules, hash router, CSS custom properties, and no npm/build step. FastAPI serves the console shell at `/console` through `static/console.html`.

## Route Map

| Hash | Page Module | Primary Purpose |
|------|-------------|-----------------|
| `#/login` | `pages/auth.js` | Sign in/register/logout recovery path |
| `#/onboarding` | `pages/onboarding.js` | First workspace creation |
| `#/ask` | `pages/ask.js` | Lightweight ask/RAG entry |
| `#/groups` | `pages/groups.js` | Workspace selection and membership operations |
| `#/groups/:gid/projects` | `pages/projects.js` | Pilot project list and creation |
| `#/groups/:gid/projects/:pid` | `pages/project.js` | Goal -> Data -> Model -> Validate -> Pilot workflow shell |
| `#/groups/:gid/documents` | `pages/documents.js` | Knowledge upload/search/archive |
| `#/groups/:gid/jobs` | `pages/jobs.js` | Ingestion job monitor, preserved legacy route |
| `#/groups/:gid/rag` | `pages/rag.js` | RAG run console, preserved legacy route |
| `#/groups/:gid/conversations` | `pages/conversations.js` | Multi-turn grounded conversations |
| `#/groups/:gid/tasks` | `pages/tasks.js` | HITL task list and confirmation flow |
| `#/groups/:gid/agent` | `pages/agent.js` | Controlled Agent run interface |
| `#/groups/:gid/ontology` | `pages/ontology.js` | Ontology entities, relations, drafts, packages |

## Current Navigation

Primary navigation favors the ontology pilot surface:

| Label | Target |
|-------|--------|
| Pilot | `#/groups/{gid}/projects` |
| Ontology | `#/groups/{gid}/ontology` |
| 工作区 | `#/groups` |

The more-tools menu keeps supporting routes discoverable: 问答, 知识库, 对话, 任务, Agent.

## File Map

```text
static/
├── console.html              SPA shell
├── styles.css                Design tokens, layout, components, page styles
└── js/
    ├── app.js                Route registration and app bootstrap
    ├── api.js                Fetch wrapper
    ├── router.js             Hash router with route params and auth redirect
    ├── state.js              Shared client state
    ├── components/           Navbar, panels, cards, badges
    ├── pages/                Console page modules
    └── util/                 Escape, task confirmation, ontology links, toast helpers
```

## Design Direction

The console should stay work-focused: quiet navigation, clear evidence surfaces, explicit status, and dense but readable ontology/pilot workflows. Avoid turning the console into a marketing page or a generic chatbot skin.

## Preservation Notes

- Legacy console routes remain active unless a dedicated retirement task handles redirects, tests, and docs.
- UI changes require `scripts\verify_ui.py` plus route-specific browser/Playwright checks for touched flows.
- The deleted `static/learning.html` page was not wired into `static/js/app.js` or the navbar and is not part of the console route contract.
