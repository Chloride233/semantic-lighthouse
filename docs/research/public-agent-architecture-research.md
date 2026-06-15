# Public Agent / Coding Assistant Architecture Research

**Date:** 2026-06-15
**Status:** Complete
**Scope:** 8 public projects/docs researched, 6 dimensions analyzed
**Constraint:** No Claude Code leaked source used — only official docs, public repos

---

## 1. Source Inventory

| # | Project | Source Type | URL / Repository |
|---|---------|-------------|------------------|
| 1 | **ECC** (Enterprise Claude Code) | Open-source harness | `https://github.com/affaan-m/ECC` |
| 2 | **Anthropic Claude Code** | Official documentation | `https://docs.anthropic.com/en/docs/claude-code` |
| 3 | **OpenAI Agents SDK** | Open-source SDK | `https://github.com/openai/openai-agents-python` |
| 4 | **LangGraph** | Open-source framework | `https://github.com/langchain-ai/langgraph` |
| 5 | **AutoGen** (Microsoft) | Open-source framework | `https://github.com/microsoft/autogen` |
| 6 | **Continue.dev** | Open-source IDE agent | `https://github.com/continuedev/continue` |
| 7 | **Aider** | Open-source CLI agent | `https://github.com/Aider-AI/aider` |
| 8 | **OpenHands** | Open-source SDK + paper | `https://github.com/All-Hands-AI/OpenHands`, arXiv:2511.03690 |

**Additional references:**
- OpenAI Codex CLI: `https://github.com/openai/codex` (Rust-based, Apache 2.0)
- Anthropic Agent SDK: `https://docs.anthropic.com/en/docs/agents-and-tools`

---

## 2. Architecture Pattern Comparison

### 2.1 Agent Workflow Organization

| Project | Workflow Model | Planning | Execution | Verification |
|---------|---------------|----------|-----------|-------------|
| **ECC** | Sequential orchestration: Research → Plan → Implement → Review → Verify | Dedicated `planner`/`architect` agents (Opus) | `tdd-guide` agent (Sonnet) | `code-reviewer` + `build-error-resolver` + `e2e-runner` |
| **Claude Code** | Plan → Execute → Verify loop | Natural language → plan → code | Multi-file edit + tool use | Hooks validate output; `/compact` preserves context |
| **OpenAI Agents SDK** | `Agent` + `Runner` loop: turns until final_output | LLM decides via tools/handoffs | Agent invokes tools, `max_turns` safety limit | Guardrails (input/output/tool tiers) + HITL approval |
| **LangGraph** | StateGraph: nodes + edges + conditional routing | Agent node calls LLM, conditional edge routes | Tool node executes | Human-in-the-loop via `interrupt_before`/`interrupt_after` |
| **AutoGen 0.4** | Event-driven AgentRuntime; pub/sub message routing | Selective Speaker LLM routing in GroupChat | CodeExecutorAgent in Docker sandbox | HumanAgent + Interruption mechanism |
| **Continue.dev** | Chat / Agent / Plan / Background modes | Plan mode: plan steps first, then execute | Agent tools (readFile, runTerminal, editFile, etc.) | ToolPolicy security checks per invocation |
| **Aider** | Single LLM call per turn: edit → lint → test → commit | Architect model plans, Editor model executes | Search/replace blocks applied atomically | Lint check → test suite → auto-fix loop (max 3 retries) |
| **OpenHands** | Event-driven: observe → plan → act → observe | LLM reasons and emits ActionEvents | Tools execute in optional Docker sandbox | SecurityAnalyzer + ConfirmationPolicy interleaved |

**Key Insight:** All systems use some form of **plan → execute → verify** loop. The difference is in **granularity**: Aider uses single-turn (least agentic), OpenHands uses persistent event loop (most agentic). Semantic Lighthouse's current "stateless RAG answer" model is simpler than all of these — the path to Agent workflow is adding a **stateful loop with tool execution feedback**.

### 2.2 Context Management & Handoff

| Project | Context Strategy | Handoff Mechanism | Resilience |
|---------|-----------------|-------------------|------------|
| **ECC** | PreCompact/Stop hooks persist state; SessionStart loads past context; `/clear` between phases | Agent output files (`.md`) pass state between phases | `$ECC_AGENT_DATA_HOME/session-data/` with retention |
| **Claude Code** | CLAUDE.md (user-written) + Auto Memory (AI-generated) loaded each session; `/compact` condenses history; `--teleport` cross-device | Sub-agents get new context + task description; Memory files (`project`/`user`/`local` scope) | MEMORY.md per-project; agent-memory directories |
| **OpenAI Agents SDK** | Dual context: `RunContextWrapper[T]` (app state, NOT sent to LLM) vs conversation history (LLM-visible); Sessions (SQLite/Redis/PG) auto-save/load | `Agent.as_tool()` (manager pattern) + handoffs (decentralized); `input_filter` controls what history transfers; `nest_handoff_history` (beta) folds prior convos into summary | `RunState.to_json()` serializable; `SessionSettings(limit=N)` |
| **LangGraph** | Shared State object across nodes; checkpoint after each super-step to SQLite/PG; `thread_id` isolation | Sub-graphs as nodes; conditional edges for dynamic routing; Supervisor/Hierarchical/Swarm patterns | Durable execution: resume from any checkpoint; time-travel to prior states |
| **AutoGen 0.4** | ChatCompletionContext (buffered/token-limited); Memory Store (vector DB for long-term) | Pub/sub message routing via AgentId; AgentRuntime manages lifecycle | AgentState save/restore; persistent AgentRuntime |
| **Continue.dev** | ChatHistoryItem with full contextItems, toolCallStates, reasoning, appliedRules; session save/load | Context Providers (@-mention system); 30+ built-in providers | Session persistence; `conversationSummary` compaction |
| **Aider** | Repo Map (global structure, low token) + relevant files + conversation history | N/A — single agent, no handoff | Git commits as state boundaries |
| **OpenHands** | Event-sourced: immutable Event log with CondensationEvents; full log always preserved; LLM sees condensed view | Sub-agent delegation as standard tools; blocking parallel execution; child inherits model + workspace | Event log supports deterministic replay; conversation state is sole mutable entity |

**Key Insight for Semantic Lighthouse:** The project already has `conversation_messages` persistence (Phase 4), `rag_runs` audit trail (Phase 3), and `agent-handoff.md` for inter-session context. The next layer is:
- **Auto-memory**: Let the agent remember per-project facts (like Claude Code's Auto Memory / ECC's Instinct system)
- **Context condensation**: When conversation history exceeds model context window (OpenHands Condenser pattern)
- **Handoff payload validation**: When sub-agents pass control, validate the structured handoff data (OpenAI `input_filter` pattern)

### 2.3 Tool Permission Boundaries

| Project | Permission Model | Granularity | Sandbox |
|---------|-----------------|-------------|---------|
| **ECC** | Agent-level `tools: [Read, Grep, Glob]` in YAML frontmatter; Hook-level PreToolUse/PostToolUse gating; Security deny baseline | Per-tool, per-agent, per-hook | AgentShield scanning; GateGuard for destructive ops |
| **Claude Code** | `Allow`/`Ask`/`Deny` rules with tool+specifier matching (e.g., `Bash(npm run *)`); `deny → ask → allow` priority | Per-tool, per-command-pattern, per-file-path | OS-level sandbox for Bash; `bypassPermissions` has hardcoded safety circuits |
| **OpenAI Agents SDK** | Input guardrails (parallel/blocking) + Output guardrails + Tool guardrails; `TripwireTriggered` exception stops execution | Per-guardrail, per-tool, per-agent | HITL `needs_approval=True` on tools; `RunState` pause/resume |
| **LangGraph** | Developer-controlled in tool nodes; `interrupt_before`/`interrupt_after` for human review | Per-node in graph | No built-in sandbox; relies on developer implementation |
| **AutoGen 0.4** | Tool Registry with agent binding; CodeExecutorAgent in Docker; Tool execution results via message passing (auditable) | Per-tool binding to agent | Docker sandbox with custom images; timeout control |
| **Continue.dev** | `ToolPolicy` evaluation before execution; `evaluateToolCallPolicy` + `preprocessArgs`; tool states: generated → calling → done/errored | Per-tool-call | `@continuedev/terminal-security` package |
| **Aider** | Read-only by default; user must explicitly `/add` files for editing; git as safety net | Per-file (read vs. write) | No sandbox; trust in git rollback |
| **OpenHands** | `SecurityAnalyzer` (risk: low/medium/high) + `ConfirmationPolicy` (threshold-based); `SecretRegistry` with output masking | Per-Action risk assessment | Optional Docker Workspace; local mode for trusted environments |

**Key Insight for Semantic Lighthouse:** The project already has `group_id` data isolation (hard invariant). For Agent tool permissions:
- **Tool registration table**: Register available tools per-agent, like ECC's `tools` field and AutoGen's Tool Registry
- **Risk-tiered confirmation**: Adopt OpenHands' `SecurityAnalyzer` pattern — categorize tool calls by risk, auto-approve low-risk, require confirmation for high-risk
- **Read-only mode**: Like Claude Code's `plan` mode and Aider's read-only default — a mode where the Agent can explore but not mutate

### 2.4 Engineering Memory & Project Rules

| Project | Memory System | Rules System | Learning/Evolution |
|---------|--------------|-------------|-------------------|
| **ECC** | Instinct architecture: atomic learning units with confidence scores (0.3–0.9); project-scoped by default, global after 2+ project confirmation | Layered rules: `common/` + 12 languages; language-specific overrides general; `@path/to/file.md` imports | `/evolve` clusters instincts → skills/commands/agents; continuous-learning-v2 skill |
| **Claude Code** | CLAUDE.md (user-written, declarative) + Auto Memory (AI-written, `~/.claude/projects/<hash>/memory/`); MEMORY.md loaded at session start (first 200 lines) | `~/.claude/rules/` (user) + `.claude/rules/` (project); path-scoped via YAML frontmatter `paths:`; file imports with `@` syntax, max depth 4 | Auto Memory: Claude autonomously decides what to remember; per-project isolation |
| **OpenAI Agents SDK** | Sessions (SQLite/Redis/PG/SQLAlchemy); `SessionSettings(limit=N)`; `OpenAIResponsesCompactionSession` for auto-summarization | Instructions (static or callable); `prompt` dict for OpenAI platform templates | No built-in learning; session persistence is the extent of memory |
| **LangGraph** | Checkpoint-based persistence; thread-level isolation; shared State object | No explicit rules system; developer controls via node logic | No built-in learning |
| **AutoGen 0.4** | ChatCompletionContext (sliding window) + Memory Store (vector DB); AgentState save/restore | No explicit rules system; system_message per agent | Teachability (experimental): store learnings to vector DB |
| **Continue.dev** | Session persistence with full ChatHistoryItem metadata; Token usage tracking | 4-tier rules: colocated `rules.md` (with YAML frontmatter) → workspace `.continuerules` → config `rules` block → model `baseAgentSystemMessage` | `CodebaseRulesCache` auto-reloads on file change |
| **Aider** | Conversation history + Repo Map per session; no persistent memory | `.aider.conf.yml` configuration; `--lint-cmd` and `--test-cmd` as quality rules | No built-in learning |
| **OpenHands** | Event log (immutable, complete); CondensationEvents for summarization; full log always preserved | Micro-agents in `.openhands/microagents/` (Markdown with optional `triggers` frontmatter); `AgentContext` with prefix/suffix/Skill objects | No built-in learning; event log enables post-hoc analysis |

**Key Insight for Semantic Lighthouse:** The project already has a strong memory foundation:
- `docs/engineering-memory/` with pitfall log, highlight log, learning index, version retros
- `CLAUDE.md` with read order and working rules
- `docs/agent-handoff.md` for inter-session context

The next step is **auto-memory**: let the agent write its own memory files (like Claude Code's Auto Memory pattern). The `docs/engineering-memory/` structure is already well-suited for this — it just needs a mechanism for the agent to append observations during runtime, not just after the fact.

### 2.5 Review / Test / Commit Quality Gates

| Project | Review | Test | Commit | Gate Architecture |
|---------|--------|------|--------|-------------------|
| **ECC** | `code-reviewer` agent with confidence-filtered findings (>80% certainty); CRITICAL→HIGH→MEDIUM→LOW severity | TDD mandatory: RED→GREEN→REFACTOR; 80% min coverage; language-specific test skills | Conventional commits (`feat:`, `fix:`, etc.); `quality-gate` command for formatting | Multi-gate: confidence filter → severity filter → formatting gate |
| **Claude Code** | Hooks validate output; `PostToolUse` runs lint/format; `Stop` hook checks tests passing, no debug code | Hooks can run test suites; `SubagentStop`/`TeammateIdle` check quality before agent stops | Git operations via natural language; commits generated by Claude | Hook lifecycle: PreToolUse → PostToolUse → Stop (3-tier gate) |
| **OpenAI Agents SDK** | Output guardrails validate final output; tool guardrails validate each tool call result | No built-in test runner; HITL `needs_approval=True` for critical ops | No built-in git integration | Guardrail tiers: input → tool → output (3-tier defense) |
| **LangGraph** | `interrupt_before` for human review at any node | No built-in test runner | No built-in git integration | Interrupt points + checkpoint state inspection |
| **AutoGen 0.4** | HumanAgent for approval; `InterventionHandler` for custom approval logic | Docker sandbox captures code execution output for review | No built-in git integration | Interruption mechanism + approval callbacks |
| **Continue.dev** | `viewDiff` tool shows changes before applying; tool states visible in chat | LSP diagnostics integration; `problems` context provider | No built-in git commit (user-driven) | ToolPolicy per-invocation + tool state machine |
| **Aider** | Lint errors fed back to LLM for auto-fix | Test failures fed back to LLM for auto-fix (max 3 retries); full suite run after every edit | Auto `git commit` with LLM-generated conventional commit message; `/undo` via `git reset` | **Lint → Test → Commit** (3-stage pipeline, the most explicit quality gate in the survey) |
| **OpenHands** | `SecurityAnalyzer` evaluates risk before execution; `ConfirmationPolicy` decides if user approval needed | No built-in test runner | No built-in git integration | SecurityAnalyzer + ConfirmationPolicy interleaved in event loop |

**Key Insight for Semantic Lighthouse:** The project already has:
- `pytest` + `ruff check` as local regression gates
- Alembic migration smoke tests
- `scripts/scan_encoding.py` and `scripts/verify_ui.py` for CI guards

The **Aider pattern is the most directly applicable**: after any agent code edit, auto-run lint → auto-run tests → if both pass, auto-commit with generated message. This can be implemented as a simple Python function that wraps the edit tool.

### 2.6 Overall Architecture Comparison (Radar Summary)

| Dimension | Best-in-Class Pattern | Source |
|-----------|----------------------|--------|
| **Workflow** | Sequential phase orchestration with dedicated agents per phase | ECC |
| **Context** | Event-sourced immutable log + condensation for LLM window | OpenHands |
| **Handoff** | Structured handoff with input filters + nested history | OpenAI Agents SDK |
| **Permissions** | Deny → Ask → Allow priority with tool+specifier matching | Claude Code |
| **Memory** | Auto-memory with confidence scoring + project scope isolation | ECC (Instinct) / Claude Code (Auto Memory) |
| **Rules** | Multi-tier rules: common → language → project → model | ECC / Claude Code / Continue.dev |
| **Quality Gate** | Lint → Test → Commit pipeline with auto-fix feedback loop | Aider |
| **Sandbox** | Optional Docker workspace with SecurityAnalyzer | OpenHands / AutoGen |
| **Observability** | Trace/Span auto-instrumentation + batch async export | OpenAI Agents SDK |

---

## 3. Adoptable Design Inventory (适合语义灯塔的设计)

### 3.1 Low-Hanging Fruit (低成本高收益)

| # | Pattern | Source | How to Apply | Effort |
|---|---------|--------|---------------|--------|
| 1 | **Repo Map** | Aider | Build a lightweight tree-sitter-based codebase structure index (~500 tokens) for agent context. Already partially exists via document chunk tree. | S |
| 2 | **Multi-tier Rule Priority** | ECC / Claude Code | Formalize current CLAUDE.md → `docs/engineering-memory/` → `.claude/rules/` priority chain with explicit override semantics | S |
| 3 | **Tool Permission Labels** | ECC | Add a `tools: [list]` field to agent definitions; the orchestrator checks before delegating any tool | S |
| 4 | **Auto-commit with Conventional Message** | Aider | After any agent code edit that passes lint+test, generate a conventional commit message and `git commit` | S |
| 5 | **Confidence-Filtered Agent Output** | ECC (code-reviewer) | When agent generates findings/risks, include `confidence: 0.0–1.0` and filter below a threshold before presenting to user | S |

### 3.2 Medium Investment (需要一定架构调整)

| # | Pattern | Source | How to Apply | Effort |
|---|---------|--------|---------------|--------|
| 6 | **Auto Memory Files** | Claude Code | Let the agent write `docs/engineering-memory/auto/` files during runtime — observations, patterns, corrections. Load at session start. Cross-reference with [[wikilinks]]. | M |
| 7 | **Edit → Lint → Test Feedback Loop** | Aider | When the agent edits code, immediately run `ruff check` on changed files; if lint fails, feed errors back to LLM; then run `pytest`; max 3 retries | M |
| 8 | **Risk-Tiered Tool Approval** | OpenHands | Categorize agent tools by risk (read-only=low, file-write=medium, shell-exec=high, db-migrate=critical). Auto-approve low; require confirmation for high+ | M |
| 9 | **Session Checkpoint / Resume** | LangGraph / OpenAI | Persist agent run state to DB (already have `rag_runs`). Add `status: paused` state and `resume_run` endpoint for long-running agent tasks | M |
| 10 | **Structured Handoff Input** | OpenAI Agents SDK | When delegating between agent phases, pass a validated Pydantic model (not free text); reject handoff if schema validation fails | M |

### 3.3 Strategic Investments (架构级变化)

| # | Pattern | Source | How to Apply | Effort |
|---|---------|--------|---------------|--------|
| 11 | **Event-Sourced Agent Log** | OpenHands | Maintain immutable `agent_events` table: every agent action/observation/error as an append-only event. Enables deterministic replay and full audit. | L |
| 12 | **Dual Context: App State vs LLM Context** | OpenAI Agents SDK | Separate what the agent runtime knows (group_id, user permissions, DB connections) from what the LLM sees (conversation history, retrieved docs). Enforce at SDK level. | L |
| 13 | **Agent Sandbox via Docker** | OpenHands / AutoGen | For risky operations (code execution, SQL queries, file system mutations), route through a Docker workspace with resource limits and network isolation | L |

---

## 4. Designs NOT Suitable for Current Phase

| # | Pattern | Source | Why Not Now | When to Revisit |
|---|---------|--------|-------------|-----------------|
| 1 | **LangGraph StateGraph + Checkpointing** | LangGraph | Project explicitly chose lightweight FSM over LangGraph in Phase 7. The graph complexity isn't justified for linear agent pipelines. | When agent workflows become DAG-shaped (branching, parallel execution, conditional routing across 3+ paths) |
| 2 | **AutoGen 0.4 Event-Driven AgentRuntime** | AutoGen | Pub/sub message routing + AgentRuntime is heavy infrastructure. Current project has ~5 agent phases max. | When agent count exceeds ~10 with dynamic discovery and cross-agent messaging |
| 3 | **OpenAI Hosted Tools (WebSearch, CodeInterpreter, FileSearch)** | OpenAI Agents SDK | These are OpenAI-platform-specific hosted tools. Semantic Lighthouse uses DeepSeek/Aliyun providers and needs provider-agnostic tools. | When OpenAI becomes a supported provider |
| 4 | **Continue.dev IDE Extension Architecture** | Continue.dev | The project is a web application, not an IDE plugin. The Core/IDE separation pattern is relevant but the VS Code/JetBrains extension architecture is not. | If the project adds an IDE plugin for direct knowledge base access |
| 5 | **MCP Server Ecosystem** | Claude Code / Continue.dev | MCP adds significant context window cost (each server adds tool definitions). Project currently keeps MCP surface minimal by design. | When a concrete integration need (e.g., PostgreSQL MCP for inline DB queries) justifies the token budget |
| 6 | **AutoGen Studio (Web UI for Agent Building)** | AutoGen | The project's agent workflows are purpose-built, not user-configurable. A visual agent builder is premature. | When the product becomes a platform where non-developers configure agents |
| 7 | **ECC Instinct Evolution Pipeline** | ECC | Atomic learning units + confidence scoring + cross-project promotion is overengineered for a single-project internship demo. | When managing 3+ projects with shared learnings |
| 8 | **OpenHands VSCode Web + VNC Desktop in Sandbox** | OpenHands | Full browser IDE + desktop in Docker is extreme overkill for a RAG pipeline | Only if the project pivots to a full cloud development environment |

---

## 5. Semantic Lighthouse Minimal Landing Plan

### 5.1 Current Architecture Assessment

Semantic Lighthouse already has solid foundations that align with best practices from the research:

| Existing Feature | Maps To | Maturity |
|-----------------|---------|----------|
| `docs/agent-handoff.md` | Claude Code handoff + ECC session data | ✅ Good |
| `docs/engineering-memory/` (pitfall, highlight, learning index, retros) | ECC Instinct / Claude Code Auto Memory | ✅ Good structure |
| `CLAUDE.md` with read order + working rules | Claude Code project rules | ✅ Good |
| `rag_runs` audit table | LangGraph checkpointing / OpenAI tracing | ✅ Good |
| `group_id` isolation | All permission systems' data isolation | ✅ Hard invariant |
| `pytest` + `ruff check` gates | Aider lint+test pipeline | ✅ Good |
| Alembic migration smoke | Database integrity gate | ✅ Good |
| `scan_encoding.py` + `verify_ui.py` | CI quality gates | ✅ Good |

### 5.2 Phase 7.5: Agent Eval Set → Agent Foundation (Recommended Next)

Based on the research, the minimal path to "Agent-capable" without over-engineering:

**Step 1: Auto Memory (1 session)**
- Create `docs/engineering-memory/auto/` directory
- Agent writes observation files during runtime (frontmatter: name, description, type)
- Load auto-memory at session start alongside handoff snapshot
- Mirror: Claude Code Auto Memory pattern

**Step 2: Tool Registry + Risk Labels (1 session)**
- Define available agent tools in a `ToolRegistry` class
- Each tool has: name, description, JSON Schema params, risk_level (low/medium/high/critical)
- The orchestrator checks risk before delegating
- Mirror: ECC `tools` field + OpenHands `SecurityAnalyzer`

**Step 3: Edit → Lint → Test Feedback Loop (1 session)**
- After any file write by agent: run `ruff check` on changed files
- If lint fails: append errors to LLM context, request fix (max 3 rounds)
- After lint passes: run `pytest` on affected tests
- If tests fail: append failures to LLM context, request fix (max 3 rounds)
- Mirror: Aider's core loop

**Step 4: Auto-Commit Gate (1 session)**
- After lint + test pass: generate conventional commit message via LLM
- Execute `git add` + `git commit`
- Mirror: Aider's auto-commit pattern

**Step 5: Agent Eval Set (Phase 7.5 as planned)**
- Design multi-step task scenarios
- Measure: task completion rate, tool call accuracy, error recovery rate
- Use the quality gates from Steps 2-4 as eval criteria

### 5.3 What NOT to Build Now
- No LangGraph/StateGraph integration (stay with lightweight FSM)
- No Docker sandbox (not needed until code execution is a feature)
- No multi-agent message bus (not needed for <5 agent types)
- No event sourcing rewrite (current `rag_runs` audit is sufficient)

---

## 6. Next Steps & Recommendations

### 6.1 Immediate Actions (This Iteration)
1. ✅ **This report** — done
2. Commit: `docs: add public agent architecture research report`
3. Update `docs/agent-handoff.md` with research findings and revised next steps

### 6.2 Recommended Next Iteration (Owner's Choice)
- **Option A**: Execute Phase 7.5 Agent Eval Set (as planned in roadmap)
- **Option B**: Implement Steps 1-2 above (Auto Memory + Tool Registry) as Agent foundation
- **Option C**: Cloud deployment + real provider integration (as listed in handoff)

### 6.3 Research Maintenance
- This report should be revisited when:
  - Adding a new agent type or tool category
  - Agent workflows become non-linear (branching, parallel, multi-agent)
  - A new major version of any surveyed project is released
  - The project owner needs interview stories about architecture decisions

### 6.4 Key Takeaway
The research confirms that Semantic Lighthouse's current architecture choices (lightweight FSM over LangGraph, SQLAlchemy persistence over event sourcing, manual memory over auto-learning) are **correct for the current phase**. The surveyed projects validate that these are the right simplifications for a pre-product-market-fit system. When the system needs to scale in complexity, the upgrade paths are clear and well-documented in this report.

---

**Report Authorship:** Researched by 8 parallel sub-agents, synthesized and written by Claude Code.
**Research Date:** 2026-06-15
**Sources Verified:** All 8 sources accessed via public URLs, official documentation, and open-source repositories. No leaked or non-public code used.
