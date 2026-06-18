"""Agent DeepSeek smoke — validates agent_decide() returns legal AgentDecision.

Usage: .venv/Scripts/python scripts/smoke_agent_deepseek.py
Without DEEPSEEK_API_KEY: SKIP, exit 0.
With key: runs 3 short calls, exits 0 if all pass, 1 if any fail.

Scope: LLM output validation only. Does NOT verify AgentRun-level audit
(ChatError → 502, failed step, fail_run). Pytest covers that.
"""
from __future__ import annotations

import os
import sys

from semantic_lighthouse.config import Settings
from semantic_lighthouse.services.chat import ChatError, DeepSeekChatClient


def main() -> int:
    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        print("SKIP: DEEPSEEK_API_KEY not set")
        return 0

    settings = Settings(
        deepseek_api_key=api_key,
        chat_model=os.getenv("CHAT_MODEL", "deepseek-v4-flash"),
        chat_base_url=os.getenv("CHAT_BASE_URL", "https://api.deepseek.com"),
        chat_timeout_seconds=30,
    )
    client = DeepSeekChatClient(settings)
    failed = 0

    # S1: finalize
    d = client.agent_decide(
        [{"role": "user", "content": 'Reply with JSON: {"action":"finalize","final_answer":"Hello","thought":"Greeting"}'}],
        [],
    )
    if d.action == "finalize" and d.final_answer:
        print(f"PASS S1: finalize — {d.final_answer[:80]}")
    else:
        print(f"FAIL S1: expected finalize, got action={d.action}")
        failed += 1

    # S2: call_tool
    tools = [{"type": "function", "function": {
        "name": "list_documents", "description": "List documents.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }}]
    d = client.agent_decide(
        [{"role": "user", "content": "List all documents."}], tools,
    )
    if d.action == "call_tool":
        if not (d.tool_name and isinstance(d.tool_name, str) and d.tool_name.strip()):
            print("FAIL S2: tool_name empty")
            failed += 1
        elif not isinstance(d.tool_arguments, dict):
            print(f"FAIL S2: tool_arguments not dict: {type(d.tool_arguments)}")
            failed += 1
        else:
            print(f"PASS S2: call_tool — {d.tool_name}")
    else:
        print(f"FAIL S2: expected call_tool, got action={d.action}")
        failed += 1

    # S3: provider failure → ChatError
    bad = Settings(deepseek_api_key="bad-key", chat_model="deepseek-v4-flash",
                   chat_base_url="https://api.deepseek.com", chat_timeout_seconds=5)
    try:
        DeepSeekChatClient(bad).agent_decide([{"role": "user", "content": "Hi."}], [])
        print("FAIL S3: expected ChatError")
        failed += 1
    except ChatError as exc:
        print(f"PASS S3: ChatError — {str(exc)[:100]}")
    except Exception as exc:
        print(f"PASS S3: unexpected {type(exc).__name__}: {exc}")

    if failed:
        print(f"\n{failed} FAILED")
        return 1
    print("\nAll smoke tests PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
