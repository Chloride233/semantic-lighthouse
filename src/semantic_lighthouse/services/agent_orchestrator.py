"""Agent workflow orchestrator — lightweight state machine.

Plan → Execute → Observe → Conclude, with human-in-the-loop checkpoints.
Zero external framework dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from semantic_lighthouse.models import AgentRun, AgentStep, AgentMemory, utc_now
from semantic_lighthouse.routers._shared import snippet
from semantic_lighthouse.services.retrieval import _keyword_search


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    required_role: str  # "member" | "admin" | "owner"
    is_risky: bool  # True → requires human confirmation


AGENT_TOOLS: list[ToolDef] = [
    ToolDef(
        name="search_knowledge_base",
        description="Search the group's knowledge base with a keyword query.",
        required_role="member",
        is_risky=False,
    ),
    ToolDef(
        name="archive_document",
        description="Archive a document by its title. Removes it from search results.",
        required_role="admin",
        is_risky=True,
    ),
    ToolDef(
        name="list_documents",
        description="List documents in the current group with their status.",
        required_role="member",
        is_risky=False,
    ),
]


def _tool_by_name(name: str) -> ToolDef | None:
    for t in AGENT_TOOLS:
        if t.name == name:
            return t
    return None


def _validate_role(tool: ToolDef, user_role: str) -> bool:
    order = {"member": 0, "admin": 1, "owner": 2}
    return order.get(user_role, -1) >= order.get(tool.required_role, 0)


def execute_tool(
    name: str,
    arguments: dict,
    db: Session,
    group_id: str,
    user_role: str,
    user_id: str | None = None,
) -> str:
    tool = _tool_by_name(name)
    if tool is None:
        return f"Error: unknown tool '{name}'."
    if not _validate_role(tool, user_role):
        return f"Error: '{name}' requires '{tool.required_role}' role."

    if name == "search_knowledge_base":
        query = arguments.get("query", "")
        if not query.strip():
            return "Error: query is required."
        results = _keyword_search(db, group_id, query, limit=5)
        if not results:
            return "No matching documents found."
        lines = []
        for i, item in enumerate(results, start=1):
            lines.append(f"[{i}] {item.document.title}: {snippet(item.chunk.content, query, radius=160)}")
        return "\n".join(lines)

    if name == "list_documents":
        from semantic_lighthouse.models import Document
        from sqlalchemy import select

        docs = db.scalars(
            select(Document)
            .where(Document.group_id == group_id, Document.status.in_(["ready", "uploaded", "processing"]))
            .order_by(Document.created_at.desc())
            .limit(20)
        ).all()
        if not docs:
            return "No documents in this group."
        return "\n".join(f"- [{d.status}] {d.title} ({d.file_name})" for d in docs)

    if name == "archive_document":
        title = arguments.get("title", "")
        if not title.strip():
            return "Error: title is required."
        from semantic_lighthouse.models import Document
        from sqlalchemy import select

        doc = db.scalar(
            select(Document).where(
                Document.group_id == group_id,
                Document.title.ilike(f"%{title}%"),
                Document.status.in_(["ready", "failed"]),
            )
        )
        if doc is None:
            return f"No document matching '{title}' found."
        from semantic_lighthouse.services.document_lifecycle import archive_document
        try:
            archive_document(db, doc, group_id, user_id or "unknown", "Agent confirmed archive")
        except ValueError as exc:
            return f"Error: {exc}"
        return f"Document '{doc.title}' has been archived."

    return f"Error: tool '{name}' has no handler."


def is_risky_tool(name: str) -> bool:
    tool = _tool_by_name(name)
    return tool.is_risky if tool else False


# ── Agent LLM Tool Loop (V2.1) ───────────────────────────────────────


@dataclass(frozen=True)
class AgentDecision:
    """LLM decision in the agent loop — call_tool or finalize."""
    thought: str
    action: str  # "call_tool" | "finalize"
    tool_name: str = ""
    tool_arguments: dict | None = None
    final_answer: str | None = None
    raw_response: str | None = None

    def __post_init__(self):
        if self.action == "call_tool" and not self.tool_name:
            raise ValueError("action=call_tool requires tool_name")


MAX_AGENT_STEPS = 5


def agent_loop(
    db: Session,
    run: AgentRun,
    group_id: str,
    user_role: str,
    decide_fn,
    max_steps: int = MAX_AGENT_STEPS,
) -> AgentStep | None:
    """Execute the agent decision loop until completed, stopped, or failed.

    Each iteration: check max_steps -> build messages -> decide -> execute.
    Risky tools pause the loop (awaiting_confirmation). Caller resumes via
    subsequent execute calls.
    """
    tool_schemas = _tool_schemas_for_llm()
    consecutive_errors = 0
    last_step = None

    while True:
        step_count = _count_agent_steps(run)
        if step_count >= max_steps:
            events: list = list(run.plan_json or [])
            events.append({
                "type": "stopped", "reason": "max_steps",
                "step_count": step_count, "max_steps": max_steps,
                "recorded_at": utc_now().isoformat(),
            })
            run.plan_json = events
            run.status = "stopped"
            run.current_phase = "conclude"
            run.final_answer = f"Agent reached max steps ({max_steps})."
            run.finished_at = utc_now()
            run.updated_at = utc_now()
            db.commit()
            return last_step

        messages = _build_agent_messages(run)
        decision = decide_fn(messages, tool_schemas)
        step_idx = len(run.steps) if run.steps else 0

        _record_plan_event(run, decision, step_idx)
        raw = decision.raw_response or ""
        if decision.action == "finalize":
            step = add_step(
                db, run, phase="execute", step_index=step_idx,
                thought=decision.thought, action_type="llm_decision",
                action_detail=_decision_detail(decision, raw),
                observation=f"Final answer: {(decision.final_answer or '')[:100]}",
                status="completed",
            )
            db.commit()
            finalize_run(db, run, decision.final_answer or "Agent completed.", [])
            db.refresh(step)
            return step

        if decision.action == "call_tool":
            tool_name = decision.tool_name
            tool_args = decision.tool_arguments or {}
            tool = _tool_by_name(tool_name)
            if tool is None:
                step = add_step(
                    db, run, phase="execute", step_index=step_idx,
                    thought=decision.thought, action_type="tool_call",
                    action_detail={"tool": tool_name, "arguments": tool_args},
                    observation=f"Error: unknown tool '{tool_name}'.",
                    error_message=f"Tool '{tool_name}' not in AGENT_TOOLS.",
                    status="failed",
                )
                db.commit()
                last_step = step
                continue

            if tool.is_risky:
                run.status = "awaiting_confirmation"
                run.current_phase = "execute"
                run.updated_at = utc_now()
                step = add_step(
                    db, run, phase="execute", step_index=step_idx,
                    thought=decision.thought, action_type="ask_user",
                    action_detail={
                        "tool": tool_name, "arguments": tool_args,
                        "needs_confirmation": True,
                        "requires_confirmation": True,
                        "risk_level": "high",
                        "confirmation_reason": f"Tool '{tool_name}' can change group data.",
                        "raw_llm_response": raw[:500],
                    },
                    observation=f"Waiting for user confirmation to execute '{tool_name}'.",
                    status="running",
                )
                db.commit()
                db.refresh(step)
                return step

            result = execute_tool(tool_name, tool_args, db, group_id, user_role, run.user_id)
            step = add_step(
                db, run, phase="execute", step_index=step_idx,
                thought=decision.thought, action_type="tool_call",
                action_detail={
                    "action": "call_tool", "tool": tool_name, "arguments": tool_args,
                    "raw_llm_response": raw[:500],
                },
                observation=result,
                status="completed" if not result.startswith("Error:") else "failed",
                error_message=result if result.startswith("Error:") else None,
            )
            db.commit()

            if result.startswith("Error:"):
                consecutive_errors += 1
                if consecutive_errors >= 2:
                    fail_run(db, run, f"Agent failed: {consecutive_errors} consecutive tool errors.")
                    db.refresh(step)
                    return step
            else:
                consecutive_errors = 0

            last_step = step
            continue

        # Unknown action -> treat as finalize
        step = add_step(
            db, run, phase="execute", step_index=step_idx,
            thought=decision.thought, action_type="llm_decision",
            action_detail={"action": decision.action},
            observation=f"Unknown action '{decision.action}', treating as finalize.",
            status="completed",
        )
        db.commit()
        finalize_run(db, run, decision.final_answer or "Agent completed.", [])
        db.refresh(step)
        return step


def _count_agent_steps(run: AgentRun) -> int:
    if not run.steps:
        return 0
    return sum(1 for s in run.steps if s.action_type != "think")


def _build_agent_messages(run: AgentRun) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _agent_system_prompt()},
        {"role": "user", "content": f"Goal: {run.goal}"},
    ]
    for s in (run.steps or []):
        if s.action_type == "tool_call" and s.observation:
            messages.append({
                "role": "assistant",
                "content": f"Tool {s.action_detail.get('tool', '?')} result: {s.observation}",
            })
        elif s.action_type == "ask_user" and s.observation:
            messages.append({
                "role": "assistant",
                "content": s.observation,
            })
    return messages


def _agent_system_prompt() -> str:
    return (
        "你是一个企业 AI 咨询 Agent。根据用户目标决定下一步。"
        "可用工具见 tool schemas。"
        "返回 JSON：{\"thought\":\"...\",\"action\":\"call_tool\","
        "\"tool_name\":\"...\",\"tool_arguments\":{...}}"
        " 或 {\"thought\":\"...\",\"action\":\"finalize\",\"final_answer\":\"...\"}"
        "。如果 observation 含 Error，尝试改参数重试一次。"
    )


def _record_plan_event(run: AgentRun, decision: AgentDecision, step_index: int) -> None:
    events: list = list(run.plan_json or [])
    events.append({
        "type": "llm_decision",
        "step_index": step_index,
        "thought": decision.thought[:200],
        "action": decision.action,
        "tool": decision.tool_name or None,
        "tool_arguments": decision.tool_arguments,
        "final_answer_preview": (decision.final_answer or "")[:100] if decision.final_answer else None,
        "recorded_at": utc_now().isoformat(),
    })
    run.plan_json = events


def _decision_detail(decision: AgentDecision, raw: str) -> dict:
    base: dict = {"action": decision.action, "raw_llm_response": raw[:500]}
    if decision.action == "call_tool":
        base["tool"] = decision.tool_name
        base["arguments"] = decision.tool_arguments
    return base


def _tool_schemas_for_llm() -> list[dict]:
    schemas = []
    for t in AGENT_TOOLS:
        props: dict = {}
        required: list[str] = []
        if t.name == "search_knowledge_base":
            props["query"] = {"type": "string", "description": "Search query"}
            required.append("query")
        elif t.name == "archive_document":
            props["title"] = {"type": "string", "description": "Document title"}
            required.append("title")
        elif t.name == "list_documents":
            pass
        schemas.append({
            "type": "function", "function": {
                "name": t.name, "description": t.description,
                "parameters": {"type": "object", "properties": props, "required": required},
            },
        })
    return schemas


def create_run(
    db: Session,
    group_id: str,
    user_id: str,
    goal: str,
    conversation_id: str | None = None,
    project_id: str | None = None,
) -> AgentRun:
    run = AgentRun(
        group_id=group_id,
        user_id=user_id,
        project_id=project_id,
        conversation_id=conversation_id,
        goal=goal,
        status="planning",
        current_phase="plan",
        plan_json=[],
        citations=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def add_step(
    db: Session,
    run: AgentRun,
    phase: str,
    step_index: int,
    thought: str,
    action_type: str,
    action_detail: dict,
    status: str = "completed",
    observation: str | None = None,
    error_message: str | None = None,
) -> AgentStep:
    step = AgentStep(
        run_id=run.id,
        phase=phase,
        step_index=step_index,
        thought=thought,
        action_type=action_type,
        action_detail=action_detail,
        observation=observation,
        status=status,
        error_message=error_message,
        started_at=utc_now(),
        finished_at=utc_now() if status in ("completed", "failed") else None,
    )
    db.add(step)
    return step


def finalize_run(db: Session, run: AgentRun, final_answer: str, citations: list) -> None:
    run.status = "completed"
    run.current_phase = "conclude"
    run.final_answer = final_answer
    run.citations = citations
    run.finished_at = utc_now()
    run.updated_at = utc_now()
    db.commit()


def fail_run(db: Session, run: AgentRun, reason: str) -> None:
    run.status = "failed"
    run.final_answer = reason
    run.finished_at = utc_now()
    run.updated_at = utc_now()
    db.commit()


def upsert_memory(
    db: Session,
    group_id: str,
    user_id: str,
    key: str,
    value: str,
    scope: str,
    ttl_days: int | None = None,
    source_run_id: str | None = None,
) -> AgentMemory:
    from sqlalchemy import select

    existing = db.scalar(
        select(AgentMemory).where(
            AgentMemory.group_id == group_id,
            AgentMemory.user_id == user_id,
            AgentMemory.key == key,
        )
    )
    if existing:
        existing.value = value
        existing.ttl_days = ttl_days
        existing.updated_at = utc_now()
        db.commit()
        db.refresh(existing)
        return existing

    mem = AgentMemory(
        group_id=group_id,
        user_id=user_id,
        key=key,
        value=value,
        scope=scope,
        ttl_days=ttl_days,
        source_run_id=source_run_id,
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem
