import { api } from '../api.js';
import { state } from '../state.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

const STATUS_LABELS = {
  created: '已创建',
  planning: '规划中',
  executing: '执行中',
  awaiting_confirmation: '等待确认',
  completed: '已完成',
  failed: '失败',
  stopped: '已停止',
};

const STATUS_STYLE = {
  completed: 'ok',
  failed: 'error',
  stopped: 'muted',
  awaiting_confirmation: 'warn',
};

const PHASE_LABELS = {
  plan: '规划',
  execute: '执行',
  conclude: '收尾',
};

const STEP_TYPE_LABELS = {
  think: '思考',
  llm_decision: 'LLM 决策',
  tool_call: '工具调用',
  ask_user: '用户确认',
  finalize: '最终答案',
};

const EXAMPLE_GOALS = [
  '列出当前知识库文档',
  '检索 Ontology 相关证据并总结',
  '归档标题包含 test 的文档（演示高风险确认）',
];

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!state.accessToken) { container.innerHTML = '<p class="muted">请先登录。</p>'; return; }
  if (!gid) { container.innerHTML = '<p class="muted">请先选择工作区。</p>'; return; }

  await renderList(container, gid);
}

/* ── List View ───────────────────────────────────────────────────── */

async function renderList(container, gid) {
  container.innerHTML = `
    <div class="agentPage">
      <h1 class="pageTitle">Agent 工作流</h1>
      <p class="pageMeta">可控的多步骤知识检索与文档管理工具。每次执行均记录审计轨迹，高风险操作需用户确认。</p>
      ${renderCreatePanel()}
      <div id="agentRunList" style="padding:24px"><span class="spinner"></span> 加载运行记录...</div>
    </div>`;

  bindCreateEvents(container, gid);
  await loadRunList(gid);
}

function renderCreatePanel() {
  return `
    <div class="panel">
      <div class="panelHeader">新建 Agent 运行</div>
      <div class="panelBody">
        <label class="formLabel">目标描述</label>
        <textarea id="agentGoalInput" class="formTextarea" rows="2" placeholder="例如：检索当前知识库中关于 Ontology 的所有文档并总结关键概念"></textarea>
        <div class="exampleGoals" style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0">
          ${EXAMPLE_GOALS.map((g, i) => `<button class="exampleGoalBtn secondary small" data-goal="${esc(g)}">${i + 1}. ${esc(g)}</button>`).join('')}
        </div>
        <button id="startAgentBtn" class="primary">启动 Agent</button>
        <span id="agentCreateError" class="formError" style="display:none"></span>
      </div>
    </div>`;
}

function bindCreateEvents(container, gid) {
  container.querySelectorAll('.exampleGoalBtn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('agentGoalInput').value = btn.dataset.goal;
    });
  });

  document.getElementById('startAgentBtn').addEventListener('click', async () => {
    const goal = document.getElementById('agentGoalInput').value.trim();
    if (!goal) { showToast('请输入目标描述', 'warn'); return; }

    const btn = document.getElementById('startAgentBtn');
    const errEl = document.getElementById('agentCreateError');
    btn.disabled = true;
    if (errEl) errEl.style.display = 'none';

    try {
      await api(`/groups/${gid}/agent/runs`, { method: 'POST', body: JSON.stringify({ goal }) });
      document.getElementById('agentGoalInput').value = '';
      await loadRunList(gid);
      showToast('Agent 运行已创建，点击查看详情并执行。', 'success');
    } catch (err) {
      if (errEl) {
        errEl.textContent = '创建失败：' + (err.detail || '服务异常');
        errEl.style.display = 'block';
      }
    } finally {
      btn.disabled = false;
    }
  });
}

async function loadRunList(gid) {
  const el = document.getElementById('agentRunList');
  if (!el) return;

  try {
    const runs = await api(`/groups/${gid}/agent/runs`) || [];
    if (!runs.length) {
      el.innerHTML = `
        <div class="emptyState">
          <div class="emptyIcon">A</div>
          <p class="emptyTitle">暂无 Agent 运行</p>
          <p class="emptyHint">创建一个 Agent 运行来执行知识检索或文档管理任务。</p>
        </div>`;
      return;
    }

    el.innerHTML = `
      <table class="dataTable">
        <thead><tr><th>目标</th><th>状态</th><th>阶段</th><th>步骤</th><th>创建时间</th><th>操作</th></tr></thead>
        <tbody>${runs.map(r => `
          <tr>
            <td><strong>${esc(truncate(r.goal, 60))}</strong></td>
            <td>${statusBadge(r.status)}</td>
            <td class="muted">${PHASE_LABELS[r.current_phase] || r.current_phase || '—'}</td>
            <td>${r.step_count}</td>
            <td class="muted">${new Date(r.created_at).toLocaleString()}</td>
            <td><button class="secondary small viewAgentBtn" data-id="${r.id}">查看</button></td>
          </tr>
        `).join('')}</tbody>
      </table>`;

    el.querySelectorAll('.viewAgentBtn').forEach(btn => {
      btn.addEventListener('click', () => renderDetail(container, gid, btn.dataset.id));
    });
  } catch (err) {
    el.innerHTML = '<p class="muted">加载运行记录失败。</p>';
  }
}

/* ── Detail View ─────────────────────────────────────────────────── */

async function renderDetail(container, gid, runId) {
  container.innerHTML = '<div style="padding:24px"><span class="spinner"></span> 加载运行详情...</div>';

  try {
    const run = await api(`/groups/${gid}/agent/runs/${runId}`);
    container.innerHTML = `
      <div class="agentDetail">
        <div class="detailHeader" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px">
          <button class="secondary small" id="backToListBtn">← 返回列表</button>
          <h1 class="pageTitle" style="margin:0">Agent 运行详情</h1>
        </div>

        ${renderRunMeta(run)}
        ${run.plan_json?.length ? renderPlanJson(run.plan_json) : ''}
        ${renderActionBar(run, gid)}
        ${renderFinalAnswer(run)}
        ${renderTimelinePanel(run)}
      </div>`;

    bindDetailEvents(container, gid, runId, run);
  } catch (err) {
    container.innerHTML = `<div class="error" style="padding:24px">
      <p>加载详情失败：${esc(err.detail || err.message)}</p>
      <button class="secondary" onclick="location.hash='#/groups/${gid}/agent'">返回列表</button>
    </div>`;
  }
}

function renderRunMeta(run) {
  return `
    <div class="panel">
      <div class="panelHeader">运行信息</div>
      <div class="panelBody">
        <table class="metaTable">
          <tr><td class="metaLabel">目标</td><td>${esc(run.goal)}</td></tr>
          <tr><td class="metaLabel">状态</td><td>${statusBadge(run.status)}</td></tr>
          <tr><td class="metaLabel">阶段</td><td>${PHASE_LABELS[run.current_phase] || run.current_phase || '—'}</td></tr>
          <tr><td class="metaLabel">步骤数</td><td>${run.step_count}</td></tr>
          <tr><td class="metaLabel">创建时间</td><td class="muted">${new Date(run.created_at).toLocaleString()}</td></tr>
          ${run.finished_at ? `<tr><td class="metaLabel">完成时间</td><td class="muted">${new Date(run.finished_at).toLocaleString()}</td></tr>` : ''}
        </table>
      </div>
    </div>`;
}

function renderFinalAnswer(run) {
  if (!run.final_answer) return '';
  if (run.status === 'failed') {
    return `<div class="panel" style="border-left:3px solid var(--danger, #e74c3c)"><div class="panelHeader">运行失败</div><div class="panelBody">${esc(run.final_answer)}</div></div>`;
  }
  if (run.status === 'stopped') {
    return `<div class="panel"><div class="panelHeader">运行已停止</div><div class="panelBody">用户中止了此次运行。</div></div>`;
  }
  return `<div class="panel"><div class="panelHeader">最终回答</div><div class="panelBody" style="white-space:pre-wrap">${esc(run.final_answer)}</div></div>`;
}

function renderActionBar(run, gid) {
  const canExecute = ['created', 'planning', 'executing'].includes(run.status);
  const needsConfirm = run.status === 'awaiting_confirmation';

  if (!canExecute && !needsConfirm) return '';

  return `
    <div class="panel" style="border-left:3px solid var(--brand-blue, #3498db)">
      <div class="panelHeader">操作</div>
      <div class="panelBody">
        ${canExecute ? `
          <button id="executeBtn" class="primary">执行下一步</button>
          <span style="margin-left:12px;color:var(--text-muted,#888);font-size:13px">Agent 将分析当前状态并决定下一步操作。</span>
        ` : ''}
        ${needsConfirm ? renderHITLPanel() : ''}
      </div>
    </div>`;
}

function renderHITLPanel() {
  return `
    <div style="background:var(--warn-bg, #fff8e1);border:1px solid var(--warn-border, #f9a825);border-radius:6px;padding:16px;margin-top:8px">
      <strong style="color:var(--warn-text, #e65100)">⚠ 高风险操作需要确认</strong>
      <p style="margin:8px 0;color:var(--text-secondary, #666)">Agent 请求执行一个可能影响数据的操作，请审查步骤详情后决定。</p>
      <div style="display:flex;gap:8px;margin-top:12px">
        <button id="hitlConfirmBtn" class="primary">确认执行</button>
        <button id="hitlRejectBtn" class="secondary">拒绝</button>
        <button id="hitlStopBtn" class="danger">停止运行</button>
      </div>
      <span id="hitlError" class="formError" style="display:none"></span>
    </div>`;
}

function renderPlanJson(plan) {
  const items = plan.map(p => {
    if (typeof p === 'string') return `<li>${esc(p)}</li>`;
    const desc = p.step || p.description || p.task || JSON.stringify(p);
    return `<li>${esc(String(desc))}</li>`;
  }).join('');

  return `
    <details class="planDetails" style="margin-bottom:16px">
      <summary style="cursor:pointer;padding:8px 12px;background:var(--surface, #f5f5f5);border-radius:6px;font-weight:600">
        📋 执行计划 (${plan.length} 步)
      </summary>
      <ol style="padding:12px 12px 12px 28px;margin:0">${items}</ol>
    </details>`;
}

function renderTimelinePanel(run) {
  const steps = run.steps || [];
  return `
    <div class="panel">
      <div class="panelHeader">步骤时间线</div>
      <div class="panelBody">
        ${steps.length ? steps.map((s, i) => renderStep(s, i)).join('') : '<p class="muted">暂无步骤。</p>'}
      </div>
    </div>`;
}

function renderStep(s) {
  const typeLabel = STEP_TYPE_LABELS[s.action_type] || s.action_type;
  const isAskUser = s.action_type === 'ask_user';
  const isResponseEvent = s.action_detail?.response_event;
  const isConfirmed = s.action_detail?.confirmed;
  const isRejected = s.action_detail?.rejected;

  let actionDetailHtml = '';
  if (s.action_detail && Object.keys(s.action_detail).length) {
    const detailJson = JSON.stringify(s.action_detail, null, 2);
    actionDetailHtml = `
      <details class="stepSubDetail" style="margin-top:6px">
        <summary style="cursor:pointer;font-size:12px;color:var(--brand-blue, #2980b9)">查看详情</summary>
        <pre style="background:var(--surface, #f0f0f0);padding:8px;border-radius:4px;font-size:12px;overflow-x:auto;margin-top:4px">${esc(detailJson)}</pre>
      </details>`;
  }

  const obsText = s.observation || '';
  let obsHtml = '';
  if (obsText.length > 200) {
    obsHtml = `
      <details class="stepSubDetail" style="margin-top:6px">
        <summary style="cursor:pointer;font-size:12px;color:var(--brand-blue, #2980b9)">观察结果</summary>
        <pre style="background:var(--surface, #f0f0f0);padding:8px;border-radius:4px;font-size:12px;overflow-x:auto;white-space:pre-wrap;max-height:300px;overflow-y:auto;margin-top:4px">${esc(obsText)}</pre>
      </details>`;
  } else if (obsText) {
    obsHtml = `<div class="stepObs" style="font-size:13px;color:var(--text-secondary, #555);margin-top:6px;padding:6px 8px;background:var(--surface, #f8f8f8);border-radius:4px;white-space:pre-wrap">${esc(obsText)}</div>`;
  }

  const errorHtml = s.error_message
    ? `<div class="stepError" style="color:var(--danger, #e74c3c);font-size:13px;margin-top:6px">❌ ${esc(s.error_message)}</div>` : '';

  let userTag = '';
  if (isResponseEvent) {
    if (isConfirmed) userTag = '<span style="background:#e8f5e9;color:#2e7d32;padding:1px 8px;border-radius:10px;font-size:11px;margin-left:4px">用户确认 ✓</span>';
    else if (isRejected) userTag = '<span style="background:#fbe9e7;color:#c62828;padding:1px 8px;border-radius:10px;font-size:11px;margin-left:4px">用户拒绝 ✗</span>';
    else userTag = '<span style="background:#e3f2fd;color:#1565c0;padding:1px 8px;border-radius:10px;font-size:11px;margin-left:4px">用户响应</span>';
  }

  const timeHtml = s.finished_at
    ? `<span style="font-size:11px;color:var(--text-muted, #999)">${new Date(s.finished_at).toLocaleString()}</span>`
    : s.started_at
      ? `<span style="font-size:11px;color:var(--text-muted, #999)">${new Date(s.started_at).toLocaleString()} · 进行中</span>`
      : '';

  const statusDot = s.status === 'completed' ? '✓' : s.status === 'failed' ? '✗' : s.status === 'running' ? '●' : '○';
  const dotColor = s.status === 'failed' ? 'color:var(--danger, #e74c3c)' : s.status === 'running' ? 'color:var(--brand-blue, #3498db)' : '';

  const borderColor = s.status === 'failed' ? 'border-left-color: var(--danger, #e74c3c)' : isAskUser ? 'border-left-color: var(--brand-amber, #f9a825)' : '';

  return `
    <div style="border-left:3px solid var(--border, #ddd);padding:8px 16px;margin-bottom:8px;${borderColor}">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px">
        <span style="font-weight:600;font-size:13px;color:var(--text-muted, #888)">#${s.step_index}</span>
        <span style="font-weight:600;font-size:13px">${typeLabel}</span>
        <span style="font-size:11px;color:var(--text-muted, #999);background:var(--surface, #f0f0f0);padding:2px 6px;border-radius:4px">${PHASE_LABELS[s.phase] || s.phase}</span>
        <span style="font-size:16px;${dotColor}">${statusDot}</span>
        ${userTag}
        ${timeHtml}
      </div>
      <div style="font-size:14px;color:var(--text-secondary, #555);margin:4px 0">${esc(s.thought)}</div>
      ${actionDetailHtml}
      ${obsHtml}
      ${errorHtml}
    </div>`;
}

/* ── Detail Events ───────────────────────────────────────────────── */

function bindDetailEvents(container, gid, runId) {
  document.getElementById('backToListBtn')?.addEventListener('click', async () => {
    await renderList(container, gid);
  });

  document.getElementById('executeBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('executeBtn');
    btn.disabled = true;
    btn.textContent = '执行中...';
    try {
      await api(`/groups/${gid}/agent/runs/${runId}/execute`, { method: 'POST' });
      await renderDetail(container, gid, runId);
    } catch (err) {
      showToast('执行失败：' + (err.detail || '服务异常'), 'error');
      await renderDetail(container, gid, runId);
    }
  });

  document.getElementById('hitlConfirmBtn')?.addEventListener('click', () => respond(gid, runId, 'yes', container));
  document.getElementById('hitlRejectBtn')?.addEventListener('click', () => respond(gid, runId, 'no', container));
  document.getElementById('hitlStopBtn')?.addEventListener('click', () => respond(gid, runId, 'stop', container));
}

async function respond(gid, runId, response, container) {
  const errEl = document.getElementById('hitlError');
  const buttons = document.querySelectorAll('.hitlActions button, #hitlConfirmBtn, #hitlRejectBtn, #hitlStopBtn');
  buttons.forEach(b => { b.disabled = true; });
  if (errEl) errEl.style.display = 'none';

  try {
    await api(`/groups/${gid}/agent/runs/${runId}/respond`, {
      method: 'POST',
      body: JSON.stringify({ response }),
    });
    await renderDetail(container, gid, runId);
    const label = response === 'yes' ? '已确认执行' : response === 'no' ? '已拒绝操作' : '已停止运行';
    showToast(label, 'success');
  } catch (err) {
    if (errEl) {
      errEl.textContent = '操作失败：' + (err.detail || '服务异常');
      errEl.style.display = 'block';
    }
    buttons.forEach(b => { b.disabled = false; });
  }
}

/* ── Shared Helpers ───────────────────────────────────────────────── */

function statusBadge(status) {
  const style = STATUS_STYLE[status] || '';
  const label = STATUS_LABELS[status] || status;
  return `<span class="statusBadge ${style}">${label}</span>`;
}

function truncate(s, max) {
  if (!s) return '';
  return s.length > max ? s.slice(0, max) + '...' : s;
}
