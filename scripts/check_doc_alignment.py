"""Document alignment checker — verifies entry docs reference canonical status source.

Uses only Python standard library. Parses docs/project-status.toml,
checks entry documents for stale expressions, and validates that the
single-source-of-truth pattern is maintained.

Exit 0 on pass, non-zero on any violation.
"""

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STATUS_FILE = DOCS / "project-status.toml"
ARCHIVE_DIR = DOCS / "archive"

# Documents that MUST reference the canonical status source
ENTRY_DOCS = [
    "AGENTS.md",
    "PRODUCT.md",
    "CLAUDE.md",
    "README.md",
    "docs/product-alignment-prd.md",
    "docs/project-roadmap.md",
    "docs/agent-handoff.md",
]

# Known stale expressions that must NOT appear in active entry docs.
# Each tuple: (pattern, description)
STALE_PATTERNS = [
    ("F2C next", "stale 'F2C next' — F2C is complete"),
    ("F2B next", "stale 'F2B next' — F2B is complete"),
    ("F2A active", "stale 'F2A active' — F2A is complete"),
    ("F2B active", "stale 'F2B active' — F2B is complete"),
    ("Frontend F2A active", "stale frontend status"),
    ("Phase 14 underway", "stale 'Phase 14 underway' — Phase 14 is complete"),
    ("14.4 next", "stale '14.4 next' — Phase 14 is complete"),
    ("14.5 next", "stale '14.5 next' — Phase 14 is complete"),
    ("Phase 13 planning", "stale 'Phase 13 planning' — Phase 13 is delivered"),
    ("Phase 13 is planning", "stale Phase 13 planning text"),
    ("Phase 12 Complete / Phase 13 Planning", "stale phase header"),
]

REQUIRED_STATUS_FIELDS = [
    ("schema", "version"),
    ("product", "phase"),
    ("product", "status"),
    ("frontend", "status"),
    ("focus", "current"),
    ("next_decision_gate", "name"),
    ("mcp", "runtime_status"),
    ("verification", "latest_commit"),
]

STATUS_REFERENCE_MARKERS = [
    "project-status.toml",
]


def parse_status():
    """Parse project-status.toml, return dict or None with error."""
    if not STATUS_FILE.exists():
        return None, f"Missing {STATUS_FILE}"
    try:
        with open(STATUS_FILE, "rb") as f:
            return tomllib.load(f), None
    except Exception as e:
        return None, f"Failed to parse {STATUS_FILE}: {e}"


def validate_required_fields(status):
    """Check all required fields exist in parsed status."""
    errors = []
    for section, key in REQUIRED_STATUS_FIELDS:
        if section not in status:
            errors.append(f"{STATUS_FILE}: missing section [{section}]")
            continue
        if key not in status[section]:
            errors.append(f"{STATUS_FILE}: [{section}] missing key '{key}'")
    return errors


def check_doc_references_status(filepath):
    """Check that a document references project-status.toml."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{filepath}: cannot read — {e}"]

    for marker in STATUS_REFERENCE_MARKERS:
        if marker in content:
            return []
    return [f"{filepath}: does not reference project-status.toml (canonical status source)"]


def check_stale_expressions(filepath):
    """Check for known stale expressions in a document."""
    errors = []
    try:
        lines = filepath.read_text(encoding="utf-8").split("\n")
    except Exception as e:
        return [f"{filepath}: cannot read — {e}"]

    for i, line in enumerate(lines, 1):
        for pattern, description in STALE_PATTERNS:
            if pattern in line:
                # Skip if inside code blocks or comments that document history
                stripped = line.strip()
                if stripped.startswith("<!--") or stripped.startswith("#"):  # TOML comments OK
                    continue
                errors.append(f"{filepath}:{i}: {description} (found '{pattern}')")
                break  # one violation per line
    return errors


def check_roadmap_no_self_declared_phase():
    """Roadmap header must not self-declare current phase."""
    roadmap = DOCS / "project-roadmap.md"
    if not roadmap.exists():
        return []
    try:
        content = roadmap.read_text(encoding="utf-8")
    except Exception:
        return [f"{roadmap}: cannot read"]

    lines = content.split("\n")
    for i, line in enumerate(lines[:8], 1):  # only check header area
        if "Current phase" in line and "project-status.toml" not in line:
            if "canonical" not in line.lower():
                return [f"{roadmap}:{i}: roadmap declares 'Current phase' without referencing project-status.toml"]
    return []


def check_handoff_is_single_current():
    """Handoff must be the only active handoff — no stale next directives."""
    handoff = DOCS / "agent-handoff.md"
    if not handoff.exists():
        return []
    try:
        content = handoff.read_text(encoding="utf-8")
    except Exception:
        return [f"{handoff}: cannot read"]

    errors = []
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        # "Next iteration" + stale phase references
        if "Next iteration" in line:
            if "Phase 13" in line or "Phase 14.1" in line or "Phase 14.2" in line:
                errors.append(f"{handoff}:{i}: handoff contains stale 'Next iteration' from old phase")
        # "Next priority" that isn't the current decision gate
        if line.strip().startswith("**Next**") or line.strip().startswith("**Next:"):
            if "F2C" in line or "F2B" in line or "Phase 13" in line or "Phase 14." in line:
                errors.append(f"{handoff}:{i}: handoff has stale 'Next' from old phase")
    return errors


def main():
    all_errors = []

    # 1. Parse and validate status file
    status, err = parse_status()
    if err:
        all_errors.append(err)
        # Cannot continue without status
        for e in all_errors:
            print(e)
        return 1
    all_errors.extend(validate_required_fields(status))

    # 2. Check entry docs reference project-status.toml
    for doc_rel in ENTRY_DOCS:
        path = ROOT / doc_rel
        if not path.exists():
            all_errors.append(f"{path}: file not found (expected entry document)")
            continue
        all_errors.extend(check_doc_references_status(path))

    # 3. Check for stale expressions (skip archive)
    for doc_rel in ENTRY_DOCS:
        path = ROOT / doc_rel
        if not path.exists():
            continue
        all_errors.extend(check_stale_expressions(path))

    # 4. Roadmap must not self-declare current phase
    all_errors.extend(check_roadmap_no_self_declared_phase())

    # 5. Handoff must be single current handoff
    all_errors.extend(check_handoff_is_single_current())

    # 6. Verify no stale docs in archive scanned (sanity check)
    if ARCHIVE_DIR.exists():
        for f in ARCHIVE_DIR.iterdir():
            if f.suffix == ".md":
                for pattern, _ in STALE_PATTERNS:
                    try:
                        if pattern in f.read_text(encoding="utf-8"):
                            # Archive docs CAN contain stale expressions — that's their purpose
                            pass
                    except Exception:
                        pass

    # Report
    if all_errors:
        print(f"\n=== DOC ALIGNMENT: {len(all_errors)} VIOLATION(S) ===\n")
        for e in all_errors:
            print(f"  FAIL: {e}")
        print(f"\n{len(all_errors)} violation(s) found.")
        return 1
    else:
        print("\n=== DOC ALIGNMENT: PASS ===")
        print(f"  Status file: {STATUS_FILE}")
        print(f"  Entry docs checked: {len(ENTRY_DOCS)}")
        print(f"  Archive dir: {'present' if ARCHIVE_DIR.exists() else 'absent'}")
        print("  No stale expressions in active docs.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
