import { api } from '../api.js';
import { state } from '../state.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

const ENTITY_COLORS = {
  Concept: '#0d9488', Vendor: '#7c3aed', Product: '#2563eb',
  Methodology: '#059669', Case: '#d97706', Person: '#dc2626',
  Research: '#0891b2', Proposal: '#9333ea', FAQ: '#4b5563',
};
const ELABEL = { Concept: '概念', Vendor: '厂商', Product: '产品', Methodology: '方法论', Case: '案例', Person: '人物', Research: '研究', Proposal: '方案', FAQ: 'FAQ' };
const TL = { pending: '待处理', confirmed: '已确认', ignored: '已忽略' };
const TS = { pending: 'badgeInfo', confirmed: 'badgeOk', ignored: 'badgeMuted' };
const SLABEL = { stub: '存根', draft: '草稿', reviewed: '已审校', canonical: '权威' };
const SRC = { 'official-doc': '官方', 'market-research': '调研', 'public-article': '公开', 'case-report': '案例', 'personal-analysis': '个人' };
const ICODE = { unresolved_wikilink: '未解析引用', duplicate_title: '重复标题', duplicate_alias: '重复别名', stale_eval_gold_doc_id: '过期评估引用', type_conflict: '类型冲突', missing_entity_type: '缺少实体类型', invalid_entity_type: '无效实体类型', invalid_document_type: '无效文档类型', missing_required_field: '缺少必填字段', invalid_controlled_value: '无效受控词', invalid_list_field: '列表格式错误' };

let _e = [], _r = [], _is = [], _sel = null;
let _graphScope = 'selected', _graphStatus = 'all';

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!state.accessToken) { container.innerHTML = '<p class="muted">请先登录。</p>'; return; }
  if (!gid) { container.innerHTML = '<p class="muted">请先选择工作区。</p>'; return; }

  const hash = location.hash.replace('#', '');
  const qp = new URLSearchParams(hash.split('?')[1] || '');
  const deepLinkEntityId = qp.get('entity_id') || '';

  container.innerHTML = `
    <div class="ontoPage">
      <div class="ontoHeader"><div><h1 class="pageTitle">Ontology 治理</h1><p class="pageMeta">实体、关系和治理问题的只读视图。编辑与建模在后续版本中开放。</p></div><div id="ontoActions"></div></div>
      <div class="ontoMetrics" id="ontoMetrics"><span class="spinner"></span> 加载中...</div>
      <div class="ontoBody">
        <div class="ontoCol ontoColLeft"><div class="ontoFilters" id="ontoFilters"></div><div class="ontoList" id="ontoList"><span class="spinner"></span> 加载实体...</div></div>
        <div class="ontoCol ontoColMid" id="ontoGraph"><div class="ontoGraphInner"><p class="muted">请选择实体以查看关系图谱。</p></div></div>
        <div class="ontoCol ontoColRight" id="ontoDetail"><p class="muted">请选择一个实体。</p></div>
      </div>
      <div id="ontoIssues"></div>
    </div>`;

  await init(gid, deepLinkEntityId);
}

async function init(gid, deepLinkEntityId = '') {
  const can = state.currentRole === 'owner' || state.currentRole === 'admin';
  document.getElementById('ontoActions').innerHTML = can
    ? '<button id="ontoScanBtn" class="primary">扫描 Ontology</button>'
    : '<span class="muted">只读视图</span>';

  document.getElementById('ontoScanBtn')?.addEventListener('click', async () => {
    const b = document.getElementById('ontoScanBtn'); b.disabled = true; b.textContent = '扫描中...';
    try { const r = await api(`/groups/${gid}/ontology/scan`, { method: 'POST' }); showToast(`扫描完成：${r.entity_count} 实体, ${r.relation_count} 关系, ${r.issue_count} 问题`, 'success'); await load(gid); }
    catch (e) { showToast('扫描失败：' + (e.detail || '服务异常'), 'error'); }
    finally { b.disabled = false; b.textContent = '扫描 Ontology'; }
  });
  await load(gid, deepLinkEntityId);
}

async function load(gid, deepLinkEntityId = '') {
  document.getElementById('ontoMetrics').innerHTML = '<span class="spinner"></span> 加载中...';
  try {
    const [er, rr, ir] = await Promise.all([
      api(`/groups/${gid}/ontology/entities?limit=100`), api(`/groups/${gid}/ontology/relations?limit=100`), api(`/groups/${gid}/ontology/issues?limit=100`)]);
    _e = er.entities || []; _r = rr.relations || []; _is = ir.issues || [];
    renderMetrics(); renderFilters(); renderList(); renderIssues();
    // Deep link: auto-select entity if provided and exists
    if (deepLinkEntityId && _e.some(x => x.id === deepLinkEntityId)) {
      selectEnt(deepLinkEntityId);
    } else if (_sel && _e.some(x => x.id === _sel)) {
      selectEnt(_sel);
    } else {
      _sel = null;
    }
  } catch (e) { document.getElementById('ontoMetrics').innerHTML = `<span class="error">加载失败：${esc(e.detail || '')}</span>`; }
}

function renderMetrics() {
  const u = _r.filter(r => r.status === 'unresolved').length;
  document.getElementById('ontoMetrics').innerHTML = `<div class="metric"><strong>${_e.length}</strong> 实体</div><div class="metric"><strong>${_r.length}</strong> 关系</div><div class="metric"><strong>${u}</strong> 未解析</div><div class="metric"><strong>${_is.length}</strong> 问题</div>`;
}

function renderFilters() {
  const ts = [...new Set(_e.map(e => e.entity_type))].sort();
  const ss = [...new Set(_e.map(e => e.status).filter(Boolean))].sort();
  document.getElementById('ontoFilters').innerHTML = `
    <input id="ontoQ" type="text" placeholder="搜索标题或别名..." class="ontoSearch" />
    <select id="ontoET"><option value="">全部类型</option>${ts.map(t => `<option>${t}</option>`).join('')}</select>
    <select id="ontoSt"><option value="">全部状态</option>${ss.map(s => `<option>${s}</option>`).join('')}</select>`;
  ['ontoQ', 'ontoET', 'ontoSt'].forEach(id => document.getElementById(id).addEventListener('input', renderList));
}

function renderList() {
  const q = (document.getElementById('ontoQ')?.value || '').toLowerCase();
  const et = document.getElementById('ontoET')?.value || '';
  const st = document.getElementById('ontoSt')?.value || '';
  let f = _e;
  if (et) f = f.filter(e => e.entity_type === et);
  if (st) f = f.filter(e => e.status === st);
  if (q) f = f.filter(e => (e.title + ' ' + (e.aliases || []).join(' ')).toLowerCase().includes(q));

  const el = document.getElementById('ontoList');
  if (!f.length) { el.innerHTML = '<p class="muted">无匹配实体。</p>'; return; }
  el.innerHTML = f.map(e => `
    <div class="ontoItem ${_sel === e.id ? 'selected' : ''}" data-id="${e.id}">
      <div class="ontoItemTitle">${esc(e.title)}</div>
      <div class="ontoItemMeta">
        <span class="badge" style="background:${ENTITY_COLORS[e.entity_type]||'#888'};color:#fff">${ELABEL[e.entity_type]||e.entity_type}</span>
        ${e.status ? `<span class="badge badgeInfo">${SLABEL[e.status]||e.status}</span>` : ''}
        ${e.source ? `<span class="badge badgeMuted">${SRC[e.source]||e.source}</span>` : ''}
      </div>
      ${e.tags?.length ? `<div class="ontoItemTags">${e.tags.map(t => `<span class="tag">${esc(t)}</span>`).join(' ')}</div>` : ''}
    </div>`).join('');
  el.querySelectorAll('.ontoItem').forEach(i => i.addEventListener('click', () => selectEnt(i.dataset.id)));
}

function selectEnt(id) {
  _sel = id; const e = _e.find(x => x.id === id); if (!e) return;
  renderList(); renderGraph(e); renderDetail(e);
}

function renderGraph(sel) {
  const c = document.getElementById('ontoGraph');
  if (!sel) { c.innerHTML = '<div class="ontoGraphInner"><p class="muted">请选择实体以查看关系图谱。</p></div>'; return; }

  const gid = state.currentGroupId;
  const can = state.currentRole === 'owner' || state.currentRole === 'admin';

  // Build the full 1-hop subgraph
  const out = _r.filter(r => r.source_entity_id === sel.id);
  const inn = _r.filter(r => r.target_entity_id === sel.id);
  const hopIds = new Set([sel.id]);
  out.forEach(r => r.target_entity_id && hopIds.add(r.target_entity_id));
  inn.forEach(r => hopIds.add(r.source_entity_id));
  const hopNodes = [...hopIds].map(id => _e.find(x => x.id === id)).filter(Boolean);
  const hopEdges = _r.filter(r => hopIds.has(r.source_entity_id) && hopIds.has(r.target_entity_id));

  // Scope: select visible ids
  let scopeIds = new Set(hopIds);
  if (_graphScope === 'visible') {
    const filterQ = (document.getElementById('ontoQ')?.value || '').toLowerCase();
    const filterET = document.getElementById('ontoET')?.value || '';
    const filterSt = document.getElementById('ontoSt')?.value || '';
    let visible = _e;
    if (filterET) visible = visible.filter(e => e.entity_type === filterET);
    if (filterSt) visible = visible.filter(e => e.status === filterSt);
    if (filterQ) visible = visible.filter(e => (e.title + ' ' + (e.aliases || []).join(' ')).toLowerCase().includes(filterQ));
    const visibleIds = new Set(visible.map(e => e.id));
    scopeIds = new Set([...hopIds].filter(id => visibleIds.has(id)));
  } else if (_graphScope === 'all') {
    scopeIds = new Set([...hopIds, ..._e.slice(0, 40).map(e => e.id)]);
  }

  let nodes = [...scopeIds].map(id => _e.find(x => x.id === id)).filter(Boolean);
  if (!nodes.find(n => n.id === sel.id)) nodes.push(sel);

  let edges = _r.filter(r => scopeIds.has(r.source_entity_id) && scopeIds.has(r.target_entity_id));
  if (_graphStatus !== 'all') edges = edges.filter(r => r.status === _graphStatus);

  // Edge list: include outbound edges even when target not in scope (for status filter)
  const allOut = _graphStatus !== 'all'
    ? out.filter(r => r.status === _graphStatus)
    : out;
  const unresolvedOut = allOut.filter(r => r.status === 'unresolved' || !r.target_entity_id);

  // Render graph controls
  let html = `<div class="ontoGraphControls">
    <label>范围 <select id="graphScope"><option value="selected"${_graphScope==='selected'?' selected':''}>选中实体</option><option value="visible"${_graphScope==='visible'?' selected':''}>过滤结果</option><option value="all"${_graphScope==='all'?' selected':''}>全部 (≤40)</option></select></label>
    <label>关系 <select id="graphStatus"><option value="all"${_graphStatus==='all'?' selected':''}>全部</option><option value="resolved"${_graphStatus==='resolved'?' selected':''}>已解析</option><option value="unresolved"${_graphStatus==='unresolved'?' selected':''}>未解析</option></select></label>
    ${can ? '' : '<span class="muted" style="font-size:11px">只读</span>'}
  </div>`;

  // SVG or empty
  if (nodes.length <= 1 && edges.length === 0) {
    html += `<div class="ontoGraphInner"><div class="emptyState"><div class="emptyIcon">🔗</div><div class="emptyTitle">暂无图谱数据</div><div class="emptyHint">${nodes.length<=1?'选中实体暂无关系。':'当前过滤条件下无匹配关系。'}${unresolvedOut.length?' 下方列出了 '+unresolvedOut.length+' 个未解析的引用目标。':''}</div></div></div>`;
  } else {
    const W = 480, H = 320, cx = W / 2, cy = H / 2, R = Math.min(W, H) * 0.35;
    const nm = {};
    nodes.forEach((n, i) => {
      const a = (i / nodes.length) * 2 * Math.PI - Math.PI / 2;
      nm[n.id] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R };
    });

    let svg = `<svg viewBox="0 0 ${W} ${H}" class="ontoSvg">`;
    // Edges with tooltips
    edges.forEach(r => {
      const a = nm[r.source_entity_id], b = nm[r.target_entity_id];
      if (!a || !b) return;
      const srcEnt = _e.find(x => x.id === r.source_entity_id);
      const tgtEnt = _e.find(x => x.id === r.target_entity_id);
      const srcName = srcEnt ? srcEnt.title : r.source_entity_id;
      const tgtName = tgtEnt ? tgtEnt.title : (r.target_path || '未解析');
      const dash = r.status === 'unresolved' ? 'stroke-dasharray:5,4' : '';
      const color = r.status === 'unresolved' ? '#d97706' : '#cbd5e1';
      svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${color}" stroke-width="1.5" ${dash} class="ontoEdge" data-sid="${r.source_entity_id}" data-tid="${r.target_entity_id}"><title>${esc(srcName)} → ${esc(tgtName)}&#10;状态: ${r.status==='resolved'?'已解析':'未解析'}${r.target_label? '&#10;标签: '+esc(r.target_label):''}</title></line>`;
    });
    // Nodes with tooltips
    nodes.forEach(n => {
      const p = nm[n.id]; if (!p) return;
      const s = n.id === sel.id;
      const label = ELABEL[n.entity_type] || n.entity_type;
      svg += `<circle cx="${p.x}" cy="${p.y}" r="${s ? 18 : 14}" fill="${ENTITY_COLORS[n.entity_type]||'#888'}" stroke="${s?'#1e293b':'#fff'}" stroke-width="${s?3:2}" class="ontoNode" data-id="${n.id}"><title>${esc(n.title)}&#10;类型: ${label}&#10;状态: ${SLABEL[n.status]||n.status||'—'}&#10;路径: ${esc(n.source_path)}</title></circle>`;
      svg += `<text x="${p.x}" y="${p.y + 28}" text-anchor="middle" font-size="10" fill="${s?'#1e293b':'#64748b'}" font-weight="${s?'600':'400'}">${esc(trunc(n.title, 14))}</text>`;
    });
    svg += '</svg>';
    html += `<div class="ontoGraphInner">${svg}<p class="muted" style="margin-top:8px;font-size:12px">${nodes.length} 节点，${edges.length} 连线</p></div>`;
  }

  // Legend
  const types = [...new Set(nodes.map(n => n.entity_type))].sort();
  html += `<div class="ontoLegend">
    <span class="legendItem"><span class="legendLine legendLineSolid"></span> 已解析</span>
    <span class="legendItem"><span class="legendLine legendLineDashed"></span> 未解析</span>
    ${types.map(t => `<span class="legendItem"><span class="legendDot" style="background:${ENTITY_COLORS[t]||'#888'}"></span> ${ELABEL[t]||t}</span>`).join('')}
  </div>`;

  // Unresolved targets list (always show for selected scope)
  if (_graphScope === 'selected' && unresolvedOut.length) {
    const unique = new Map();
    unresolvedOut.forEach(r => { const k = r.target_path || '?'; if (!unique.has(k)) unique.set(k, r); });
    html += `<div class="ontoUnresolvedList"><div class="ontoUnresolvedTitle">未解析引用 (${unique.size})</div><ul>`;
    unique.forEach((r, path) => {
      html += `<li><code>${esc(path)}</code>${r.target_label?` (${esc(r.target_label)})`:''}</li>`;
    });
    html += '</ul><p class="muted" style="font-size:11px">这些路径没有对应实体，可能是文档缺失或链接过时。</p></div>';
  }

  c.innerHTML = html;

  // Wire graph control events
  c.querySelector('#graphScope')?.addEventListener('change', e => { _graphScope = e.target.value; if (_sel) { const ent = _e.find(x => x.id === _sel); if (ent) renderGraph(ent); } });
  c.querySelector('#graphStatus')?.addEventListener('change', e => { _graphStatus = e.target.value; if (_sel) { const ent = _e.find(x => x.id === _sel); if (ent) renderGraph(ent); } });
  c.querySelectorAll('.ontoNode').forEach(n => n.addEventListener('click', () => selectEnt(n.dataset.id)));
}

function renderDetail(e) {
  const out = _r.filter(r => r.source_entity_id === e.id);
  const inn = _r.filter(r => r.target_entity_id === e.id);
  const eis = _is.filter(i => i.entity_id === e.id || i.document_id === e.document_id);
  document.getElementById('ontoDetail').innerHTML = `
    <div class="ontoDetailCard">
      <h3 style="margin:0 0 12px">${esc(e.title)}</h3>
      <div class="ontoDetailMeta"><span class="badge" style="background:${ENTITY_COLORS[e.entity_type]||'#888'};color:#fff">${ELABEL[e.entity_type]||e.entity_type}</span>${e.status ? `<span class="badge badgeInfo">${SLABEL[e.status]||e.status}</span>` : ''}${e.source ? `<span class="badge badgeMuted">${SRC[e.source]||e.source}</span>` : ''}</div>
      ${e.aliases?.length ? `<div class="ontoDMeta">别名：${e.aliases.map(a => esc(a)).join('、')}</div>` : ''}
      ${e.tags?.length ? `<div class="ontoDMeta">标签：${e.tags.map(t => `<span class="tag">${esc(t)}</span>`).join(' ')}</div>` : ''}
      <div class="ontoDMeta">路径：<code>${esc(e.source_path)}</code></div>
      <div class="ontoDMeta">文档：${esc(e.document_id)}</div>
      ${out.length ? `<details class="ontoDRels" open><summary>发出关系 (${out.length})</summary><ul>${out.map(r => { const t = _e.find(x => x.id === r.target_entity_id); const badge = r.status==='resolved' ? '<span class="badge badgeOk">已解析</span>' : '<span class="badge badgeMuted">未解析</span>'; const tgt = t ? `<span class="ontoRelTarget" data-eid="${t.id}">${esc(t.title)}</span>` : `<code class="ontoRelPath">${esc(trunc(r.target_path, 40))}</code>`; return `<li class="ontoRelItem">→ ${tgt}${r.target_label ? ` (${esc(r.target_label)})` : ''} ${badge}</li>`; }).join('')}</ul></details>` : '<div class="ontoDMeta">无发出关系</div>'}
      ${inn.length ? `<details class="ontoDRels" open><summary>进入关系 (${inn.length})</summary><ul>${inn.map(r => { const s = _e.find(x => x.id === r.source_entity_id); const tgt = s ? `<span class="ontoRelTarget" data-eid="${s.id}">${esc(s.title)}</span>` : `<code>${esc(r.source_entity_id)}</code>`; return `<li class="ontoRelItem">${tgt} → ${esc(r.target_path)}${r.target_label ? ` (${esc(r.target_label)})` : ''}</li>`; }).join('')}</ul></details>` : '<div class="ontoDMeta">无进入关系</div>'}
      ${eis.length ? `<details class="ontoDRels"><summary>相关问题 (${eis.length})</summary><ul>${eis.map(i => `<li><span class="badge ${i.severity==='error'?'badgeErr':'badgeWarn'}">${i.severity}</span> ${ICODE[i.code]||i.code} — ${esc(i.message)}</li>`).join('')}</ul></details>` : '<div class="ontoDMeta">无相关问题</div>'}
    </div>`;
  // Click handlers for relation target navigation
  document.querySelectorAll('.ontoRelTarget').forEach(el => {
    el.addEventListener('click', () => selectEnt(el.dataset.eid));
  });
}

function renderIssues() {
  const c = document.getElementById('ontoIssues'); if (!_is.length) { c.innerHTML = ''; return; }
  const canTriage = state.currentRole === 'owner' || state.currentRole === 'admin';

  // Build code options
  const codes = [...new Set(_is.map(i => i.code))].sort();

  // Issue filter state (module-level for simplicity)
  let _issueTriageFilter = _issueTriageFilter || 'all';
  let _issueCodeFilter = _issueCodeFilter || 'all';

  const renderFiltered = () => {
    let filtered = _is;
    if (_issueTriageFilter !== 'all') filtered = filtered.filter(i => (i.triage_status || 'pending') === _issueTriageFilter);
    if (_issueCodeFilter !== 'all') filtered = filtered.filter(i => i.code === _issueCodeFilter);

    const by = {};
    filtered.forEach(i => { (by[i.severity] || (by[i.severity] = [])).push(i); });

    let html = '';
    ['error', 'warning'].forEach(s => {
      if (!by[s]?.length) return;
      const color = s === 'error' ? 'var(--danger)' : 'var(--warn)';
      const emoji = s === 'error' ? '❌ 错误' : '⚠ 警告';
      html += `<div class="ontoIssueGroup"><strong style="color:${color}">${emoji} (${by[s].length})</strong><div class="ontoIssueList">`;
      by[s].forEach(i => {
        const ts = i.triage_status || 'pending';
        const tsLabel = TL[ts] || ts;
        const tsStyle = TS[ts] || 'badgeInfo';
        const ignoredClass = ts === 'ignored' ? ' ontoIssueIgnored' : '';
        const triageBadge = `<span class="badge ${tsStyle}">${tsLabel}</span>`;
        const triageBtns = canTriage ? `<span class="ontoTriageBtns">
          <button class="triageBtn triageConfirm" data-iid="${i.id}" title="确认">✓</button>
          <button class="triageBtn triageIgnore" data-iid="${i.id}" title="忽略">✕</button>
          <button class="triageBtn triageReset" data-iid="${i.id}" title="重置">↺</button>
        </span>` : '';
        const codeLabel = ICODE[i.code] || i.code;
        html += `<div class="ontoIssueItem${ignoredClass} ${i.entity_id ? ' clickable' : ''}" data-eid="${i.entity_id || ''}"><span class="badge ${s==='error'?'badgeErr':'badgeWarn'}">${codeLabel}</span><span>${esc(i.message)}</span>${triageBadge}${triageBtns}<span class="muted" style="font-size:11px">${esc(i.source_path)}</span></div>`;
      });
      html += '</div></div>';
    });

    const listEl = c.querySelector('.ontoIssueBody');
    if (listEl) {
      listEl.innerHTML = html || '<p class="muted">当前过滤条件下无匹配问题。</p>';
      // Rebind events
      listEl.querySelectorAll('.ontoIssueItem.clickable').forEach(el => el.addEventListener('click', () => selectEnt(el.dataset.eid)));
      if (canTriage) bindTriageBtns(listEl);
    }
  };

  const bindTriageBtns = (el) => {
    const gid = state.currentGroupId;
    el.querySelectorAll('.triageConfirm').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); doTriage(gid, b.dataset.iid, 'confirmed'); }));
    el.querySelectorAll('.triageIgnore').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); doTriage(gid, b.dataset.iid, 'ignored'); }));
    el.querySelectorAll('.triageReset').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); doTriage(gid, b.dataset.iid, 'pending'); }));
  };

  c.innerHTML = `<div class="panel"><div class="panelHeader">治理问题 (${_is.length})</div>
    <div class="ontoIssueFilters">
      <select id="issueTriageFilter"><option value="all">全部状态</option><option value="pending">待处理</option><option value="confirmed">已确认</option><option value="ignored">已忽略</option></select>
      <select id="issueCodeFilter"><option value="all">全部类型</option>${codes.map(co => `<option value="${co}">${ICODE[co]||co}</option>`).join('')}</select>
    </div>
    <div class="ontoIssueBody"></div></div>`;

  // Set initial filter values and render
  const triageSel = c.querySelector('#issueTriageFilter');
  const codeSel = c.querySelector('#issueCodeFilter');
  if (triageSel) { triageSel.value = _issueTriageFilter; triageSel.addEventListener('change', () => { _issueTriageFilter = triageSel.value; renderFiltered(); }); }
  if (codeSel) { codeSel.value = _issueCodeFilter; codeSel.addEventListener('change', () => { _issueCodeFilter = codeSel.value; renderFiltered(); }); }
  renderFiltered();
}

async function doTriage(gid, iid, status) {
  try {
    await api(`/groups/${gid}/ontology/issues/${iid}/triage`, { method: 'POST', body: JSON.stringify({ triage_status: status }) });
    // Refresh local data
    const issuesResp = await api(`/groups/${gid}/ontology/issues?limit=100`);
    _is = issuesResp.issues || [];
    renderIssues();
  } catch (e) { showToast('操作失败：' + (e.detail || '服务异常'), 'error'); }
}

function trunc(s, n) { return s && s.length > n ? s.slice(0, n) + '...' : s; }
