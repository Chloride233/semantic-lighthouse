"""Build a static offline governance review workbench.

The workbench is a local HTML review surface over governance_review_briefing.json
and governance_review_decisions_template.csv. It lets a human reviewer fill
decisions in the browser and download a CSV. It does not write to the database,
create governance issues, apply model changes, publish packages, or execute
runtime queries.

Usage:
  .venv/Scripts/python scripts/build_governance_review_workbench.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKBENCH_VERSION = "1.0"
DECISION_OPTIONS = ["accept", "reject", "defer", "needs_more_evidence"]
UNSAFE_KEYS = {"source_path", "storage_path"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found in {path.parent}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(csv_path: Path | None) -> list[dict[str, str]]:
    if csv_path is None or not csv_path.is_file():
        return []
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _decision_complete(row: dict[str, str]) -> bool:
    return all(
        _clean(row.get(field))
        for field in ["decision", "reviewer", "reviewed_at", "rationale"]
    )


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if key not in UNSAFE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _safe_json_script(value: Any) -> str:
    text = json.dumps(_sanitize(value), ensure_ascii=False)
    return text.replace("</", "<\\/")


def _workbench_payload(
    *,
    briefing: dict[str, Any],
    briefing_path: Path,
    decision_rows: list[dict[str, str]],
    csv_path: Path | None,
) -> dict[str, Any]:
    completed = sum(1 for row in decision_rows if _decision_complete(row))
    pending = len(decision_rows) - completed
    return {
        "workbench_version": WORKBENCH_VERSION,
        "pipeline": "governance_review_workbench",
        "generated_at": _utc_now(),
        "data_pack": briefing.get("data_pack", {}),
        "source_artifacts": {
            "governance_review_briefing": str(briefing_path),
            "governance_review_decisions_csv": str(csv_path) if csv_path else None,
        },
        "summary": {
            "review_groups": len(briefing.get("review_groups", [])),
            "decision_rows": len(decision_rows),
            "pending_decision_rows": pending,
            "completed_decision_rows": completed,
            "requires_human_review": pending > 0,
        },
        "decision_options": DECISION_OPTIONS,
        "review_groups": briefing.get("review_groups", []),
        "decision_rows": decision_rows,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "executes_runtime_query": False,
            "workbench_only": True,
            "auto_accepts_candidates": False,
            "requires_explicit_human_decision": True,
        },
    }


def build_governance_review_workbench(
    data_dir: Path,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    briefing_path = data_dir / "governance_review_briefing.json"
    briefing = _read_json(briefing_path, "governance_review_briefing.json")
    if csv_path is None:
        default_csv = data_dir / "governance_review_decisions_template.csv"
        csv_path = default_csv if default_csv.is_file() else None
    return _sanitize(
        _workbench_payload(
            briefing=briefing,
            briefing_path=briefing_path,
            decision_rows=_read_csv(csv_path),
            csv_path=csv_path,
        )
    )


def _html_document(payload: dict[str, Any]) -> str:
    payload_json = _safe_json_script(payload)
    preloaded_groups = "\n".join(
        "<li>"
        f"{group.get('source_table')} / {group.get('derived_class')}"
        "</li>"
        for group in payload.get("review_groups", [])
    )
    css = """
:root {
  color-scheme: light;
  --bg: #f6f7f4;
  --ink: #17201b;
  --muted: #657066;
  --line: #d9ded5;
  --panel: #ffffff;
  --accent: #23684f;
  --warn: #a45d18;
  --danger: #9b2d30;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  letter-spacing: 0;
}
button, input, select, textarea {
  font: inherit;
}
.shell {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  min-height: 100vh;
}
.sidebar {
  border-right: 1px solid var(--line);
  background: #eef1ea;
  padding: 20px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: auto;
}
.main {
  padding: 24px;
}
.title {
  font-size: 24px;
  line-height: 1.15;
  margin: 0 0 8px;
}
.muted {
  color: var(--muted);
}
.metric {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
}
.group-nav {
  width: 100%;
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 8px;
  padding: 10px;
  text-align: left;
  margin-top: 8px;
  cursor: pointer;
}
.group-nav[aria-current="true"] {
  border-color: var(--accent);
  box-shadow: inset 3px 0 0 var(--accent);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.button {
  border: 1px solid var(--ink);
  background: var(--ink);
  color: white;
  border-radius: 8px;
  padding: 9px 12px;
  cursor: pointer;
}
.button.secondary {
  background: transparent;
  color: var(--ink);
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 14px;
}
.group-title {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 12px;
}
.group-title h2 {
  margin: 0;
  font-size: 20px;
}
.badge {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  background: #f7f8f5;
}
.checks, .samples {
  display: grid;
  gap: 8px;
}
.sample {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px;
  background: #fbfcfa;
}
.kv {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.kv span {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 3px 6px;
  background: white;
  font-size: 12px;
}
.decision-grid {
  display: grid;
  grid-template-columns: minmax(140px, 180px) repeat(4, minmax(120px, 1fr));
  gap: 10px;
  align-items: start;
}
.field {
  display: grid;
  gap: 5px;
}
.field label {
  color: var(--muted);
  font-size: 12px;
}
select, input, textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: white;
  padding: 8px;
}
textarea {
  min-height: 64px;
  resize: vertical;
}
.row-status {
  font-size: 12px;
  color: var(--muted);
}
.row-status.complete {
  color: var(--accent);
}
.row-status.incomplete {
  color: var(--warn);
}
.boundary {
  font-size: 12px;
  line-height: 1.5;
  border-top: 1px solid var(--line);
  padding-top: 12px;
  margin-top: 14px;
}
@media (max-width: 900px) {
  .shell { grid-template-columns: 1fr; }
  .sidebar { position: static; height: auto; }
  .decision-grid { grid-template-columns: 1fr; }
}
"""
    js = """
const state = window.REVIEW_WORKBENCH;
const rowsById = new Map(state.decision_rows.map((row) => [row.review_item_id, {...row}]));
let activeGroupKey = state.review_groups[0]?.group_key || "";

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\\n\\r]/.test(text)) {
    return '"' + text.replaceAll('"', '""') + '"';
  }
  return text;
}

function rowComplete(row) {
  return Boolean(row.decision && row.reviewer && row.reviewed_at && row.rationale);
}

function renderSidebar() {
  const sidebar = document.querySelector("#groups");
  sidebar.innerHTML = "";
  state.review_groups.forEach((group) => {
    const button = document.createElement("button");
    button.className = "group-nav";
    button.type = "button";
    button.setAttribute("aria-current", group.group_key === activeGroupKey ? "true" : "false");
    button.innerHTML = `<strong>${group.source_table} / ${group.derived_class}</strong><br><span class="muted">${group.pending_decision_items} pending · ${group.total_items} total</span>`;
    button.addEventListener("click", () => {
      activeGroupKey = group.group_key;
      render();
    });
    sidebar.appendChild(button);
  });
}

function renderSummary() {
  const rows = [...rowsById.values()];
  const complete = rows.filter(rowComplete).length;
  const pending = rows.length - complete;
  document.querySelector("#summary").innerHTML = `
    <div class="metric"><span>Total rows</span><strong>${rows.length}</strong></div>
    <div class="metric"><span>Completed</span><strong>${complete}</strong></div>
    <div class="metric"><span>Pending</span><strong>${pending}</strong></div>
    <div class="metric"><span>Groups</span><strong>${state.review_groups.length}</strong></div>
  `;
}

function inputField(label, value, onInput, options = {}) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  const labelEl = document.createElement("label");
  labelEl.textContent = label;
  wrap.appendChild(labelEl);
  const input = options.textarea ? document.createElement("textarea") : document.createElement("input");
  input.value = value || "";
  if (options.placeholder) input.placeholder = options.placeholder;
  input.addEventListener("input", () => onInput(input.value));
  wrap.appendChild(input);
  return wrap;
}

function decisionSelect(row) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  const label = document.createElement("label");
  label.textContent = "Decision";
  const select = document.createElement("select");
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "Select";
  select.appendChild(blank);
  state.decision_options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option;
    item.textContent = option;
    select.appendChild(item);
  });
  select.value = row.decision || "";
  select.addEventListener("change", () => {
    row.decision = select.value;
    render();
  });
  wrap.appendChild(label);
  wrap.appendChild(select);
  return wrap;
}

function decisionEditor(group) {
  const container = document.createElement("div");
  container.className = "checks";
  group.review_item_ids.forEach((id) => {
    const row = rowsById.get(id);
    if (!row) return;
    const panel = document.createElement("div");
    panel.className = "panel";
    const status = rowComplete(row) ? "complete" : "incomplete";
    panel.innerHTML = `<div class="group-title"><div><strong>${id}</strong><div class="muted">${row.finding_message || ""}</div></div><span class="row-status ${status}">${status}</span></div>`;
    const grid = document.createElement("div");
    grid.className = "decision-grid";
    grid.appendChild(decisionSelect(row));
    grid.appendChild(inputField("Reviewer", row.reviewer, (value) => { row.reviewer = value; }));
    grid.appendChild(inputField("Reviewed at", row.reviewed_at, (value) => { row.reviewed_at = value; }, {placeholder: "2026-07-09T08:00:00+00:00"}));
    grid.appendChild(inputField("Rationale", row.rationale, (value) => { row.rationale = value; }, {textarea: true}));
    panel.appendChild(grid);
    container.appendChild(panel);
  });
  return container;
}

function samples(group) {
  const wrap = document.createElement("div");
  wrap.className = "samples";
  group.source_row_samples.forEach((sample) => {
    const item = document.createElement("div");
    item.className = "sample";
    const values = Object.entries(sample.values || {}).map(([key, value]) => `<span>${key}: ${value}</span>`).join("");
    item.innerHTML = `<strong>${sample.review_item_id}</strong> <span class="muted">${sample.table} row ${sample.row}</span><div class="kv">${values}</div>`;
    wrap.appendChild(item);
  });
  return wrap;
}

function renderMain() {
  const group = state.review_groups.find((item) => item.group_key === activeGroupKey) || state.review_groups[0];
  const main = document.querySelector("#main");
  if (!group) {
    main.innerHTML = "<div class='panel'>No review groups available.</div>";
    return;
  }
  main.innerHTML = `
    <div class="panel">
      <div class="group-title">
        <div>
          <h2>${group.source_table} / ${group.derived_class}</h2>
          <div class="muted">${group.total_items} items · ${group.pending_decision_items} pending</div>
        </div>
        <span class="badge">${group.owner_roles.join(", ") || "reviewer"}</span>
      </div>
      <div class="muted">${(group.finding_messages || []).join(" ")}</div>
      <div class="kv">${(group.required_checks || []).map((check) => `<span>${check}</span>`).join("")}</div>
    </div>
  `;
  const samplePanel = document.createElement("div");
  samplePanel.className = "panel";
  samplePanel.innerHTML = "<h3>Source row samples</h3>";
  samplePanel.appendChild(samples(group));
  main.appendChild(samplePanel);
  const decisionPanel = document.createElement("div");
  decisionPanel.className = "panel";
  decisionPanel.innerHTML = "<h3>Decisions</h3>";
  decisionPanel.appendChild(decisionEditor(group));
  main.appendChild(decisionPanel);
}

function downloadCsv() {
  const columns = Object.keys(state.decision_rows[0] || {});
  const lines = [columns.join(",")];
  [...rowsById.values()].forEach((row) => {
    lines.push(columns.map((column) => csvEscape(row[column] || "")).join(","));
  });
  const blob = new Blob([lines.join("\\n") + "\\n"], {type: "text/csv;charset=utf-8"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "governance_review_decisions_filled.csv";
  link.click();
  URL.revokeObjectURL(link.href);
}

function setReviewedAtNow() {
  const value = new Date().toISOString();
  [...rowsById.values()].forEach((row) => {
    if (!row.reviewed_at) row.reviewed_at = value;
  });
  render();
}

function render() {
  renderSidebar();
  renderSummary();
  renderMain();
}

document.querySelector("#download").addEventListener("click", downloadCsv);
document.querySelector("#timestamp").addEventListener("click", setReviewedAtNow);
render();
"""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Governance Review Workbench</title>
  <style>{css}</style>
</head>
<body data-review-workbench>
  <div class="shell">
    <aside class="sidebar">
      <h1 class="title">Governance Review Workbench</h1>
      <p class="muted">Offline review surface. It edits browser state and exports CSV only.</p>
      <div id="summary"></div>
      <div class="toolbar">
        <button class="button" id="download" type="button">Download CSV</button>
        <button class="button secondary" id="timestamp" type="button">Set missing reviewed_at</button>
      </div>
      <div id="groups"></div>
      <ul hidden>
        {preloaded_groups}
      </ul>
      <div class="boundary">
        <strong>Boundaries</strong><br>
        offlineOnly: true<br>
        writesToDatabase: false<br>
        createsRealGovernanceIssues: false<br>
        appliesModelChanges: false<br>
        publishesModelPackage: false<br>
        executesRuntimeQuery: false<br>
        autoAcceptsCandidates: false
      </div>
    </aside>
    <main class="main" id="main"></main>
  </div>
  <script>window.REVIEW_WORKBENCH = {payload_json};</script>
  <script>{js}</script>
</body>
</html>
"""


def write_governance_review_workbench(
    data_dir: Path,
    csv_path: Path | None,
    output_path: Path,
) -> dict[str, Any]:
    payload = build_governance_review_workbench(data_dir, csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_html_document(payload), encoding="utf-8")
    payload["source_artifacts"]["workbench_html"] = str(output_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build static offline governance review workbench",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing governance_review_briefing.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "Decision CSV path "
            "(default: <data-pack>/governance_review_decisions_template.csv)"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="HTML output path (default: <data-pack>/governance_review_workbench.html)",
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "governance_review_workbench.html")
    try:
        result = write_governance_review_workbench(args.data_pack, args.csv, output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Governance Review Workbench ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Groups: {summary['review_groups']}")
    print(f"Decision rows: {summary['decision_rows']}")
    print(f"Pending: {summary['pending_decision_rows']}")
    print(f"HTML: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
