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
const DRAFT_TYPE_LABEL = { object_type: '对象类型', property: '属性', link_type: '关联类型', action_type: '动作类型' };
const DRAFT_STATUS = { proposed: '待审核', accepted: '已接受', rejected: '已拒绝' };
const QUALITY_L = { PASS: '通过', WARN: '警告', FAIL: '失败' };

/** Extract a human-readable message from an APIError for UI display. */
function errMsg(e) {
  const d = e?.detail;
  if (!d) return e?.message || e?.statusText || '请求失败';
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d.map(i => (i?.msg || i?.message || String(i))).join('; ');
  }
  return d.message || d.detail || String(e.status || '') + ' 错误';
}

let _e = [], _r = [], _is = [], _drafts = [], _packages = [], _quality = null;
let _sel = null, _activeTab = 'graph';
let _graphScope = 'selected', _graphStatus = 'all';
let _issueTriageFilter = 'all', _issueCodeFilter = 'all';
let _selDraft = null, _selPackage = null;
let _batchSelected = new Set();

function resetState() {
  _e = []; _r = []; _is = []; _drafts = []; _packages = []; _quality = null;
  _sel = null; _selDraft = null; _selPackage = null; _batchSelected = new Set();
  _graphScope = 'selected'; _graphStatus = 'all'; _activeTab = 'graph';
  _issueTriageFilter = 'all'; _issueCodeFilter = 'all';
}

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!state.accessToken) { container.innerHTML = '<p class="muted">请先登录。</p>'; return; }
  if (!gid) { container.innerHTML = '<p class="muted">请先选择工作区。</p>'; return; }
  resetState();

  const hash = location.hash.replace('#', '');
  const qp = new URLSearchParams(hash.split('?')[1] || '');
  const deepLinkEntityId = qp.get('entity_id') || '';

  container.innerHTML = `
    <div class="ontoPage">
      <div class="ontoHeader"><div><h1 class="pageTitle">Ontology 治理</h1><p class="pageMeta">实体、关系、建模、审核与契约。</p></div><div id="ontoActions" class="ontoActions"></div></div>
      <div class="ontoMetrics" id="ontoMetrics"><span class="spinner"></span> 加载中…</div>
      <div class="tabs" id="ontoTabs">
        <button class="tab${_activeTab==='overview'?' active':''}" data-tab="overview">总览</button>
        <button class="tab${_activeTab==='graph'?' active':''}" data-tab="graph">图谱</button>
        <button class="tab${_activeTab==='governance'?' active':''}" data-tab="governance">治理</button>
        <button class="tab${_activeTab==='modeling'?' active':''}" data-tab="modeling">建模</button>
        <button class="tab${_activeTab==='contracts'?' active':''}" data-tab="contracts">契约</button>
      </div>
      <div id="tab-overview" class="ontoTabContent"${_activeTab!=='overview'?' style="display:none"':''}></div>
      <div id="tab-graph" class="ontoTabContent"${_activeTab!=='graph'?' style="display:none"':''}>
        <div class="ontoBody">
          <div class="ontoCol ontoColLeft"><div class="ontoFilters" id="ontoFilters"></div><div class="ontoList" id="ontoList"><span class="spinner"></span> 加载实体…</div></div>
          <div class="ontoCol ontoColMid" id="ontoGraph"><div class="ontoGraphInner"><p class="muted">请选择实体以查看关系图谱。</p></div></div>
          <div class="ontoCol ontoColRight" id="ontoDetail"><p class="muted">请选择一个实体。</p></div>
        </div>
      </div>
      <div id="tab-governance" class="ontoTabContent"${_activeTab!=='governance'?' style="display:none"':''}>
        <div class="ontoIssueFilters" id="ontoIssueFilters"></div>
        <div class="ontoIssueBody" id="ontoIssueBody"></div>
      </div>
      <div id="tab-modeling" class="ontoTabContent"${_activeTab!=='modeling'?' style="display:none"':''}>
        <div class="ontoDrafts" id="ontoDraftsArea"><div class="muted">加载建模草稿…</div></div>
      </div>
      <div id="tab-contracts" class="ontoTabContent"${_activeTab!=='contracts'?' style="display:none"':''}>
        <div id="ontoContractsArea"><div class="muted">加载模型包…</div></div>
      </div>
    </div>`;

  bindTabs(container, gid);
  await init(gid, deepLinkEntityId);
}

function bindTabs(container, gid) {
  container.querySelectorAll('#ontoTabs .tab').forEach(t => {
    t.addEventListener('click', () => {
      _activeTab = t.dataset.tab;
      container.querySelectorAll('#ontoTabs .tab').forEach(x => { x.classList.toggle('active', x.dataset.tab === _activeTab); });
      container.querySelectorAll('.ontoTabContent').forEach(d => { d.style.display = 'none'; });
      const target = document.getElementById(`tab-${_activeTab}`);
      if (target) { target.style.display = ''; }
      if (_activeTab === 'overview') renderOverview();
      if (_activeTab === 'graph') { renderFilters(); renderList(); if (_sel) { const e = _e.find(x => x.id === _sel); if (e) renderGraph(e); renderDetail(e); } }
      if (_activeTab === 'governance') renderIssues();
      if (_activeTab === 'modeling') renderModeling(gid);
      if (_activeTab === 'contracts') renderContracts(gid);
    });
  });
}

async function init(gid, deepLinkEntityId) {
  const can = state.currentRole === 'owner' || state.currentRole === 'admin';
  document.getElementById('ontoActions').innerHTML = can
    ? '<button id="ontoScanBtn">扫描 Ontology</button>'
    : '<span class="muted" style="font-size:13px">只读视图</span>';

  document.getElementById('ontoScanBtn')?.addEventListener('click', async () => {
    const b = document.getElementById('ontoScanBtn'); b.disabled = true; b.textContent = '扫描中…';
    try { const r = await api(`/groups/${gid}/ontology/scan`, { method: 'POST' }); showToast(`扫描完成：${r.entity_count} 实体, ${r.relation_count} 关系, ${r.issue_count} 问题`, 'success'); await loadAll(gid); }
    catch (e) { showToast('扫描失败：' + errMsg(e), 'error'); }
    finally { b.disabled = false; b.textContent = '扫描 Ontology'; }
  });

  await loadAll(gid, deepLinkEntityId);
}

async function loadAll(gid, deepLinkEntityId) {
  document.getElementById('ontoMetrics').innerHTML = '<span class="spinner"></span> 加载中…';
  try {
    const [er, rr, ir] = await Promise.all([
      api(`/groups/${gid}/ontology/entities?limit=100`),
      api(`/groups/${gid}/ontology/relations?limit=100`),
      api(`/groups/${gid}/ontology/issues?limit=100`),
    ]);
    _e = er.entities || []; _r = rr.relations || []; _is = ir.issues || [];

    // Load drafts, packages, quality in background
    try {
      const dr = await api(`/groups/${gid}/ontology/drafts?limit=100`);
      _drafts = dr.drafts || [];
    } catch (_) { _drafts = []; }
    try {
      const pr = await api(`/groups/${gid}/ontology/packages?limit=20`);
      _packages = pr.packages || [];
    } catch (_) { _packages = []; }
    try {
      _quality = await api(`/groups/${gid}/ontology/drafts/quality`);
    } catch (_) { _quality = null; }

    renderMetrics();
    renderFilters(); renderList(); renderIssues(); renderModeling(gid); renderContracts(gid);

    if (deepLinkEntityId && _e.some(x => x.id === deepLinkEntityId)) {
      _activeTab = 'graph'; switchTabUI(gid); selectEnt(deepLinkEntityId);
    } else if (_sel && _e.some(x => x.id === _sel)) {
      selectEnt(_sel);
    } else if (_e.length > 0) {
      selectEnt(_e[0].id);
    } else {
      selectEnt(null);
    }

    // Render overview after all data loaded
    renderOverview();
  } catch (e) {
    document.getElementById('ontoMetrics').innerHTML = `<span class="error">加载失败：${esc(errMsg(e))}</span>`;
  }
}

function switchTabUI(gid) {
  const container = document.getElementById('outlet') || document.body;
  container.querySelectorAll('#ontoTabs .tab').forEach(x => { x.classList.toggle('active', x.dataset.tab === _activeTab); });
  container.querySelectorAll('.ontoTabContent').forEach(d => { d.style.display = 'none'; });
  const target = document.getElementById(`tab-${_activeTab}`);
  if (target) target.style.display = '';
}

function renderMetrics() {
  const u = _r.filter(r => r.status === 'unresolved').length;
  const pTotal = _is.filter(i => (i.triage_status || 'pending') === 'pending').length;
  const proposed = _drafts.filter(d => d.status === 'proposed').length;
  document.getElementById('ontoMetrics').innerHTML = `
    <div class="metric"><strong>${_e.length}</strong> 实体</div>
    <div class="metric"><strong>${_r.length}</strong> 关系</div>
    <div class="metric"><strong>${u}</strong> 未解析</div>
    <div class="metric"><strong>${_is.length}</strong> 问题</div>
    <div class="metric"><strong>${_drafts.length}</strong> 草稿</div>
    <div class="metric"><strong>${_packages.length}</strong> 包</div>
    ${_quality ? `<div class="metric"><strong style="color:${_quality.status==='PASS'?'var(--ok)':_quality.status==='FAIL'?'var(--danger)':'var(--warn)'}">${QUALITY_L[_quality.status]||_quality.status}</strong> 质量</div>` : ''}`;
}

/* ── Overview ───────────────────────────────────────────────── */

function renderOverview() {
  const el = document.getElementById('tab-overview');
  if (!el) return;
  const pendingIssues = _is.filter(i => (i.triage_status || 'pending') === 'pending').length;
  const proposed = _drafts.filter(d => d.status === 'proposed').length;
  const accepted = _drafts.filter(d => d.status === 'accepted').length;
  const rejected = _drafts.filter(d => d.status === 'rejected').length;
  const typeCounts = {};
  _e.forEach(e => { const t = e.entity_type || '未知'; typeCounts[t] = (typeCounts[t] || 0) + 1; });

  el.innerHTML = `
    <div class="ontoOverview">
      <div class="panel">
        <div class="panelHeader"><h2>实体分布</h2></div>
        <ul class="overviewList">${Object.entries(typeCounts).map(([t, c]) => `<li><strong>${c}</strong> ${ELABEL[t] || t}</li>`).join('') || '<li class="muted">暂无实体</li>'}</ul>
        <div class="overviewAction"><button class="secondary small" onclick="document.querySelector('#ontoTabs .tab[data-tab=graph]').click()">打开图谱 →</button></div>
      </div>
      <div class="panel">
        <div class="panelHeader"><h2>治理状态</h2></div>
        <div class="overviewStat"><strong>${_is.length}</strong> 总问题</div>
        <div class="overviewStat"><strong>${pendingIssues}</strong> 待处理</div>
        <div class="overviewStat"><strong>${_r.filter(r => r.status === 'unresolved').length}</strong> 未解析关系</div>
        <div class="overviewAction"><button class="secondary small" onclick="document.querySelector('#ontoTabs .tab[data-tab=governance]').click()">查看治理 →</button></div>
      </div>
      <div class="panel">
        <div class="panelHeader"><h2>建模草稿</h2></div>
        <div class="overviewStat"><strong>${proposed}</strong> 待审核</div>
        <div class="overviewStat"><strong>${accepted}</strong> 已接受</div>
        <div class="overviewStat"><strong>${rejected}</strong> 已拒绝</div>
        ${_quality ? `<div class="overviewStat"><strong style="color:${_quality.status==='PASS'?'var(--ok)':_quality.status==='FAIL'?'var(--danger)':'var(--warn)'}">${QUALITY_L[_quality.status]||_quality.status}</strong> 质量</div>` : ''}
        <div class="overviewAction"><button class="secondary small" onclick="document.querySelector('#ontoTabs .tab[data-tab=modeling]').click()">查看草稿 →</button></div>
      </div>
    </div>`;
}

/* ── Graph (entity list + graph + detail) ────────────────────── */

function renderFilters() {
  const ts = [...new Set(_e.map(e => e.entity_type))].sort();
  const ss = [...new Set(_e.map(e => e.status).filter(Boolean))].sort();
  const el = document.getElementById('ontoFilters');
  if (!el) return;
  el.innerHTML = `
    <input id="ontoQ" type="text" placeholder="搜索标题或别名…" class="ontoSearch" />
    <select id="ontoET"><option value="">全部类型</option>${ts.map(t => `<option>${t}</option>`).join('')}</select>
    <select id="ontoSt"><option value="">全部状态</option>${ss.map(s => `<option>${s}</option>`).join('')}</select>`;
  ['ontoQ', 'ontoET', 'ontoSt'].forEach(id => document.getElementById(id)?.addEventListener('input', () => { renderList(); if (_sel) { const e = _e.find(x => x.id === _sel); if (e) renderGraph(e); } }));
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
  if (!el) return;
  if (!f.length) { el.innerHTML = '<p class="muted">无匹配实体。</p>'; return; }
  el.innerHTML = f.map(e => `
    <div class="ontoItem${_sel === e.id ? ' selected' : ''}" data-id="${e.id}">
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
  _sel = id;
  renderList();
  const e = _e.find(x => x.id === id);
  renderGraph(e || null);
  renderDetail(e || null);
}

function renderGraph(sel) {
  const c = document.getElementById('ontoGraph');
  if (!c) return;
  if (!sel) {
    c.innerHTML = `<div class="ontoGraphControls"><label>范围 <select id="graphScope" disabled><option>选中实体</option></select></label><label>关系 <select id="graphStatus" disabled><option>全部</option></select></label></div><div class="ontoGraphInner"><p class="muted">请选择实体以查看关系图谱。${_e.length?'':' 请先上传知识文档并扫描 Ontology。'}</p></div><div class="ontoLegend"><span class="legendItem muted">无实体</span></div>`;
    return;
  }

  const gid = state.currentGroupId;
  const out = _r.filter(r => r.source_entity_id === sel.id);
  const inn = _r.filter(r => r.target_entity_id === sel.id);
  const hopIds = new Set([sel.id]);
  out.forEach(r => r.target_entity_id && hopIds.add(r.target_entity_id));
  inn.forEach(r => hopIds.add(r.source_entity_id));
  const hopNodes = [...hopIds].map(id => _e.find(x => x.id === id)).filter(Boolean);

  let scopeIds = new Set(hopIds);
  if (_graphScope === 'visible') {
    const fq = (document.getElementById('ontoQ')?.value || '').toLowerCase();
    const fet = document.getElementById('ontoET')?.value || '';
    const fst = document.getElementById('ontoSt')?.value || '';
    let vis = _e;
    if (fet) vis = vis.filter(e => e.entity_type === fet);
    if (fst) vis = vis.filter(e => e.status === fst);
    if (fq) vis = vis.filter(e => (e.title + ' ' + (e.aliases || []).join(' ')).toLowerCase().includes(fq));
    const visIds = new Set(vis.map(e => e.id));
    scopeIds = new Set([...hopIds].filter(id => visIds.has(id)));
  } else if (_graphScope === 'all') {
    scopeIds = new Set([...hopIds, ..._e.slice(0, 40).map(e => e.id)]);
  }

  let nodes = [...scopeIds].map(id => _e.find(x => x.id === id)).filter(Boolean);
  if (!nodes.find(n => n.id === sel.id)) nodes.push(sel);
  let edges = _r.filter(r => scopeIds.has(r.source_entity_id) && scopeIds.has(r.target_entity_id));
  if (_graphStatus !== 'all') edges = edges.filter(r => r.status === _graphStatus);
  const unresolvedOut = out.filter(r => r.status === 'unresolved' || !r.target_entity_id);

  let html = `<div class="ontoGraphControls">
    <label>范围 <select id="graphScope"><option value="selected"${_graphScope==='selected'?' selected':''}>选中实体</option><option value="visible"${_graphScope==='visible'?' selected':''}>过滤结果</option><option value="all"${_graphScope==='all'?' selected':''}>全部 (≤40)</option></select></label>
    <label>关系 <select id="graphStatus"><option value="all"${_graphStatus==='all'?' selected':''}>全部</option><option value="resolved"${_graphStatus==='resolved'?' selected':''}>已解析</option><option value="unresolved"${_graphStatus==='unresolved'?' selected':''}>未解析</option></select></label>
  </div>`;

  if (nodes.length <= 1 && edges.length === 0) {
    html += `<div class="ontoGraphInner"><div class="emptyState"><div class="emptyTitle">暂无图谱数据</div><div class="emptyHint">${unresolvedOut.length?'下方列出了 '+unresolvedOut.length+' 个未解析的引用目标。':'选中实体暂无关系。'}</div></div></div>`;
  } else {
    const W = 480, H = 320, cx = W / 2, cy = H / 2, R = Math.min(W, H) * 0.35;
    const nm = {};
    nodes.forEach((n, i) => {
      const a = (i / nodes.length) * 2 * Math.PI - Math.PI / 2;
      nm[n.id] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R };
    });
    let svg = `<svg viewBox="0 0 ${W} ${H}" class="ontoSvg">`;
    edges.forEach(r => {
      const a = nm[r.source_entity_id], b = nm[r.target_entity_id];
      if (!a || !b) return;
      const srcEnt = _e.find(x => x.id === r.source_entity_id);
      const tgtEnt = _e.find(x => x.id === r.target_entity_id);
      const dash = r.status === 'unresolved' ? 'stroke-dasharray:5,4' : '';
      const color = r.status === 'unresolved' ? '#d97706' : '#cbd5e1';
      svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${color}" stroke-width="1.5" ${dash} class="ontoEdge" data-sid="${r.source_entity_id}" data-tid="${r.target_entity_id}"><title>${esc((srcEnt?.title||r.source_entity_id))} → ${esc((tgtEnt?.title||r.target_path||'未解析'))} (${r.status==='resolved'?'已解析':'未解析'})</title></line>`;
    });
    nodes.forEach(n => {
      const p = nm[n.id]; if (!p) return;
      const s = n.id === sel.id;
      svg += `<circle cx="${p.x}" cy="${p.y}" r="${s?18:14}" fill="${ENTITY_COLORS[n.entity_type]||'#888'}" stroke="${s?'#1e293b':'#fff'}" stroke-width="${s?3:2}" class="ontoNode" data-id="${n.id}"><title>${esc(n.title)} (${ELABEL[n.entity_type]||n.entity_type})</title></circle>`;
      svg += `<text x="${p.x}" y="${p.y+28}" text-anchor="middle" font-size="10" fill="${s?'#1e293b':'#64748b'}" font-weight="${s?'600':'400'}">${esc(trunc(n.title,14))}</text>`;
    });
    svg += '</svg>';
    html += `<div class="ontoGraphInner">${svg}<p class="muted" style="margin-top:8px;font-size:12px">${nodes.length} 节点，${edges.length} 连线</p></div>`;
  }

  const types = [...new Set(nodes.map(n => n.entity_type))].sort();
  html += `<div class="ontoLegend">
    <span class="legendItem"><span class="legendLine legendLineSolid"></span> 已解析</span>
    <span class="legendItem"><span class="legendLine legendLineDashed"></span> 未解析</span>
    ${types.map(t => `<span class="legendItem"><span class="legendDot" style="background:${ENTITY_COLORS[t]||'#888'}"></span> ${ELABEL[t]||t}</span>`).join('')}
  </div>`;

  if (_graphScope === 'selected' && unresolvedOut.length) {
    const unique = new Map();
    unresolvedOut.forEach(r => { const k = r.target_path || '?'; if (!unique.has(k)) unique.set(k, r); });
    html += `<div class="ontoUnresolvedList"><div class="ontoUnresolvedTitle">未解析引用 (${unique.size})</div><ul>`;
    unique.forEach((r, path) => { html += `<li><code>${esc(path)}</code>${r.target_label?` (${esc(r.target_label)})`:''}</li>`; });
    html += '</ul></div>';
  }

  c.innerHTML = html;
  c.querySelector('#graphScope')?.addEventListener('change', e => { _graphScope = e.target.value; if (_sel) { const ent = _e.find(x => x.id === _sel); if (ent) renderGraph(ent); } });
  c.querySelector('#graphStatus')?.addEventListener('change', e => { _graphStatus = e.target.value; if (_sel) { const ent = _e.find(x => x.id === _sel); if (ent) renderGraph(ent); } });
  c.querySelectorAll('.ontoNode').forEach(n => n.addEventListener('click', () => selectEnt(n.dataset.id)));
}

function renderDetail(e) {
  const el = document.getElementById('ontoDetail');
  if (!el) return;
  if (!e) { el.innerHTML = '<p class="muted">请选择一个实体。</p>'; return; }

  const out = _r.filter(r => r.source_entity_id === e.id);
  const inn = _r.filter(r => r.target_entity_id === e.id);
  const eis = _is.filter(i => i.entity_id === e.id || i.document_id === e.document_id);
  const edrafts = _drafts.filter(d => d.source_entity_id === e.id);
  const gid = state.currentGroupId;
  const can = state.currentRole === 'owner' || state.currentRole === 'admin';

  el.innerHTML = `
    <div class="ontoDetailCard">
      <h3 style="margin:0 0 12px">${esc(e.title)}</h3>
      <div class="ontoDetailMeta">
        <span class="badge" style="background:${ENTITY_COLORS[e.entity_type]||'#888'};color:#fff">${ELABEL[e.entity_type]||e.entity_type}</span>
        ${e.status ? `<span class="badge badgeInfo">${SLABEL[e.status]||e.status}</span>` : ''}
        ${e.source ? `<span class="badge badgeMuted">${SRC[e.source]||e.source}</span>` : ''}
      </div>
      ${e.aliases?.length ? `<div class="ontoDMeta">别名：${e.aliases.map(a => esc(a)).join('、')}</div>` : ''}
      ${e.tags?.length ? `<div class="ontoDMeta">标签：${e.tags.map(t => `<span class="tag">${esc(t)}</span>`).join(' ')}</div>` : ''}
      <div class="ontoDMeta">路径：<code>${esc(e.source_path)}</code></div>
      <div class="ontoDMeta">文档：${esc(e.document_id)}</div>
      ${out.length ? `<details class="ontoDRels" open><summary>发出关系 (${out.length})</summary><ul>${out.map(r => { const t = _e.find(x => x.id === r.target_entity_id); const badge = r.status==='resolved' ? '<span class="badge badgeOk">已解析</span>' : '<span class="badge badgeMuted">未解析</span>'; const tgt = t ? `<span class="ontoRelTarget" data-eid="${t.id}">${esc(t.title)}</span>` : `<code class="ontoRelPath">${esc(trunc(r.target_path,40))}</code>`; return `<li class="ontoRelItem">→ ${tgt}${r.target_label ? ` (${esc(r.target_label)})` : ''} ${badge}</li>`; }).join('')}</ul></details>` : '<div class="ontoDMeta">无发出关系</div>'}
      ${inn.length ? `<details class="ontoDRels" open><summary>进入关系 (${inn.length})</summary><ul>${inn.map(r => { const s = _e.find(x => x.id === r.source_entity_id); const tgt = s ? `<span class="ontoRelTarget" data-eid="${s.id}">${esc(s.title)}</span>` : `<code>${esc(r.source_entity_id)}</code>`; return `<li class="ontoRelItem">${tgt} → ${esc(r.target_path)}${r.target_label ? ` (${esc(r.target_label)})` : ''}</li>`; }).join('')}</ul></details>` : '<div class="ontoDMeta">无进入关系</div>'}
      ${eis.length ? `<details class="ontoDRels"><summary>相关问题 (${eis.length})</summary><ul>${eis.map(i => `<li><span class="badge ${i.severity==='error'?'badgeErr':'badgeWarn'}">${i.severity}</span> ${ICODE[i.code]||i.code} — ${esc(i.message)}</li>`).join('')}</ul></details>` : '<div class="ontoDMeta">无相关问题</div>'}
      ${edrafts.length ? `<details class="ontoDRels"><summary>关联草稿 (${edrafts.length})</summary><ul>${edrafts.map(d => `<li><span class="badge badgeInfo">${DRAFT_TYPE_LABEL[d.draft_type]||d.draft_type}</span> ${esc(d.name)} <span class="badge badgeMuted">${DRAFT_STATUS[d.status]||d.status}</span></li>`).join('')}</ul></details>` : ''}
    </div>`;
  document.querySelectorAll('.ontoRelTarget').forEach(el2 => {
    el2.addEventListener('click', () => selectEnt(el2.dataset.eid));
  });
}

/* ── Governance ──────────────────────────────────────────────── */

function renderIssues() {
  const filtersEl = document.getElementById('ontoIssueFilters');
  const bodyEl = document.getElementById('ontoIssueBody');
  if (!filtersEl || !bodyEl) return;
  const gid = state.currentGroupId;
  const can = state.currentRole === 'owner' || state.currentRole === 'admin';

  const codes = [...new Set(_is.map(i => i.code))].sort();
  filtersEl.innerHTML = `
    <select id="issueTriageFilter"><option value="all">全部状态</option><option value="pending">待处理</option><option value="confirmed">已确认</option><option value="ignored">已忽略</option></select>
    <select id="issueCodeFilter"><option value="all">全部类型</option>${codes.map(co => `<option value="${co}">${ICODE[co]||co}</option>`).join('')}</select>
  `;

  const triageSel = document.getElementById('issueTriageFilter');
  const codeSel = document.getElementById('issueCodeFilter');
  if (triageSel) triageSel.value = _issueTriageFilter;
  if (codeSel) codeSel.value = _issueCodeFilter;

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
      const label = s === 'error' ? '错误' : '警告';
      html += `<div class="ontoIssueGroup"><strong style="color:${color}">${label} (${by[s].length})</strong><div class="ontoIssueList">`;
      by[s].forEach(i => {
        const ts = i.triage_status || 'pending';
        const tsLabel = TL[ts] || ts;
        const tsStyle = TS[ts] || 'badgeInfo';
        const ignCls = ts === 'ignored' ? ' ontoIssueIgnored' : '';
        const triageBtns = can ? `<span class="ontoTriageBtns">
          <button class="triageBtn triageConfirm" data-iid="${i.id}" title="确认">✓</button>
          <button class="triageBtn triageIgnore" data-iid="${i.id}" title="忽略">✕</button>
          <button class="triageBtn triageReset" data-iid="${i.id}" title="重置">↺</button>
        </span>` : '';
        html += `<div class="ontoIssueItem${ignCls}${i.entity_id?' clickable':''}" data-eid="${i.entity_id||''}">
          <span class="badge ${s==='error'?'badgeErr':'badgeWarn'}">${ICODE[i.code]||i.code}</span>
          <span>${esc(i.message)}</span>
          <span class="badge ${tsStyle}">${tsLabel}</span>
          ${triageBtns}
          <span class="muted" style="font-size:11px">${esc(i.source_path)}</span>
        </div>`;
      });
      html += '</div></div>';
    });
    bodyEl.innerHTML = html || '<p class="muted">无匹配问题。</p>';

    bodyEl.querySelectorAll('.ontoIssueItem.clickable').forEach(el2 => {
      el2.addEventListener('click', () => { _activeTab = 'graph'; switchTabUI(gid); selectEnt(el2.dataset.eid); });
    });
    if (can) {
      bodyEl.querySelectorAll('.triageConfirm').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); doTriage(gid, b.dataset.iid, 'confirmed'); }));
      bodyEl.querySelectorAll('.triageIgnore').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); doTriage(gid, b.dataset.iid, 'ignored'); }));
      bodyEl.querySelectorAll('.triageReset').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); doTriage(gid, b.dataset.iid, 'pending'); }));
    }
  };

  triageSel?.addEventListener('change', () => { _issueTriageFilter = triageSel.value; renderFiltered(); });
  codeSel?.addEventListener('change', () => { _issueCodeFilter = codeSel.value; renderFiltered(); });
  renderFiltered();
}

async function doTriage(gid, iid, status) {
  try {
    await api(`/groups/${gid}/ontology/issues/${iid}/triage`, { method: 'POST', body: JSON.stringify({ triage_status: status }) });
    const r = await api(`/groups/${gid}/ontology/issues?limit=100`);
    _is = r.issues || [];
    renderIssues();
    renderMetrics();
  } catch (e) { showToast('操作失败：' + errMsg(e), 'error'); }
}

/* ── Modeling Drafts ─────────────────────────────────────────── */

function renderModeling(gid) {
  const area = document.getElementById('ontoDraftsArea');
  if (!area) return;
  const can = state.currentRole === 'owner' || state.currentRole === 'admin';
  _batchSelected = new Set();

  let html = '';
  if (can) {
    const hasProposed = _drafts.some(d => d.status === 'proposed');
    html += '<div class="draftToolbar">';
    html += `<button id="genDraftsBtn" class="secondary small">生成草稿</button>`;
    html += `<button id="batchAcceptBtn" class="small" disabled>批量接受</button>`;
    html += `<button id="batchRejectBtn" class="secondary small" disabled>批量拒绝</button>`;
    html += `<div id="batchRejectGroup" style="display:none;margin-top:6px"><input id="reviewNoteBatch" class="draftNote" placeholder="拒绝时必须填写备注…" /><button id="batchRejectConfirmBtn" class="danger small" style="margin-top:4px">确认拒绝</button><button id="batchRejectCancelBtn" class="secondary small" style="margin-top:4px">取消</button></div>`;
    html += `<span id="batchReviewMsg" class="muted" style="font-size:var(--text-xs);margin-left:8px"></span>`;
    html += '</div>';
  }

  if (!_drafts.length) {
    html += '<div class="emptyState"><div class="emptyTitle">暂无建模草稿</div><div class="emptyHint">扫描 Ontology 后生成建模草稿，或从实体详情手动创建。</div></div>';
    area.innerHTML = html;
  } else {
    html += '<div class="ontoDrafts"><div class="draftList" id="draftList"></div><div class="draftDetail" id="draftDetail"><p class="muted">请选择草稿查看详情。</p></div></div>';
    area.innerHTML = html;
    renderDraftList();
  }

  if (can) {
    document.getElementById('genDraftsBtn')?.addEventListener('click', generateDrafts);
    document.getElementById('batchAcceptBtn')?.addEventListener('click', () => reviewBatch(gid, 'accepted'));
    document.getElementById('batchRejectBtn')?.addEventListener('click', () => {
      document.getElementById('batchRejectGroup').style.display = '';
      document.getElementById('reviewNoteBatch').focus();
    });
    document.getElementById('batchRejectCancelBtn')?.addEventListener('click', () => {
      document.getElementById('batchRejectGroup').style.display = 'none';
      document.getElementById('reviewNoteBatch').value = '';
      document.getElementById('batchReviewMsg').textContent = '';
    });
    document.getElementById('batchRejectConfirmBtn')?.addEventListener('click', () => {
      const note = document.getElementById('reviewNoteBatch')?.value.trim();
      if (!note) { document.getElementById('batchReviewMsg').textContent = '拒绝时必须填写审核备注。'; return; }
      reviewBatch(gid, 'rejected', note);
    });
  }
}

function updateBatchButtons() {
  document.getElementById('batchAcceptBtn').disabled = _batchSelected.size === 0;
  document.getElementById('batchRejectBtn').disabled = _batchSelected.size === 0;
}

function renderDraftList() {
  const el = document.getElementById('draftList');
  if (!el) return;
  const can = state.currentRole === 'owner' || state.currentRole === 'admin';

  el.innerHTML = _drafts.map(d => {
    const isProposed = d.status === 'proposed';
    const isSel = _selDraft === d.id;
    const isBatch = _batchSelected.has(d.id);
    const cb = (can && isProposed)
      ? `<input type="checkbox" class="draftCheck" data-id="${d.id}" ${isBatch ? 'checked' : ''} ${!isProposed ? 'disabled' : ''} />`
      : `<span class="draftCheckPlaceholder"></span>`;
    return `
    <div class="draftItem${isSel ? ' draftItem--detail' : ''}${isBatch ? ' draftItem--batch' : ''}" data-id="${d.id}">
      ${cb}
      <div class="draftItemInfo">
        <div class="draftItemTitle">${esc(d.name)}</div>
        <div class="draftItemMeta">
          <span class="badge badgeInfo">${DRAFT_TYPE_LABEL[d.draft_type]||d.draft_type}</span>
          <span class="badge badgeMuted">${DRAFT_STATUS[d.status]||d.status}</span>
        </div>
      </div>
    </div>`;
  }).join('');

  el.querySelectorAll('.draftItem').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.closest('.draftCheck')) return;
      _selDraft = item.dataset.id; renderDraftList(); renderDraftDetail();
    });
  });
  el.querySelectorAll('.draftCheck').forEach(cb => {
    cb.addEventListener('click', (e) => {
      e.stopPropagation();
      if (cb.checked) _batchSelected.add(cb.dataset.id);
      else _batchSelected.delete(cb.dataset.id);
      renderDraftList();
      updateBatchButtons();
    });
  });
}

function renderDraftDetail() {
  const el = document.getElementById('draftDetail');
  if (!el) return;
  const d = _drafts.find(x => x.id === _selDraft);
  if (!d) { el.innerHTML = '<p class="muted">请选择草稿查看详情。</p>'; return; }

  const gid = state.currentGroupId;
  const can = state.currentRole === 'owner' || state.currentRole === 'admin';
  const se = d.source_entity_id ? _e.find(x => x.id === d.source_entity_id) : null;
  const payload = JSON.stringify(d.payload || {}, null, 2);
  const evidence = JSON.stringify(d.evidence_refs || [], null, 2);

  el.innerHTML = `
    <h3 style="margin:0 0 12px">${esc(d.name)}</h3>
    <div class="ontoDetailMeta">
      <span class="badge badgeInfo">${DRAFT_TYPE_LABEL[d.draft_type]||d.draft_type}</span>
      <span class="badge badgeMuted">${DRAFT_STATUS[d.status]||d.status}</span>
    </div>
    ${d.description ? `<p style="margin:8px 0;font-size:var(--text-sm)">${esc(d.description)}</p>` : ''}
    <div class="ontoDMeta">来源实体：${se ? `<span class="ontoRelTarget" data-eid="${se.id}">${esc(se.title)}</span>` : (d.source_entity_id || '—')}</div>
    ${d.source_rag_run_id ? `<div class="ontoDMeta">RAG 运行：<code>${esc(d.source_rag_run_id)}</code></div>` : ''}
    ${d.source_issue_id ? `<div class="ontoDMeta">来源问题：<code>${esc(d.source_issue_id)}</code></div>` : ''}
    <details class="ontoDRels" style="margin-top:8px"><summary>Payload</summary><pre style="background:var(--surface);padding:8px;border-radius:var(--radius-sm);font-size:var(--text-xs);overflow-x:auto;max-height:200px">${esc(payload)}</pre></details>
    <details class="ontoDRels"><summary>证据引用 (${d.evidence_refs?.length||0})</summary><pre style="background:var(--surface);padding:8px;border-radius:var(--radius-sm);font-size:var(--text-xs);overflow-x:auto;max-height:200px">${esc(evidence)}</pre></details>
    ${d.reviewed_by ? `<div class="ontoDMeta">审核人：${esc(d.reviewed_by)}</div>` : ''}
    ${d.reviewed_at ? `<div class="ontoDMeta">审核时间：${new Date(d.reviewed_at).toLocaleString()}</div>` : ''}
    ${d.review_note ? `<div class="ontoDMeta">审核备注：${esc(d.review_note)}</div>` : ''}
    ${can && d.status === 'proposed' ? `
      <div class="actions" style="margin-top:12px">
        <button class="singleAcceptBtn small" data-id="${d.id}">接受</button>
        <button class="singleRejectBtn secondary small" data-id="${d.id}">拒绝</button>
        <input id="singleReviewNote" class="draftNote" placeholder="拒绝时必须填写备注…" style="margin-top:6px" />
        <span id="draftReviewMsg" class="muted" style="font-size:var(--text-xs)"></span>
      </div>` : ''}
  `;

  el.querySelector('.ontoRelTarget')?.addEventListener('click', (e2) => {
    _activeTab = 'graph'; switchTabUI(gid); selectEnt(e2.target.dataset.eid);
  });
  el.querySelector('.singleAcceptBtn')?.addEventListener('click', () => singleReview(gid, d.id, 'accepted'));
  el.querySelector('.singleRejectBtn')?.addEventListener('click', () => {
    const note = document.getElementById('singleReviewNote')?.value.trim();
    if (!note) { document.getElementById('draftReviewMsg').textContent = '拒绝时必须填写审核备注。'; return; }
    singleReview(gid, d.id, 'rejected', note);
  });
}

async function generateDrafts() {
  const gid = state.currentGroupId;
  const btn = document.getElementById('genDraftsBtn');
  btn.disabled = true; btn.textContent = '生成中…';
  try {
    const r = await api(`/groups/${gid}/ontology/drafts/generate`, { method: 'POST' });
    showToast(`生成：${r.generated_count} 新增, ${r.existing_count} 已存在, ${r.skipped_count} 跳过`, 'success');
    const dr = await api(`/groups/${gid}/ontology/drafts?limit=100`);
    _drafts = dr.drafts || [];
    try { _quality = await api(`/groups/${gid}/ontology/drafts/quality`); } catch (_) {}
    _selDraft = null; _batchSelected = new Set();
    renderMetrics(); renderList(); renderModeling(gid); renderOverview();
  } catch (e) { showToast('生成失败：' + errMsg(e), 'error'); }
  finally { btn.disabled = false; btn.textContent = '生成草稿'; }
}

async function singleReview(gid, draftId, status, note) {
  const msg = document.getElementById('draftReviewMsg');
  try {
    await api(`/groups/${gid}/ontology/drafts/${draftId}/review`, { method: 'POST', body: JSON.stringify({ status, review_note: note || null }) });
    const dr = await api(`/groups/${gid}/ontology/drafts?limit=100`);
    _drafts = dr.drafts || [];
    try { _quality = await api(`/groups/${gid}/ontology/drafts/quality`); } catch (_) {}
    _selDraft = null; _batchSelected = new Set();
    renderDraftList(); renderDraftDetail(); renderMetrics(); renderOverview();
    showToast(status === 'accepted' ? '已接受草稿' : '已拒绝草稿', 'success');
  } catch (e) { if (msg) msg.textContent = errMsg(e); }
}

async function reviewBatch(gid, status, note) {
  if (!_batchSelected.size) { showToast('请先勾选待审核的草稿。', 'warn'); return; }
  if (status === 'rejected' && !note) { showToast('拒绝时必须填写审核备注。', 'warn'); return; }

  const selected = [..._batchSelected];
  try {
    const r = await api(`/groups/${gid}/ontology/drafts/review-batch`, { method: 'POST', body: JSON.stringify({ draft_ids: selected, status, review_note: note || null }) });
    const dr = await api(`/groups/${gid}/ontology/drafts?limit=100`);
    _drafts = dr.drafts || [];
    try { _quality = await api(`/groups/${gid}/ontology/drafts/quality`); } catch (_) {}
    _selDraft = null; _batchSelected = new Set();
    document.getElementById('batchRejectGroup').style.display = 'none';
    document.getElementById('reviewNoteBatch').value = '';
    renderDraftList(); renderDraftDetail(); renderMetrics(); renderOverview();
    showToast(`已${status==='accepted'?'接受':status==='rejected'?'拒绝':''} ${r.reviewed_count} 个草稿`, 'success');
  } catch (e) { showToast('批量审核失败：' + errMsg(e), 'error'); }
}

/* ── Contracts (packages) ────────────────────────────────────── */

function renderContracts(gid) {
  const area = document.getElementById('ontoContractsArea');
  if (!area) return;
  const can = state.currentRole === 'owner' || state.currentRole === 'admin';

  let html = '';
  if (can) {
    html += `<div class="actions"><button id="buildPackageBtn">构建模型包</button></div>`;
  }

  if (!_packages.length) {
    html += '<div class="emptyState"><div class="emptyTitle">暂无模型包</div><div class="emptyHint">接受建模草稿后，构建模型包并导出业务契约。</div></div>';
  } else {
    html += '<div class="packageList" id="packageList"></div>';
    html += '<div id="contractDetail" style="margin-top:16px"></div>';
  }
  area.innerHTML = html;

  if (_packages.length) renderPackageList();

  document.getElementById('buildPackageBtn')?.addEventListener('click', buildPackage);
}

function renderPackageList() {
  const el = document.getElementById('packageList');
  if (!el) return;
  el.innerHTML = _packages.map(p => `
    <div class="packageItem${_selPackage === p.id ? ' selected' : ''}" data-id="${p.id}" style="cursor:pointer">
      <div><span class="packageVersion">v${p.version}</span><span class="packageMeta" style="margin-left:8px">${esc(p.content_hash?.substring(0,10)||'')}…</span></div>
      <div><span class="badge ${p.quality_status==='PASS'?'badgeOk':p.quality_status==='FAIL'?'badgeErr':'badgeWarn'}">${QUALITY_L[p.quality_status]||p.quality_status}</span><span class="packageMeta" style="margin-left:8px">${p.draft_count} 草稿</span></div>
      <div class="packageMeta">${new Date(p.created_at).toLocaleString()}</div>
    </div>`).join('');

  el.querySelectorAll('.packageItem').forEach(item => {
    item.addEventListener('click', () => { _selPackage = item.dataset.id; renderPackageList(); renderContract(gid); });
  });
}

async function renderContract(gid) {
  const el = document.getElementById('contractDetail');
  if (!el || !_selPackage) return;
  el.innerHTML = '<div class="loading"><span class="spinner"></span> 加载契约…</div>';

  const pkg = _packages.find(p => p.id === _selPackage);
  if (!pkg) return;
  try {
    const contract = await api(`/groups/${gid}/ontology/packages/${_selPackage}/contract`);
    el.innerHTML = buildContractHTML(contract, pkg);
  } catch (e) {
    el.innerHTML = `<div class="errorCard"><p class="errorTitle">加载契约失败</p><p class="errorDetail">${esc(errMsg(e))}</p></div>`;
  }
}

function buildContractHTML(contract, pkg) {
  const m = contract.manifest || {};
  const p = contract.provenance || {};
  const sections = [
    { title: '对象类型', items: contract.object_types || [], key: 'object_types' },
    { title: '属性', items: contract.properties || [], key: 'properties' },
    { title: '关联类型', items: contract.link_types || [], key: 'link_types' },
    { title: '动作类型', items: contract.action_types || [], key: 'action_types' },
  ];

  let html = `
    <div class="panel" style="margin-bottom:16px">
      <div class="panelHeader"><h2>编译契约 — v${pkg.version}</h2></div>
      <div class="ontoDMeta">Profile：${esc(m.contract_profile||'—')} · Schema：${esc(m.schema_version||'—')}</div>
      <div class="ontoDMeta">语义 Hash：<code>${esc(m.semantic_hash||'—')}</code></div>
      <div class="ontoDMeta">来源包：${esc(p.source_package_id||'')} · 内容 Hash：<code>${esc(p.source_content_hash||'').substring(0,16)}…</code></div>
    </div>`;

  sections.forEach(s => {
    if (!s.items.length) return;
    html += `<div class="contractSection"><h4>${s.title} (${s.items.length})</h4>`;
    html += '<table class="contractTable"><thead><tr>';
    const keys = Object.keys(s.items[0] || {}).filter(k => k !== 'entity_type');
    keys.forEach(k => { html += `<th>${esc(k)}</th>`; });
    html += '</tr></thead><tbody>';
    s.items.forEach(item => {
      html += '<tr>';
      keys.forEach(k => {
        const v = item[k];
        html += `<td>${v != null ? esc(String(v)) : '—'}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
  });

  return html;
}

async function buildPackage() {
  const gid = state.currentGroupId;
  const btn = document.getElementById('buildPackageBtn');
  btn.disabled = true; btn.textContent = '构建中…';
  try {
    const r = await api(`/groups/${gid}/ontology/packages`, { method: 'POST' });
    showToast(r.created ? `包 v${r.version} 已创建` : `包已存在（内容相同）`, 'success');
    const pr = await api(`/groups/${gid}/ontology/packages?limit=20`);
    _packages = pr.packages || [];
    renderContracts(gid); renderMetrics(); renderOverview();
  } catch (e) { showToast('构建失败：' + errMsg(e), 'error'); }
  finally { btn.disabled = false; btn.textContent = '构建模型包'; }
}

/* ── Utils ───────────────────────────────────────────────────── */

function trunc(s, n) { return s && s.length > n ? s.slice(0, n) + '...' : s; }
