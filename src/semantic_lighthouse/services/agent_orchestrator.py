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
                Document.status == "ready",
            )
        )
        if doc is None:
            return f"No ready document matching '{title}' found."
        doc.status = "archived"
        db.commit()
        return f"Document '{doc.title}' has been archived."

    return f"Error: tool '{name}' has no handler."


def is_risky_tool(name: str) -> bool:
    tool = _tool_by_name(name)
    return tool.is_risky if tool else False


def create_run(
    db: Session,
    group_id: str,
    user_id: str,
    goal: str,
    conversation_id: str | None = None,
) -> AgentRun:
    run = AgentRun(
        group_id=group_id,
        user_id=user_id,
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
