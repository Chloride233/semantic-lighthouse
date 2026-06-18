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
const SLABEL = { stub: '存根', draft: '草稿', reviewed: '已审校', canonical: '权威' };
const SRC = { 'official-doc': '官方', 'market-research': '调研', 'public-article': '公开', 'case-report': '案例', 'personal-analysis': '个人' };
const ICODE = { unresolved_wikilink: '未解析引用', duplicate_title: '重复标题', duplicate_alias: '重复别名', stale_eval_gold_doc_id: '过期评估引用', type_conflict: '类型冲突', missing_entity_type: '缺少实体类型', invalid_entity_type: '无效实体类型', invalid_document_type: '无效文档类型', missing_required_field: '缺少必填字段', invalid_controlled_value: '无效受控词', invalid_list_field: '列表格式错误' };

let _e = [], _r = [], _is = [], _sel = null;

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!state.accessToken) { container.innerHTML = '<p class="muted">请先登录。</p>'; return; }
  if (!gid) { container.innerHTML = '<p class="muted">请先选择工作区。</p>'; return; }

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

  await init(gid);
}

async function init(gid) {
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
  await load(gid);
}

async function load(gid) {
  document.getElementById('ontoMetrics').innerHTML = '<span class="spinner"></span> 加载中...';
  try {
    const [er, rr, ir] = await Promise.all([
      api(`/groups/${gid}/ontology/entities?limit=100`), api(`/groups/${gid}/ontology/relations?limit=100`), api(`/groups/${gid}/ontology/issues?limit=100`)]);
    _e = er.entities || []; _r = rr.relations || []; _is = ir.issues || [];
    renderMetrics(); renderFilters(); renderList(); renderIssues();
    if (_sel && _e.some(x => x.id === _sel)) selectEnt(_sel); else _sel = null;
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
  const out = _r.filter(r => r.source_entity_id === sel.id);
  const inn = _r.filter(r => r.target_entity_id === sel.id);
  const ids = new Set([sel.id]); out.forEach(r => r.target_entity_id && ids.add(r.target_entity_id)); inn.forEach(r => ids.add(r.source_entity_id));
  const nodes = [...ids].map(id => _e.find(x => x.id === id)).filter(Boolean);
  if (nodes.length <= 1) { c.innerHTML = '<div class="ontoGraphInner"><p class="muted">暂无关系数据。</p></div>'; return; }
  const W = 480, H = 300, cx = W / 2, cy = H / 2, R = Math.min(W, H) * 0.33;
  const nm = {}; nodes.forEach((n, i) => { const a = (i / nodes.length) * 2 * Math.PI - Math.PI / 2; nm[n.id] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R }; });
  const edges = _r.filter(r => nm[r.source_entity_id] && nm[r.target_entity_id]);
  let svg = `<svg viewBox="0 0 ${W} ${H}" class="ontoSvg">`;
  edges.forEach(r => { const a = nm[r.source_entity_id], b = nm[r.target_entity_id]; const d = r.status === 'unresolved' ? 'stroke-dasharray:4,3' : ''; svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#cbd5e1" stroke-width="1.5" ${d} />`; });
  nodes.forEach(n => { const p = nm[n.id]; const s = n.id === sel.id; svg += `<circle cx="${p.x}" cy="${p.y}" r="${s ? 18 : 14}" fill="${ENTITY_COLORS[n.entity_type]||'#888'}" stroke="${s ? '#1e293b' : '#fff'}" stroke-width="${s ? 3 : 2}" class="ontoNode" data-id="${n.id}" /><text x="${p.x}" y="${p.y + 28}" text-anchor="middle" font-size="10" fill="#64748b">${esc(trunc(n.title, 14))}</text>`; });
  svg += '</svg>';
  c.innerHTML = `<div class="ontoGraphInner">${svg}<p class="muted" style="margin-top:8px;font-size:12px">${nodes.length} 节点，${edges.length} 连线。点击节点查看详情。</p></div>`;
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
      ${out.length ? `<details class="ontoDRels"><summary>发出关系 (${out.length})</summary><ul>${out.map(r => { const t = _e.find(x => x.id === r.target_entity_id); return `<li>→ ${esc(r.target_path)}${r.target_label ? ` (${esc(r.target_label)})` : ''} <span class="badge ${r.status==='resolved'?'badgeOk':'badgeMuted'}">${r.status==='resolved'?'已解析':'未解析'}</span>${t ? ` → ${esc(t.title)}` : ''}</li>`; }).join('')}</ul></details>` : '<div class="ontoDMeta">无发出关系</div>'}
      ${inn.length ? `<details class="ontoDRels"><summary>进入关系 (${inn.length})</summary><ul>${inn.map(r => { const s = _e.find(x => x.id === r.source_entity_id); return `<li>${s ? esc(s.title) : r.source_entity_id} → ${esc(r.target_path)}${r.target_label ? ` (${esc(r.target_label)})` : ''}</li>`; }).join('')}</ul></details>` : '<div class="ontoDMeta">无进入关系</div>'}
      ${eis.length ? `<details class="ontoDRels"><summary>相关问题 (${eis.length})</summary><ul>${eis.map(i => `<li><span class="badge ${i.severity==='error'?'badgeErr':'badgeWarn'}">${i.severity}</span> ${ICODE[i.code]||i.code} — ${esc(i.message)}</li>`).join('')}</ul></details>` : '<div class="ontoDMeta">无相关问题</div>'}
    </div>`;
}

function renderIssues() {
  const c = document.getElementById('ontoIssues'); if (!_is.length) { c.innerHTML = ''; return; }
  const by = {}; _is.forEach(i => { (by[i.severity] || (by[i.severity] = [])).push(i); });
  c.innerHTML = `<div class="panel"><div class="panelHeader">治理问题 (${_is.length})</div><div class="panelBody">${['error', 'warning'].map(s => by[s]?.length ? `<div class="ontoIssueGroup"><strong style="color:${s==='error'?'var(--danger)':'var(--warn)'}">${s==='error'?'❌ 错误' : '⚠ 警告'} (${by[s].length})</strong><div class="ontoIssueList">${by[s].slice(0,30).map(i => `<div class="ontoIssueItem ${i.entity_id ? 'clickable' : ''}" data-eid="${i.entity_id || ''}"><span class="badge ${i.severity==='error'?'badgeErr':'badgeWarn'}">${ICODE[i.code]||i.code}</span><span>${esc(i.message)}</span><span class="muted" style="font-size:11px">${esc(i.source_path)}</span></div>`).join('')}</div></div>` : '').join('')}</div></div>`;
  c.querySelectorAll('.ontoIssueItem.clickable').forEach(el => el.addEventListener('click', () => selectEnt(el.dataset.eid)));
}

function trunc(s, n) { return s && s.length > n ? s.slice(0, n) + '...' : s; }
