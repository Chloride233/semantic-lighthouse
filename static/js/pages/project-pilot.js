/** Pilot stage — query workbench */
import { api } from '../api.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

export async function renderPilotStage(container, gid, pid, project, reloadProject, isOwnerAdmin) {
  const main = document.getElementById('projectMain');
  if (!main) return;
  main.innerHTML = '<div class="loading"><span class="spinner"></span>加载 Pilot 数据...</div>';

  let bindings, contractInfo = null;
  try {
    bindings = await api(`/groups/${gid}/projects/${pid}/runtime/bindings`);
    if (!Array.isArray(bindings) || bindings.length === 0) {
      main.innerHTML = '<div class="stagePanel"><p class="muted">尚无数据绑定。请先在验证阶段生成绑定。</p></div>';
      return;
    }
    const pkgsData = await api(`/groups/${gid}/projects/${pid}/model-drafts/packages?limit=1`);
    const pkg = (pkgsData.packages || [])[0];
    if (pkg) {
      try { contractInfo = await api(`/groups/${gid}/projects/${pid}/model-drafts/packages/${pkg.id}/contract`); } catch (_) {}
    }
  } catch (err) {
    main.innerHTML = `<div class="error"><p>${esc(err.humanMessage || err.message)}</p></div>`;
    return;
  }

  const props = contractInfo?.properties || [];
  const propVT = {};
  for (const p of props) propVT[p.api_name] = p.value_type || 'string';

  const bindingOpts = bindings.map((b, i) => ({ ...b, fields: Object.keys(b.property_mappings || {}), idx: i }));

  main.innerHTML = `
    <div class="stagePanel"><div class="stagePanelHead"><h2>Pilot — 查询工作台</h2></div>
      <div class="queryForm">
        <div class="queryRow">
          <label class="field"><span>对象类型</span><select id="qOT">${bindingOpts.map((b, i) => `<option value="${i}">${esc(b.object_type_api_name)}</option>`).join('')}</select></label>
          <label class="field"><span>返回行数</span><select id="qLimit"><option value="10">10</option><option value="20" selected>20</option><option value="50">50</option><option value="100">100</option></select></label>
        </div>
        <div id="qFields"></div>
        <div id="qFilter"></div>
        <div class="queryActions"><button class="primary" id="qRunBtn">执行查询</button><button class="secondary" id="qExplainBtn">仅查看说明</button></div>
      </div>
      <div id="qResults"></div>
    </div>
    <div class="stagePanel" id="pilotTaskSummary">
      <div class="stagePanelHead">
        <h2>项目任务</h2>
        <a href="#/groups/${gid}/tasks" class="supportLink">全部任务 →</a>
      </div>
      <div id="pilotTaskContent"><div class="loading"><span class="spinner"></span>加载任务...</div></div>
    </div>`;

  const fieldEl = document.getElementById('qFields');
  const filterEl = document.getElementById('qFilter');
  const otSelect = document.getElementById('qOT');
  const resultsEl = document.getElementById('qResults');

  function updateFields() {
    const bi = bindingOpts[parseInt(otSelect.value)];
    if (!bi) return;
    fieldEl.innerHTML = `<p class="muted">字段 (${bi.fields.length})</p><div class="fieldChecks">${bi.fields.map(f => {
      const vt = propVT[f] || 'string';
      return `<label class="fieldCheck"><input type="checkbox" class="qField" value="${esc(f)}" checked /> ${esc(f)} <span class="typeTag txt">${esc(vt)}</span></label>`;
    }).join('')}</div>`;

    filterEl.innerHTML = `<p class="muted">过滤（可选）</p><div class="queryRow">
      <select id="qFilterField"><option value="">无过滤</option>${bi.fields.map(f => `<option value="${esc(f)}">${esc(f)}</option>`).join('')}</select>
      <span id="qFilterInput"></span></div>`;
    document.getElementById('qFilterField')?.addEventListener('change', updateFilterInput);
    updateFilterInput();
  }

  function updateFilterInput() {
    const fname = document.getElementById('qFilterField')?.value;
    const wrap = document.getElementById('qFilterInput');
    if (!wrap || !fname) { wrap.innerHTML = ''; return; }
    const vt = propVT[fname] || 'string';
    if (vt === 'boolean') {
      wrap.innerHTML = '<select id="qFilterVal"><option value="true">true</option><option value="false">false</option></select>';
    } else if (vt === 'integer' || vt === 'number') {
      wrap.innerHTML = `<input id="qFilterVal" type="number" step="${vt === 'integer' ? '1' : 'any'}" />`;
    } else if (vt === 'date') {
      wrap.innerHTML = '<input id="qFilterVal" type="date" />';
    } else if (vt === 'datetime') {
      wrap.innerHTML = '<input id="qFilterVal" type="datetime-local" />';
    } else {
      wrap.innerHTML = '<input id="qFilterVal" type="text" />';
    }
  }

  otSelect.addEventListener('change', updateFields);
  updateFields();

  function getTypedFilterValue(vt) {
    const el = document.getElementById('qFilterVal');
    if (!el) return undefined;
    const raw = el.value;
    if (raw === '' || raw === undefined) return undefined;
    if (vt === 'integer') { const n = Number.parseInt(raw, 10); return Number.isNaN(n) ? undefined : n; }
    if (vt === 'number') { const n = Number(raw); return Number.isNaN(n) ? undefined : n; }
    if (vt === 'boolean') return raw === 'true';
    return raw;
  }

  async function doQuery(explainOnly) {
    const bi = bindingOpts[parseInt(otSelect.value)];
    const checked = [...document.querySelectorAll('.qField:checked')].map(cb => cb.value);
    if (checked.length === 0) { resultsEl.innerHTML = '<p class="error">请至少选择一个字段</p>'; return; }

    const filterField = document.getElementById('qFilterField')?.value;
    const filterVT = filterField ? (propVT[filterField] || 'string') : null;
    const filterVal = filterField ? getTypedFilterValue(filterVT) : undefined;
    const limit = parseInt(document.getElementById('qLimit')?.value || '20');

    const body = { object_type: bi.object_type_api_name, fields: checked, limit, explain_only: explainOnly };
    if (filterField && filterVal !== undefined && filterVal !== '') {
      body.filters = { [filterField]: filterVal };
    }

    resultsEl.innerHTML = '<div class="loading"><span class="spinner"></span>查询中...</div>';
    try {
      const result = await api(`/groups/${gid}/projects/${pid}/runtime/query`, { method: 'POST', body: JSON.stringify(body) });
      resultsEl.innerHTML = explainOnly ? explainHTML(result.explain) : resultHTML(result);
      // Bind explain toggle via addEventListener (not inline script)
      const toggleBtn = document.getElementById('toggleExplainBtn');
      const explainBlock = document.getElementById('explainBlock');
      if (toggleBtn && explainBlock) {
        toggleBtn.addEventListener('click', () => {
          explainBlock.hidden = !explainBlock.hidden;
          toggleBtn.textContent = explainBlock.hidden ? '查看溯源▼' : '收起▲';
        });
      }
    } catch (err) {
      resultsEl.innerHTML = `<div class="error"><p>${esc(err.humanMessage || err.message)}</p></div>`;
    }
  }

  document.getElementById('qRunBtn')?.addEventListener('click', () => doQuery(false));
  document.getElementById('qExplainBtn')?.addEventListener('click', () => doQuery(true));

  loadTaskSummary(gid, pid, isOwnerAdmin);
}

const STATUS_LABELS = { pending: '待处理', in_progress: '进行中', done: '已完成', cancelled: '已取消' };
const STATUS_CLASS = { pending: 'badgeInfo', in_progress: 'badgeWarn', done: 'badgeOk', cancelled: 'badgeMuted' };

async function loadTaskSummary(gid, pid, isOwnerAdmin) {
  const contentEl = document.getElementById('pilotTaskContent');
  if (!contentEl) return;

  let tasks = [], total = 0;
  try {
    const result = await api(`/groups/${gid}/tasks?project_id=${pid}&limit=5`);
    tasks = result.tasks || [];
    total = result.total || 0;
  } catch (err) {
    contentEl.innerHTML = `<p class="muted">无法加载任务：${esc(err.humanMessage || err.message)}</p>`;
    return;
  }

  contentEl.innerHTML = renderTaskSummary(tasks, total, gid, pid, isOwnerAdmin);
  if (isOwnerAdmin) bindCreateTask(gid, pid);
}

function renderTaskSummary(tasks, total, gid, pid, isOwnerAdmin) {
  const hasTasks = total > 0;

  let html = '';

  if (!hasTasks) {
    html += `
      <div class="pilotTaskEmpty">
        <p class="muted">暂无任务。Pilot 阶段可创建后续行动项。</p>
      </div>`;
  } else {
    html += `
      <div class="pilotTaskList">
        ${tasks.slice(0, 5).map(t => `
          <div class="pilotTaskItem">
            <span class="badge ${STATUS_CLASS[t.status] || 'badgeMuted'}" style="font-size:var(--text-xs);flex-shrink:0">${STATUS_LABELS[t.status] || t.status}</span>
            <span class="pilotTaskTitle">${esc(t.title)}</span>
            <span class="muted" style="font-size:var(--text-xs);margin-left:auto;white-space:nowrap">${fmtShortDate(t.created_at)}</span>
          </div>
        `).join('')}
      </div>`;
    if (total > 5) {
      html += `<p class="muted" style="font-size:var(--text-xs);margin:6px 0 0">还有 ${total - 5} 个任务...</p>`;
    }
  }

  if (isOwnerAdmin) {
    html += `
      <div class="pilotTaskCreate">
        <input id="pilotTaskInput" type="text" placeholder="添加任务..." maxlength="200" autocomplete="off" />
        <button id="pilotTaskCreateBtn" class="secondary small">添加</button>
      </div>
      <p id="pilotTaskError" class="formError" style="display:none"></p>`;
  }

  return html;
}

function bindCreateTask(gid, pid) {
  const input = document.getElementById('pilotTaskInput');
  const btn = document.getElementById('pilotTaskCreateBtn');
  const errEl = document.getElementById('pilotTaskError');
  if (!input || !btn) return;

  const submit = async () => {
    const title = input.value.trim();
    if (!title) { if (errEl) { errEl.textContent = '请输入任务标题。'; errEl.style.display = 'block'; } return; }
    if (errEl) errEl.style.display = 'none';
    btn.disabled = true;
    btn.textContent = '...';
    try {
      await api(`/groups/${gid}/tasks`, {
        method: 'POST',
        body: JSON.stringify({
          title,
          description: '',
          source_type: 'manual',
          source_id: `manual-${Date.now().toString(36)}`,
          project_id: pid,
        }),
      });
      input.value = '';
      showToast('任务已创建', 'success');
      loadTaskSummary(gid, pid, true);
    } catch (err) {
      if (errEl) { errEl.textContent = err.humanMessage || err.message || '创建失败'; errEl.style.display = 'block'; }
    } finally {
      btn.disabled = false;
      btn.textContent = '添加';
    }
  };

  btn.addEventListener('click', submit);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submit();
  });
}

function fmtShortDate(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch (_) { return iso.slice(0, 16); }
}

function resultHTML(result) {
  const rows = result.rows || [];
  if (rows.length === 0) {
    let html = '<p class="muted">查询无结果。</p>';
    if (result.explain) html += explainHTML(result.explain);
    return html;
  }
  const cols = Object.keys(rows[0]);
  return `<div class="queryResultMeta"><span>${result.row_count} 行</span><button class="linkBtn" id="toggleExplainBtn">查看溯源▼</button></div>
    <div id="explainBlock" hidden>${explainHTML(result.explain)}</div>
    <div class="queryTableWrap"><table class="profileTable"><thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${esc(r[c] !== null && r[c] !== undefined ? String(r[c]) : '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function explainHTML(explain) {
  if (!explain) return '';
  const trunc = explain.scan_truncated ? ' ⚠ 扫描已截断' : '';
  const items = [
    ['Package', `${(explain.package_id || '').slice(0, 8)}… v${explain.package_version}`],
    ['Semantic Hash', (explain.package_semantic_hash || '').slice(0, 24) + '…'],
    ['Binding', (explain.binding_id || '').slice(0, 8) + '…'],
    ['Dataset', `${(explain.dataset_id || '').slice(0, 8)}… hash:${(explain.dataset_content_hash || '').slice(0, 12)}`],
    ['Fields', (explain.selected_fields || []).join(', ')],
    ['Filter Fields', (explain.filter_field_names || []).join(', ') || 'none'],
    ['Limit/Offset', `${explain.limit}/${explain.offset}`],
    ['Scanned', `${explain.scanned_rows ?? '?'} / ${explain.scan_limit ?? '?'}${trunc}`],
    ['Matched', explain.matched_before_paging ?? '?'],
  ];
  return `<div class="explainBox">${items.map(([k, v]) => `<div><strong>${esc(k)}:</strong> <span class="muted">${esc(v)}</span></div>`).join('')}</div>`;
}
