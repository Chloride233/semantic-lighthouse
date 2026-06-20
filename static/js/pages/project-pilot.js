/** Pilot stage — query workbench */
import { api } from '../api.js';
import { state } from '../state.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

const FIELD_VT_ALIAS = { string: 's', integer: 'i', number: 'n', boolean: 'b', date: 'd', datetime: 'dt' };

export async function renderPilotStage(container, gid, pid, project, reloadProject, isOwnerAdmin) {
  const main = document.getElementById('projectMain');
  if (!main) return;

  main.innerHTML = '<div class="loading"><span class="spinner"></span>加载 Pilot 数据...</div>';

  let bindings, contractInfo;
  try {
    bindings = await api(`/groups/${gid}/projects/${pid}/runtime/bindings`);
    const pkgsData = await api(`/groups/${gid}/projects/${pid}/model-drafts/packages?limit=1`);
    const pkg = (pkgsData.packages || [])[0];
    contractInfo = pkg ? await api(`/groups/${gid}/projects/${pid}/model-drafts/packages/${pkg.id}/contract`).catch(() => null) : null;
  } catch (err) {
    main.innerHTML = `<div class="error"><p>${esc(err.humanMessage || err.message)}</p></div>`;
    return;
  }

  const bindingList = bindings || [];
  renderQueryUI(main, gid, pid, bindingList, contractInfo);
}

function renderQueryUI(main, gid, pid, bindingList, contractInfo) {
  if (bindingList.length === 0) {
    main.innerHTML = '<div class="stagePanel"><p class="muted">尚无数据绑定。请先在验证阶段生成绑定。</p></div>';
    return;
  }

  const props = contractInfo?.properties || [];
  const propVT = {};
  for (const p of props) propVT[p.api_name] = p.value_type || 'string';

  // Find properties for each object type from its binding
  const bindingOpts = bindingList.map((b, i) => {
    const fields = Object.keys(b.property_mappings || {});
    return { ...b, fields, idx: i };
  });

  main.innerHTML = `
    <div class="stagePanel"><div class="stagePanelHead"><h2>Pilot — 查询工作台</h2></div>
      <div class="queryForm" id="queryForm">
        <div class="queryRow">
          <label class="field"><span>对象类型</span>
            <select id="qOT">${bindingOpts.map((b, i) => `<option value="${i}">${esc(b.object_type_api_name)}</option>`).join('')}</select>
          </label>
          <label class="field"><span>返回行数</span>
            <select id="qLimit"><option value="10">10</option><option value="20" selected>20</option><option value="50">50</option><option value="100">100</option></select>
          </label>
        </div>
        <div id="qFields" class="queryFields"></div>
        <div id="qFilter" class="queryFilter"></div>
        <div class="queryActions">
          <button class="primary" id="qRunBtn">执行查询</button>
          <button class="secondary" id="qExplainBtn">仅查看说明</button>
        </div>
      </div>
      <div id="qResults"></div>
    </div>
  `;

  const fieldEl = document.getElementById('qFields');
  const filterEl = document.getElementById('qFilter');
  const otSelect = document.getElementById('qOT');

  function updateFields() {
    const bi = bindingOpts[parseInt(otSelect.value)];
    if (!bi) return;
    fieldEl.innerHTML = `<p class="muted">字段 (${bi.fields.length})</p><div class="fieldChecks">${bi.fields.map(f => {
      const vt = propVT[f] || 'string';
      return `<label class="fieldCheck"><input type="checkbox" class="qField" value="${esc(f)}" checked data-vt="${esc(vt)}" /> ${esc(f)} <span class="typeTag ${FIELD_VT_ALIAS[vt] || 'txt'}">${esc(vt)}</span></label>`;
    }).join('')}</div>`;

    filterEl.innerHTML = `<p class="muted">过滤（可选，最多一个等值条件）</p>
      <div class="queryRow">
        <select id="qFilterField"><option value="">无过滤</option>${bi.fields.map(f => `<option value="${esc(f)}">${esc(f)}</option>`).join('')}</select>
        <span id="qFilterInput"></span>
      </div>`;

    document.getElementById('qFilterField')?.addEventListener('change', updateFilterInput);
    updateFilterInput();
  }

  function updateFilterInput() {
    const fname = document.getElementById('qFilterField')?.value;
    const wrap = document.getElementById('qFilterInput');
    if (!wrap || !fname) { if (wrap) wrap.innerHTML = ''; return; }
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

  async function doQuery(explainOnly) {
    const bi = bindingOpts[parseInt(otSelect.value)];
    const checked = [...document.querySelectorAll('.qField:checked')].map(cb => cb.value);
    const filterField = document.getElementById('qFilterField')?.value;
    const filterValEl = document.getElementById('qFilterVal');
    const filterVal = filterField && filterValEl ? filterValEl.value : undefined;
    const limit = parseInt(document.getElementById('qLimit')?.value || '20');
    const resultsEl = document.getElementById('qResults');

    const body = { object_type: bi.object_type_api_name, fields: checked, limit, explain_only: explainOnly };
    if (filterField && filterVal !== undefined && filterVal !== '') {
      body.filters = { [filterField]: filterVal };
    }

    resultsEl.innerHTML = '<div class="loading"><span class="spinner"></span>查询中...</div>';

    try {
      const result = await api(`/groups/${gid}/projects/${pid}/runtime/query`, {
        method: 'POST', body: JSON.stringify(body),
      });
      if (explainOnly) {
        resultsEl.innerHTML = explainHTML(result.explain);
      } else {
        resultsEl.innerHTML = resultHTML(result);
      }
    } catch (err) {
      resultsEl.innerHTML = `<div class="error"><p>${esc(err.humanMessage || err.message)}</p></div>`;
    }
  }

  document.getElementById('qRunBtn')?.addEventListener('click', () => doQuery(false));
  document.getElementById('qExplainBtn')?.addEventListener('click', () => doQuery(true));
}

function resultHTML(result) {
  const rows = result.rows || [];
  if (rows.length === 0) return '<p class="muted">查询无结果。</p>' + explainHTML(result.explain);

  const cols = Object.keys(rows[0]);
  return `
    <div class="queryResultMeta"><span>${result.row_count} 行</span> <button class="linkBtn" id="toggleExplain">查看溯源▼</button></div>
    <div id="explainBlock" hidden>${explainHTML(result.explain)}</div>
    <div class="queryTableWrap"><table class="profileTable"><thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${esc(r[c] !== null && r[c] !== undefined ? String(r[c]) : '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
    <script>document.getElementById('toggleExplain')?.addEventListener('click', function(){const e=document.getElementById('explainBlock');e.hidden=!e.hidden;this.textContent=e.hidden?'查看溯源▼':'收起▲';})</script>
  `;
}

function explainHTML(explain) {
  if (!explain) return '';
  const items = [
    ['Package', `${explain.package_id?.slice(0, 8)}… v${explain.package_version}`],
    ['Semantic Hash', explain.package_semantic_hash?.slice(0, 24) + '…'],
    ['Binding', explain.binding_id?.slice(0, 8) + '…'],
    ['Dataset', explain.dataset_id?.slice(0, 8) + '… hash:' + (explain.dataset_content_hash?.slice(0, 12) || '')],
    ['Fields', (explain.selected_fields || []).join(', ')],
    ['Filters', (explain.filter_field_names || []).join(', ') || 'none'],
    ['Limit/Offset', `${explain.limit}/${explain.offset}`],
    ['Scanned', `${explain.scanned_rows ?? '?'} / ${explain.scan_limit ?? '?'} ${explain.scan_truncated ? '(truncated)' : ''}`],
    ['Matched', explain.matched_before_paging ?? '?'],
  ];
  return `<div class="explainBox">${items.map(([k, v]) => `<div><strong>${esc(k)}:</strong> <span class="muted">${esc(v)}</span></div>`).join('')}</div>`;
}
