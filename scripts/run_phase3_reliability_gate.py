"""Run the deterministic Phase 3 reliability and degradation regression gate."""

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
            "tests/test_phase3_reliability.py",
            "tests/test_phase3_load_baseline.py",
            "-p",
            "no:cacheprovider",
        ],
        cwd=repository_root,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
