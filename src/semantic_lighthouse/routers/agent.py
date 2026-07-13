"""Agent orchestration router — run lifecycle, steps, human-in-the-loop, memory."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import get_current_user, get_membership_or_404
from semantic_lighthouse.models import (
    AgentRun, AgentStep, AgentMemory, BusinessProject, Conversation, User, utc_now,
)
from semantic_lighthouse.schemas import (
    AgentRunCreateRequest,
    AgentRunDetailResponse,
    AgentRunRespondRequest,
    AgentRunResponse,
    AgentStepResponse,
    AgentMemoryResponse,
    AgentMemoryUpsertRequest,
    RagCitation,
)
from semantic_lighthouse.services.agent_orchestrator import (
    add_step,
    agent_loop,
    create_run,
    execute_tool,
    fail_run,
    finalize_run,
    is_risky_tool,
    tool_role_error,
    upsert_memory,
)

router = APIRouter(prefix="/groups/{group_id}/agent", tags=["agent"])


def _get_project_or_404(db: Session, group_id: str, project_id: str) -> BusinessProject:
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _run_response(run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse(
        id=run.id,
        group_id=run.group_id,
        user_id=run.user_id,
        project_id=run.project_id,
        conversation_id=run.conversation_id,
        goal=run.goal,
        status=run.status,
        current_phase=run.current_phase,
        step_count=len(run.steps) if run.steps else 0,
        created_at=run.created_at,
        updated_at=run.updated_at,
        finished_at=run.finished_at,
    )


def _step_response(step: AgentStep) -> AgentStepResponse:
    return AgentStepResponse(
        id=step.id,
        run_id=step.run_id,
        phase=step.phase,
        step_index=step.step_index,
        thought=step.thought,
        action_type=step.action_type,
        action_detail=step.action_detail,
        observation=step.observation,
        status=step.status,
        error_message=step.error_message,
        started_at=step.started_at,
        finished_at=step.finished_at,
    )


# ── runs ──────────────────────────────────────────────────────────────


@router.post("/runs", response_model=AgentRunResponse, status_code=201)
def start_agent_run(
    group_id: str,
    body: AgentRunCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AgentRunResponse:
    get_membership_or_404(db, current_user.id, group_id)

    # S2.3A: validate project and conversation consistency
    project_id = body.project_id
    if body.conversation_id:
        conv = db.get(Conversation, body.conversation_id)
        if conv is None or conv.group_id != group_id or conv.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if project_id is not None and project_id != conv.project_id:
            raise HTTPException(
                status_code=409,
                detail="Project context does not match conversation",
            )
        project_id = conv.project_id
    if project_id:
        project = _get_project_or_404(db, group_id, project_id)
        if project.status == "archived":
            raise HTTPException(
                status_code=409, detail="Cannot create Agent run in an archived project"
            )

    run = create_run(db, group_id, current_user.id, body.goal, body.conversation_id, project_id)

    add_step(
        db, run, phase="plan", step_index=0,
        thought=f"Goal received: {body.goal}",
        action_type="think",
        action_detail={"goal": body.goal},
        observation=f"Planning execution for goal: {body.goal}",
        status="completed",
    )
    db.commit()
    db.refresh(run)
    return _run_response(run)


@router.get("/runs", response_model=list[AgentRunResponse])
def list_agent_runs(
    group_id: str,
    project_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgentRunResponse]:
    get_membership_or_404(db, current_user.id, group_id)
    conditions = [AgentRun.group_id == group_id, AgentRun.user_id == current_user.id]
    if project_id is not None:
        _get_project_or_404(db, group_id, project_id)
        conditions.append(AgentRun.project_id == project_id)
    runs = db.scalars(
        select(AgentRun)
        .where(*conditions)
        .order_by(AgentRun.created_at.desc())
        .limit(20)
    ).all()
    return [_run_response(r) for r in runs]


@router.get("/runs/{run_id}", response_model=AgentRunDetailResponse)
def get_agent_run(
    group_id: str,
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRunDetailResponse:
    get_membership_or_404(db, current_user.id, group_id)
    run = db.scalar(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.group_id == group_id)
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    if run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another user's run")

    steps = db.scalars(
        select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index.asc())
    ).all()

    return AgentRunDetailResponse(
        id=run.id, group_id=run.group_id, user_id=run.user_id,
        project_id=run.project_id,
        conversation_id=run.conversation_id, goal=run.goal,
        status=run.status, current_phase=run.current_phase,
        step_count=len(steps), created_at=run.created_at,
        updated_at=run.updated_at, finished_at=run.finished_at,
        final_answer=run.final_answer,
        citations=[RagCitation.model_validate(c) for c in run.citations] if run.citations else [],
        steps=[_step_response(s) for s in steps],
        plan_json=run.plan_json or [],
    )


# ── steps ─────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}/steps", response_model=list[AgentStepResponse])
def list_agent_steps(
    group_id: str,
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgentStepResponse]:
    get_membership_or_404(db, current_user.id, group_id)
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.group_id == group_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    if run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another user's run")
    steps = db.scalars(
        select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index.asc())
    ).all()
    return [_step_response(s) for s in steps]


# ── execute step ──────────────────────────────────────────────────────


@router.post("/runs/{run_id}/execute")
def execute_agent_step(
    group_id: str,
    run_id: str,
    tool: str = Query(default="", description="If set: V1 single-tool eval path. If empty: V2 agent loop path."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AgentStepResponse:
    membership = get_membership_or_404(db, current_user.id, group_id)
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.group_id == group_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    if run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another user's run")
    if run.project_id:
        project = db.get(BusinessProject, run.project_id)
        if project is not None and project.status == "archived":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot execute Agent run scoped to an archived project",
            )
    if run.status == "awaiting_confirmation":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is awaiting confirmation; respond before continuing",
        )
    if run.status not in ("planning", "executing"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Run is {run.status}, cannot execute")

    # ── V1: deterministic single-tool path (eval / manual) ──────────
    if tool:
        return _step_response(_execute_single_tool(
            db, run, group_id, membership.role, tool,
        ))

    # ── V2: agent loop path ────────────────────────────────────────
    run.status = "executing"
    run.current_phase = "execute"
    run.updated_at = utc_now()
    db.commit()

    from semantic_lighthouse.services.chat import ChatError, create_chat_client, FakeLoopChatClient
    try:
        client = create_chat_client(settings)
    except ChatError as exc:
        add_step(db, run, phase="execute", step_index=len(run.steps) if run.steps else 0,
                 thought="Agent provider failed.", action_type="llm_decision",
                 action_detail={"action": "agent_decide"},
                 observation=str(exc)[:200], error_message=str(exc)[:200], status="failed")
        fail_run(db, run, f"Chat provider unavailable: {exc}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                           detail=f"Chat provider unavailable: {exc}") from exc

    if settings.chat_provider == "fake" and not isinstance(client, FakeLoopChatClient):
        client = FakeLoopChatClient([{"action": "finalize", "final_answer": "FakeChatClient fallback.", "thought": "No decisions configured."}])

    max_steps = min(max(settings.agent_max_steps, 1), 10)
    try:
        last_step = agent_loop(db, run, group_id, membership.role, client.agent_decide, max_steps=max_steps)
    except ChatError as exc:
        add_step(db, run, phase="execute", step_index=len(run.steps) if run.steps else 0,
                 thought="Agent provider failed.", action_type="llm_decision",
                 action_detail={"action": "agent_decide"},
                 observation=str(exc)[:200], error_message=str(exc)[:200], status="failed")
        fail_run(db, run, f"Agent decision failed: {exc}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                           detail=f"Agent decision failed: {exc}") from exc

    if last_step is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Agent loop produced no step")
    db.refresh(last_step)
    return _step_response(last_step)


def _execute_single_tool(
    db: Session, run: AgentRun, group_id: str, user_role: str, tool: str,
) -> AgentStep:
    """V1 deterministic single-tool execution — preserved for eval regression."""
    tool_args: dict = {"query": run.goal} if tool == "search_knowledge_base" else {"title": run.goal} if tool == "archive_document" else {}

    role_error = tool_role_error(tool, user_role)
    if role_error:
        run.status = "executing"
        run.current_phase = "execute"
        run.updated_at = utc_now()
        step = add_step(
            db, run, phase="execute", step_index=len(run.steps) if run.steps else 0,
            thought=f"Tool authorization failed: {tool}",
            action_type="tool_call",
            action_detail={"tool": tool, "arguments": tool_args},
            observation=role_error,
            error_message=role_error,
            status="failed",
        )
        fail_run(db, run, role_error)
        db.refresh(step)
        return step

    if is_risky_tool(tool) and not (run.project_id is not None and tool == "archive_document"):
        run.status = "awaiting_confirmation"
        run.current_phase = "execute"
        run.updated_at = utc_now()
        step_index = len(run.steps) if run.steps else 0
        step = add_step(
            db, run, phase="execute", step_index=step_index,
            thought=f"Tool '{tool}' requires confirmation before execution.",
            action_type="ask_user",
            action_detail={
                "tool": tool, "arguments": tool_args,
                "needs_confirmation": True, "requires_confirmation": True,
                "risk_level": "high",
                "confirmation_reason": f"Tool '{tool}' can change group data.",
            },
            observation=f"Waiting for user confirmation to execute '{tool}'.",
            status="running",
        )
        db.commit()
        db.refresh(step)
        return step

    run.status = "executing"
    run.current_phase = "execute"
    run.updated_at = utc_now()
    step_index = len(run.steps) if run.steps else 0
    step = add_step(
        db, run, phase="execute", step_index=step_index,
        thought=f"Executing tool: {tool}",
        action_type="tool_call",
        action_detail={"tool": tool, "arguments": tool_args},
        status="running",
    )
    db.commit()

    result = execute_tool(tool, tool_args, db, group_id, user_role, run.user_id, project_id=run.project_id)
    step.observation = result
    step.finished_at = utc_now()

    if result.startswith("Error:"):
        step.status = "failed"
        step.error_message = result
    else:
        step.status = "completed"

    citations = [{
        "document_id": "", "chunk_id": "", "title": f"Agent {tool} Result",
        "source_path": "", "file_name": "", "chunk_index": 0,
        "heading_path": None, "snippet": result[:200],
        "score": None, "retrieval_method": "keyword",
    }] if result and not result.startswith("Error:") else []

    if step.status == "completed":
        finalize_run(db, run, f"Agent executed '{tool}':\n\n{result}", citations)
    else:
        fail_run(db, run, f"Tool '{tool}' failed: {result}")

    db.commit()
    db.refresh(step)
    return step


# ── human-in-the-loop ─────────────────────────────────────────────────


@router.post("/runs/{run_id}/respond", response_model=AgentRunResponse)
def respond_to_agent(
    group_id: str,
    run_id: str,
    body: AgentRunRespondRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AgentRunResponse:
    membership = get_membership_or_404(db, current_user.id, group_id)
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.group_id == group_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    if run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another user's run")
    if run.project_id:
        project = db.get(BusinessProject, run.project_id)
        if project is not None and project.status == "archived":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot respond to Agent run scoped to an archived project",
            )

    response_lower = body.response.strip().lower()

    if response_lower in ("stop", "abort"):
        run.status = "stopped"
        run.current_phase = "conclude"
        run.final_answer = "User stopped the run."
        run.finished_at = utc_now()
        run.updated_at = utc_now()
        db.commit()
        db.refresh(run)
        return _run_response(run)

    if response_lower in ("yes", "confirm", "approve", "proceed"):
        if run.status == "awaiting_confirmation":
            last_step = run.steps[-1] if run.steps else None
            tool_name = (last_step.action_detail or {}).get("tool", "unknown")
            tool_args = (last_step.action_detail or {}).get("arguments", {})
            # Preserve original ask_user step; append user confirmation event
            current_step_count = len(run.steps) if run.steps else 0
            add_step(
                db, run, phase="execute", step_index=current_step_count,
                thought="User confirmed risky action.",
                action_type="ask_user",
                action_detail={
                    "response_event": True,
                    "user_id": current_user.id,
                    "response": body.response,
                    "confirmed": True,
                    "tool": tool_name,
                    "arguments": tool_args,
                    "responded_at": utc_now().isoformat(),
                },
                observation=f"User confirmed execution of '{tool_name}'.",
                status="completed",
            )
            # Execute the confirmed tool in a separate tool_call step
            result = execute_tool(tool_name, tool_args, db, group_id, membership.role, current_user.id, project_id=run.project_id)
            step_index2 = len(run.steps) if run.steps else 0
            add_step(
                db, run, phase="execute", step_index=step_index2,
                thought=f"Executing confirmed tool: {tool_name}",
                action_type="tool_call",
                action_detail={"tool": tool_name, "arguments": tool_args},
                observation=result,
                status="completed" if not result.startswith("Error:") else "failed",
                error_message=result if result.startswith("Error:") else None,
            )
            if result.startswith("Error:"):
                fail_run(db, run, result)
            else:
                run.status = "executing"
                run.current_phase = "execute"
                run.updated_at = utc_now()
            db.commit()
            db.refresh(run)
        else:
            step_index = len(run.steps) if run.steps else 0
            add_step(
                db, run, phase="execute", step_index=step_index,
                thought="User confirmed the action.",
                action_type="ask_user",
                action_detail={"user_response": body.response},
                observation=f"User confirmed: {body.response}",
                status="completed",
            )
            run.status = "executing"
            run.current_phase = "execute"
            run.updated_at = utc_now()
            db.commit()
            db.refresh(run)
    elif response_lower in ("no", "reject", "cancel", "deny"):
        if run.status == "awaiting_confirmation":
            last_step = run.steps[-1] if run.steps else None
            tool_name = (last_step.action_detail or {}).get("tool", "unknown")
            tool_args = (last_step.action_detail or {}).get("arguments", {})
            # Preserve original ask_user step; append user rejection event
            current_step_count = len(run.steps) if run.steps else 0
            rejection_msg = (
                f"User REJECTED the request to use '{tool_name}'. "
                f"Do NOT propose this tool again in this run."
            )
            add_step(
                db, run, phase="execute", step_index=current_step_count,
                thought="User rejected risky action.",
                action_type="ask_user",
                action_detail={
                    "response_event": True,
                    "user_id": current_user.id,
                    "response": body.response,
                    "rejected": True,
                    "tool": tool_name,
                    "arguments": tool_args,
                    "responded_at": utc_now().isoformat(),
                },
                observation=rejection_msg,
                status="completed",
            )
            run.status = "executing"
            run.current_phase = "execute"
            run.updated_at = utc_now()
            db.commit()
            db.refresh(run)
        else:
            fail_run(db, run, f"User rejected: {body.response}")
    else:
        step_index = len(run.steps) if run.steps else 0
        add_step(
            db, run, phase="execute", step_index=step_index,
            thought=f"User provided input: {body.response}",
            action_type="ask_user",
            action_detail={"user_response": body.response},
            observation=f"User input: {body.response}",
            status="completed",
        )
        run.updated_at = utc_now()
        db.commit()
        db.refresh(run)

    return _run_response(run)


# ── memory ────────────────────────────────────────────────────────────


@router.get("/memories", response_model=list[AgentMemoryResponse])
def list_memories(
    group_id: str,
    scope: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgentMemoryResponse]:
    get_membership_or_404(db, current_user.id, group_id)
    conditions = [AgentMemory.group_id == group_id, AgentMemory.user_id == current_user.id]
    if scope:
        conditions.append(AgentMemory.scope == scope)
    memories = db.scalars(
        select(AgentMemory).where(*conditions).order_by(AgentMemory.updated_at.desc()).limit(50)
    ).all()
    return [_memory_response(m) for m in memories]


@router.post("/memories", response_model=AgentMemoryResponse, status_code=201)
def upsert_memory_endpoint(
    group_id: str,
    body: AgentMemoryUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentMemoryResponse:
    get_membership_or_404(db, current_user.id, group_id)
    mem = upsert_memory(
        db, group_id, current_user.id,
        key=body.key, value=body.value,
        scope=body.scope, ttl_days=body.ttl_days,
    )
    return _memory_response(mem)


@router.delete("/memories/{memory_id}", status_code=204)
def delete_memory(
    group_id: str,
    memory_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    get_membership_or_404(db, current_user.id, group_id)
    mem = db.scalar(
        select(AgentMemory).where(
            AgentMemory.id == memory_id,
            AgentMemory.group_id == group_id,
            AgentMemory.user_id == current_user.id,
        )
    )
    if mem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    db.delete(mem)
    db.commit()


def _memory_response(m: AgentMemory) -> AgentMemoryResponse:
    return AgentMemoryResponse(
        id=m.id, group_id=m.group_id, user_id=m.user_id,
        key=m.key, value=m.value, scope=m.scope,
        ttl_days=m.ttl_days, source_run_id=m.source_run_id,
        created_at=m.created_at, updated_at=m.updated_at,
    )
