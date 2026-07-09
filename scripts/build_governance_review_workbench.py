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
  --bg: #f3f4f1;
  --ink: #151b17;
  --muted: #69736b;
  --line: #d6dcd2;
  --panel: #ffffff;
  --soft: #edf1ea;
  --accent: #1f6b4f;
  --accent-soft: #e5f1eb;
  --warn: #9b5a14;
  --danger: #9b2d30;
}
* { box-sizing: border-box; }
* { min-width: 0; }
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
  grid-template-columns: minmax(300px, 340px) minmax(0, 1fr);
  min-height: 100vh;
}
.sidebar {
  border-right: 1px solid var(--line);
  background: var(--soft);
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
  margin: 0 0 10px;
}
.muted {
  color: var(--muted);
  overflow-wrap: anywhere;
}
.section-label {
  margin: 20px 0 8px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}
.flow {
  display: grid;
  gap: 8px;
}
.flow-step {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgb(255 255 255 / 0.58);
}
.flow-step strong {
  display: block;
  font-size: 13px;
}
.flow-index {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 999px;
  background: var(--accent);
  color: white;
  font-size: 12px;
  font-weight: 700;
}
.flow-note {
  margin-top: 2px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
}
.rubric {
  display: grid;
  gap: 8px;
}
.rubric-item {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px;
  background: rgb(255 255 255 / 0.58);
}
.rubric-item strong {
  display: block;
  font-size: 13px;
}
.rubric-item span {
  display: block;
  margin-top: 3px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
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
  padding: 12px;
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
  white-space: nowrap;
}
.button.secondary {
  background: transparent;
  color: var(--ink);
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  margin-bottom: 14px;
}
.panel h3 {
  margin: 0 0 12px;
  font-size: 17px;
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
.badge.strong {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
}
.stat-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}
.stat {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px;
  background: #fafbf8;
}
.stat span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}
.stat strong {
  display: block;
  margin-top: 4px;
  font-size: 18px;
}
.checks, .samples {
  display: grid;
  gap: 8px;
}
.work-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(260px, 0.8fr) minmax(0, 1.25fr);
  gap: 14px;
  align-items: start;
}
.batch-grid {
  display: grid;
  grid-template-columns: minmax(130px, 170px) minmax(120px, 1fr) minmax(170px, 1fr) minmax(200px, 1.2fr) auto;
  gap: 10px;
  align-items: end;
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-items: start;
}
.queue-item {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: #fbfcfa;
  overflow: hidden;
}
.queue-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.queue-meta span {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 3px 6px;
  background: white;
  font-size: 12px;
  max-width: 100%;
  overflow-wrap: anywhere;
}
.decision-help {
  margin-top: 10px;
  border-left: 3px solid var(--accent);
  padding: 8px 10px;
  background: var(--accent-soft);
  color: #1b4f3c;
  font-size: 12px;
  line-height: 1.45;
}
.decision-help strong {
  display: block;
  margin-bottom: 3px;
}
.field-guide {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}
.field-help {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px 10px;
  background: #fbfcfa;
  font-size: 12px;
  line-height: 1.45;
}
.field-help strong {
  color: var(--ink);
}
.field-help span {
  color: var(--muted);
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
  min-width: 0;
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
.hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
}
.status-line {
  min-height: 18px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--accent);
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
  .stat-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .work-grid { grid-template-columns: 1fr; }
  .batch-grid { grid-template-columns: 1fr; }
  .decision-grid { grid-template-columns: 1fr; }
}
"""
    js = """
const state = window.REVIEW_WORKBENCH;
const rowsById = new Map(state.decision_rows.map((row) => [row.review_item_id, {...row}]));
let activeGroupKey = state.review_groups[0]?.group_key || "";
let batchMessage = "";
const decisionLabels = {
  accept: "接受",
  reject: "拒绝",
  defer: "暂缓",
  needs_more_evidence: "需要更多证据",
};
const fieldHelp = {
  equipment_id: "设备标识，用来确认是哪一台设备。",
  work_center_id: "工作中心标识，用来定位设备所在生产区域。",
  equipment_name: "设备名称，用来辅助人工识别设备。",
  serial_number: "设备序列号，用来辅助核对唯一实物。",
  install_date: "安装日期，可辅助判断设备使用年限。",
  last_calibration: "最近校准日期，可辅助判断维护状态。",
  status: "设备状态。当前规则把 degraded/down 作为风险信号。",
  material_id: "物料标识，用来确认是哪一种物料。",
  material_name: "物料名称，用来辅助人工识别物料。",
  material_code: "物料编码，用来对齐源系统和采购/库存记录。",
  supplier_id: "供应商标识，用来辅助判断供应来源。",
  unit_of_measure: "计量单位，用来理解数量和成本口径。",
  unit_cost: "单位成本，用来辅助判断材料价值。",
  lead_time_days: "采购或补货提前期天数，用来辅助判断供应风险。",
  safety_stock_qty: "安全库存数量，用来辅助理解库存策略。",
  reorder_point: "再订货点，用来辅助理解补货触发阈值。",
  abc_class: "ABC 分类。当前规则把 A 类作为高价值材料信号。",
  is_batch_tracked: "是否批次追踪，用来辅助判断追溯要求。",
};

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

function currentGroup() {
  return state.review_groups.find((item) => item.group_key === activeGroupKey) || state.review_groups[0];
}

function groupRows(group) {
  return group.review_item_ids.map((id) => rowsById.get(id)).filter(Boolean);
}

function groupCompletedCount(group) {
  return groupRows(group).filter(rowComplete).length;
}

function groupPendingCount(group) {
  return groupRows(group).filter((row) => !row.decision).length;
}

function statusLabel(row) {
  if (rowComplete(row)) return "已完成";
  if (row.decision) return "缺少字段";
  return "待处理";
}

function renderSidebar() {
  const sidebar = document.querySelector("#groups");
  sidebar.innerHTML = "";
  state.review_groups.forEach((group) => {
    const button = document.createElement("button");
    button.className = "group-nav";
    button.type = "button";
    button.setAttribute("aria-current", group.group_key === activeGroupKey ? "true" : "false");
    const completed = groupCompletedCount(group);
    const pending = groupPendingCount(group);
    button.innerHTML = `<strong>${group.source_table} / ${group.derived_class}</strong><br><span class="muted">${pending} 待处理 · ${completed} 已完成 · ${group.total_items} 总计</span>`;
    button.addEventListener("click", () => {
      activeGroupKey = group.group_key;
      batchMessage = "";
      render();
    });
    sidebar.appendChild(button);
  });
}

function renderWorkflow() {
  const group = currentGroup();
  const pending = group ? groupPendingCount(group) : 0;
  const hasEvidence = Boolean(group?.source_row_samples?.length);
  const flow = document.querySelector("#workflow");
  flow.innerHTML = `
    <div class="section-label">审查流程</div>
    <div class="flow" data-step="review-flow">
      <div class="flow-step"><span class="flow-index">1</span><div><strong>选择分组</strong><div class="flow-note">${group ? `${group.source_table} / ${group.derived_class}` : "暂无分组"}</div></div></div>
      <div class="flow-step"><span class="flow-index">2</span><div><strong>核验证据</strong><div class="flow-note">${hasEvidence ? "查看源数据样例和规则证据" : "当前分组没有样例"}</div></div></div>
      <div class="flow-step"><span class="flow-index">3</span><div><strong>记录决策</strong><div class="flow-note">${pending} 条待处理，可批量或逐条填写</div></div></div>
      <div class="flow-step"><span class="flow-index">4</span><div><strong>导出CSV</strong><div class="flow-note">下载后交给 post-review runner</div></div></div>
    </div>
  `;
}

function renderDecisionGuide() {
  const guide = document.querySelector("#decision-guide");
  guide.innerHTML = `
    <div class="section-label">决策怎么选</div>
    <div class="rubric" id="decision-rubric">
      <div class="rubric-item"><strong>接受</strong><span>接受: 业务含义成立，证据样例支持，且可以进入本体资产。</span></div>
      <div class="rubric-item"><strong>拒绝</strong><span>拒绝: 不是稳定业务概念，或样例显示只是噪声/误报。</span></div>
      <div class="rubric-item"><strong>暂缓</strong><span>暂缓: 方向可能成立，但需要领域负责人确认。</span></div>
      <div class="rubric-item"><strong>需要更多证据</strong><span>需要更多证据: 当前样例或规则不足以支撑判断。</span></div>
    </div>
  `;
}

function renderSummary() {
  const rows = [...rowsById.values()];
  const complete = rows.filter(rowComplete).length;
  const pending = rows.length - complete;
  document.querySelector("#summary").innerHTML = `
    <div class="metric"><span>总行数</span><strong>${rows.length}</strong></div>
    <div class="metric"><span>已完成</span><strong>${complete}</strong></div>
    <div class="metric"><span>待审</span><strong>${pending}</strong></div>
    <div class="metric"><span>分组</span><strong>${state.review_groups.length}</strong></div>
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
  label.textContent = "决策";
  const select = document.createElement("select");
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "请选择";
  select.appendChild(blank);
  state.decision_options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option;
    item.textContent = decisionLabels[option] || option;
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
    panel.className = "queue-item";
    const status = rowComplete(row) ? "complete" : "incomplete";
    panel.innerHTML = `
      <div class="group-title">
        <div>
          <strong>${id}</strong>
          <div class="muted">${row.finding_message || ""}</div>
          <div class="queue-meta">
            <span>推荐动作: ${row.recommended_decision || "无"}</span>
            <span>证据锚点: ${row.evidence_anchor || "无"}</span>
          </div>
          <div class="decision-help">
            <strong>每条怎么做</strong>
            先看源数据样例，再看推荐动作和证据锚点。理由模板: 我选择该决策，因为...
          </div>
        </div>
        <span class="row-status ${status}">${statusLabel(row)}</span>
      </div>
    `;
    const grid = document.createElement("div");
    grid.className = "decision-grid";
    grid.appendChild(decisionSelect(row));
    grid.appendChild(inputField("审查人", row.reviewer, (value) => { row.reviewer = value; }));
    grid.appendChild(inputField("审查时间", row.reviewed_at, (value) => { row.reviewed_at = value; }, {placeholder: "2026-07-09T08:00:00+00:00"}));
    grid.appendChild(inputField("理由", row.rationale, (value) => { row.rationale = value; }, {textarea: true}));
    panel.appendChild(grid);
    container.appendChild(panel);
  });
  return container;
}

function decisionOptionsMarkup() {
  return [
    '<option value="">请选择</option>',
    ...state.decision_options.map((option) => `<option value="${option}">${decisionLabels[option] || option}</option>`),
  ].join("");
}

function applyGroupDecision(group) {
  const decision = document.querySelector("#group-decision").value;
  const reviewer = document.querySelector("#group-reviewer").value.trim();
  const reviewedAt = document.querySelector("#group-reviewed-at").value.trim();
  const rationale = document.querySelector("#group-rationale").value.trim();
  const status = document.querySelector("#group-apply-status");
  if (!decision || !reviewer || !reviewedAt || !rationale) {
    status.textContent = "决策、审查人、审查时间和理由都必须填写。";
    return;
  }
  let updated = 0;
  groupRows(group).forEach((row) => {
    if (row.decision) return;
    row.decision = decision;
    row.reviewer = reviewer;
    row.reviewed_at = reviewedAt;
    row.rationale = rationale;
    updated += 1;
  });
  batchMessage = `已更新 ${updated} 条待审记录；已有决策会保留。`;
  status.textContent = batchMessage;
  renderSummary();
  renderMain();
}

function renderBatchControls(group) {
  const panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML = `
    <h3>批量决策</h3>
    <div class="batch-grid">
      <div class="field">
        <label for="group-decision">决策</label>
        <select id="group-decision">${decisionOptionsMarkup()}</select>
      </div>
      <div class="field">
        <label for="group-reviewer">审查人</label>
        <input id="group-reviewer" autocomplete="off">
      </div>
      <div class="field">
        <label for="group-reviewed-at">审查时间</label>
        <input id="group-reviewed-at" placeholder="2026-07-09T08:00:00+00:00">
      </div>
      <div class="field">
        <label for="group-rationale">理由</label>
        <textarea id="group-rationale"></textarea>
      </div>
      <button class="button" id="apply-group" type="button">应用</button>
    </div>
    <div class="hint">只应用到当前分组的待审记录；已有决策会保留。</div>
    <div class="status-line" id="group-apply-status">${batchMessage}</div>
  `;
  panel.querySelector("#apply-group").addEventListener("click", () => applyGroupDecision(group));
  return panel;
}

function samples(group) {
  const wrap = document.createElement("div");
  wrap.className = "samples";
  if (!group.source_row_samples.length) {
    wrap.innerHTML = "<div class='sample muted'>没有源数据样例。</div>";
    return wrap;
  }
  group.source_row_samples.forEach((sample) => {
    const item = document.createElement("div");
    item.className = "sample";
    const values = Object.entries(sample.values || {}).map(([key, value]) => `<span>${key}: ${value}</span>`).join("");
    item.innerHTML = `<strong>${sample.review_item_id}</strong> <span class="muted">${sample.table} 行 ${sample.row}</span><div class="kv">${values}</div>`;
    wrap.appendChild(item);
  });
  return wrap;
}

function renderFieldGuide(group) {
  const keys = [];
  group.source_row_samples.forEach((sample) => {
    Object.keys(sample.values || {}).forEach((key) => {
      if (!keys.includes(key)) keys.push(key);
    });
  });
  const panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML = `
    <div class="group-title">
      <div>
        <h3>字段速读</h3>
        <div class="muted">辅助解释基于字段名和当前规则，不替代源系统定义。</div>
      </div>
    </div>
    <div class="field-guide">
      ${keys.map((key) => `<div class="field-help"><strong>${key}:</strong> <span>${fieldHelp[key] || "未配置说明，请按源系统口径确认。"}</span></div>`).join("")}
    </div>
  `;
  return panel;
}

function renderActiveGroupSummary(group) {
  const completed = groupCompletedCount(group);
  const pending = groupPendingCount(group);
  const panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML = `
      <div class="section-label">当前分组</div>
      <div class="group-title">
        <div>
          <h2>${group.source_table} / ${group.derived_class}</h2>
          <div class="muted">${(group.finding_messages || []).join(" ")}</div>
        </div>
        <span class="badge strong">${group.owner_roles.join(", ") || "reviewer"}</span>
      </div>
      <div class="stat-strip">
        <div class="stat"><span>待处理事项</span><strong>${pending}</strong></div>
        <div class="stat"><span>已完成</span><strong>${completed}</strong></div>
        <div class="stat"><span>证据样例</span><strong>${group.source_row_samples.length}</strong></div>
        <div class="stat"><span>总事项</span><strong>${group.total_items}</strong></div>
      </div>
      <div class="kv">${(group.required_checks || []).map((check) => `<span>${check}</span>`).join("")}</div>
  `;
  return panel;
}

function renderQueueOverview(group) {
  const panel = document.createElement("div");
  panel.className = "panel";
  const rows = groupRows(group);
  const pending = rows.filter((row) => !row.decision).length;
  panel.innerHTML = `
    <div class="group-title">
      <div>
        <h3>决策队列</h3>
        <div class="muted">${pending} 条待处理。逐条填写可修正当前行。</div>
      </div>
      <span class="badge">${rows.length} 条</span>
    </div>
  `;
  panel.appendChild(decisionEditor(group));
  return panel;
}

function renderMain() {
  const group = currentGroup();
  const main = document.querySelector("#main");
  if (!group) {
    main.innerHTML = "<div class='panel'>没有可审查分组。</div>";
    return;
  }
  main.innerHTML = "";
  main.appendChild(renderActiveGroupSummary(group));
  main.appendChild(renderBatchControls(group));
  const grid = document.createElement("div");
  grid.className = "work-grid";
  const samplePanel = document.createElement("div");
  samplePanel.className = "panel";
  samplePanel.innerHTML = `
    <div class="group-title">
      <div>
        <h3>源数据样例</h3>
        <div class="muted">先核对样例，再决定是否进入 accepted ontology。</div>
      </div>
    </div>
  `;
  samplePanel.appendChild(samples(group));
  grid.appendChild(samplePanel);
  grid.appendChild(renderFieldGuide(group));
  grid.appendChild(renderQueueOverview(group));
  main.appendChild(grid);
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
  renderWorkflow();
  renderDecisionGuide();
  renderSidebar();
  renderSummary();
  renderMain();
}

document.querySelector("#download").addEventListener("click", downloadCsv);
document.querySelector("#timestamp").addEventListener("click", setReviewedAtNow);
render();
"""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>治理审查工作台</title>
  <style>{css}</style>
</head>
<body data-review-workbench>
  <div class="shell">
    <aside class="sidebar">
      <h1 class="title">治理审查工作台</h1>
      <p class="muted">离线审查界面。只编辑浏览器状态，并导出 CSV。</p>
      <div id="workflow"></div>
      <div id="decision-guide"></div>
      <div id="summary"></div>
      <div class="toolbar">
        <button class="button" id="download" type="button">下载 CSV</button>
        <button class="button secondary" id="timestamp" type="button">填充缺失审查时间</button>
      </div>
      <div id="groups"></div>
      <ul hidden>
        {preloaded_groups}
      </ul>
      <div class="boundary">
        <strong>边界</strong><br>
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
