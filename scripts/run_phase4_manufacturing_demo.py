#!/usr/bin/env python3
"""Run the local Phase 4 manufacturing rehearsal.

This is a reproducible presenter entrypoint, not a real-user pilot runner.
It executes the established FDE smoke chain on temporary SQLite data and
labels the result so local rehearsal evidence cannot be confused with Issue #3
user-validation evidence.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "smoke_fde_demo.py"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the local, non-user Phase 4 manufacturing rehearsal.",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        default=None,
        help="Optional validated manufacturing data-pack directory.",
    )
    args = parser.parse_args()

    command = [sys.executable, str(SMOKE_SCRIPT)]
    if args.data_pack is not None:
        command.extend(["--data-pack", str(args.data_pack)])

    print("=== Phase 4 Manufacturing Rehearsal ===")
    print("Mode: local simulated demonstration; no real-user evidence is produced.\n")
    environment = os.environ.copy()
    source_path = str(REPO_ROOT / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [source_path, environment.get("PYTHONPATH")])
    )
    result = subprocess.run(command, cwd=REPO_ROOT, env=environment)
    if result.returncode != 0:
        print("\nRehearsal result: FAIL")
        return result.returncode

    print("\nRehearsal result: PASS")
    print("Next: record this run with record_pilot_task.py using --session-type simulated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
