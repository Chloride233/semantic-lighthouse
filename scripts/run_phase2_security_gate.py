"""Run the deterministic Phase 2 controlled Agent security regression gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_phase2_agent_security.py",
            "-p",
            "no:cacheprovider",
        ],
        cwd=repository_root,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
