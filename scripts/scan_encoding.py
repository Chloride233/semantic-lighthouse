r"""Scan frontend and scripts for garbled UTF-8 or mojibake markers.

Usage:
    .venv/Scripts/python scripts/scan_encoding.py

Exit 0: clean. Exit 1: garbled characters found.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRS = ["static", "scripts"]
EXTENSIONS = {".html", ".js", ".css", ".py"}

MOJIBAKE_CODEPOINTS: set[int] = {0xFFFD, 0xFEFF, 0xFFFE}


def _latin1_mojibake(text: str) -> list[int]:
    """Extended Latin runs of 4+ chars in U+00C0-U+00FF → likely mojibake."""
    issues: list[int] = []
    run = 0
    for i, ch in enumerate(text):
        if 0x00C0 <= ord(ch) <= 0x00FF:
            run += 1
            if run >= 4:
                issues.append(i - run + 1)
                run = 0
        else:
            run = 0
    return issues


def scan_file(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        print(f"ERROR {path}: {exc}")
        return 1

    errors = 0
    for i, ch in enumerate(text):
        if ord(ch) in MOJIBAKE_CODEPOINTS:
            ctx = repr(text[max(0, i - 10):i + 10])
            print(f"BAD-CHAR U+{ord(ch):04X} in {path} at byte {i}: {ctx}")
            errors += 1

    for pos in _latin1_mojibake(text):
        print(f"MOJIBAKE in {path} at byte {pos}: {repr(text[pos:pos + 20])}")
        errors += 1

    return errors


def main() -> int:
    total = 0
    for dir_name in DIRS:
        d = ROOT / dir_name
        if not d.exists():
            continue
        for fp in sorted(d.rglob("*")):
            if fp.suffix in EXTENSIONS:
                total += scan_file(fp)

    if total == 0:
        print("OK: No encoding issues detected")
    else:
        print(f"\nFAIL: {total} encoding issue(s) found")
    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
