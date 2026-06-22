import { api } from '../api.js';
import { state } from '../state.js';
import { panel } from '../components/panel.js';
import { statusBadge, ontologyStatusBadge, sourceBadge } from '../components/badge.js';
import { esc } from '../util/esc.js';

const STATUS_FILTERS = [
  { key: '', label: '全部' },
  { key: 'ready', label: '可检索' },
  { key: 'processing', label: '处理中' },
  { key: 'failed', label: '失败' },
  { key: 'archived', label: '已归档' },
];
const ENTITY_COLORS = {
  Concept: 'var(--brand)', Vendor: 'var(--accent)', Methodology: 'var(--info)',
  Case: 'var(--ok)', FAQ: 'var(--warn)',
};

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!gid) { container.innerHTML = '<p>请先选择工作区。</p>'; return; }

  const hash = location.hash.replace('#', '');
  const urlParams = new URLSearchParams(hash.split('?')[1] || '');
  const activeFilter = urlParams.get('status') || '';

  container.innerHTML = '<div class="legacyPage"><h1 class="pageTitle">知识库</h1><p class="pageMeta">上传、导入和管理当前工作区的知识文档。</p><div class="loading"><span class="spinner"></span>正在加载文档...</div>';

  let docs = [];
  try {
    const qs = activeFilter ? `?status=${activeFilter}` : '';
    docs = await api(`/groups/${gid}/documents${qs}`) || [];
  } catch (err) {
    container.innerHTML = `<div class="legacyPage"><h1 class="pageTitle">知识库</h1><div class="errorCard"><p class="errorTitle">加载失败</p><p class="errorDetail">${esc(err.detail)}</p><button onclick="location.reload()">重试</button></div></div>`;
    return;
  }

  const role = state.currentRole;
  const canManage = role === 'owner' || role === 'admin';

  const uploadForm = canManage ? panel('导入知识', `
    <label>文档文件 <input type="file" id="docFileInput" accept=".md,.txt,.pdf,.docx" multiple /></label>
    <div class="actions">
      <button id="uploadDocBtn">上传选中文件</button>
      <button id="importLocalBtn" class="secondary">导入本地知识库</button>
    </div>
    <p id="uploadMsg" class="muted" style="margin-top:8px"></p>
    <div id="uploadQueue" class="uploadQueue"></div>
  `) : '';

  const filterBar = `
    <div class="legacyFilters docFilters">
      ${STATUS_FILTERS.map(f => `
        <button class="taskFilter ${activeFilter === f.key ? 'active' : ''}" data-status="${f.key}">${f.label}</button>
      `).join('')}
    </div>`;

  const docTable = docs.length === 0
    ? '<div class="emptyState"><div class="emptyIcon">文</div><p class="emptyTitle">还没有文档</p><p class="emptyHint">上传 Markdown、TXT、PDF 或 DOCX 文档，或者直接导入本地知识库。</p></div>'
    : `<table class="dataTable legacyTable">
        <thead><tr><th>标题</th><th>类型</th><th>来源</th><th>成熟度</th><th>状态</th>${canManage ? '<th>操作</th>' : ''}</tr></thead>
        <tbody>
          ${docs.map((d) => {
            const fm = d.frontmatter || {};
            const eType = fm.entityType || '未分类';
            const eColor = ENTITY_COLORS[eType] || '#999';
            const fmStatus = fm.status || '';
            const source = fm.source || '';
            const tags = fm.tags || [];
            const industry = fm.industry || '';
            const scenario = fm.scenario || '';
            return `
            <tr class="docRow" data-doc-id="${d.id}">
              <td>
                <span class="docEntity" style="color:${eColor}">●</span>
                <strong>${esc(d.title)}</strong>
                ${eType !== '未分类' ? `<span class="docEntityLabel">${esc(eType)}</span>` : ''}
                <br><span class="muted">${esc(d.file_name || d.source_path || '')}</span>
              </td>
              <td>${eType !== '未分类' ? `<span class="docTag">${esc(eType)}</span>` : '<span class="muted">-</span>'}</td>
              <td>${source ? sourceBadge(source) : '<span class="muted">-</span>'}</td>
              <td>${fmStatus ? ontologyStatusBadge(fmStatus) : '<span class="muted">未知</span>'}</td>
              <td>${statusBadge(d.status)}${d.ingestion_error ? `<br><span class="muted">${esc(d.ingestion_error.substring(0, 80))}</span>` : ''}</td>
              ${canManage ? `<td>
                ${d.status === 'ready' || d.status === 'failed' ? `<button class="secondary small archiveBtn" data-id="${d.id}">归档</button>` : ''}
                ${d.status === 'archived' ? `<button class="secondary small unarchiveBtn" data-id="${d.id}">恢复</button>` : ''}
              </td>` : ''}
            </tr>
            <tr class="docMetaRow" id="meta-${d.id}" style="display:none">
              <td colspan="${canManage ? 6 : 5}">
                <div class="docMetaPanel">
                  <div class="docMetaGrid">
                    <span class="docMetaLabel">实体类型</span><span class="docMetaValue">${esc(eType)}</span>
                    <span class="docMetaLabel">内容成熟度</span><span class="docMetaValue">${fmStatus ? ontologyStatusBadge(fmStatus) : '<span class="muted">未知</span>'}</span>
                    <span class="docMetaLabel">来源等级</span><span class="docMetaValue">${source ? sourceBadge(source) : '<span class="muted">未知</span>'}</span>
                    ${industry ? `<span class="docMetaLabel">行业</span><span class="docMetaValue">${esc(industry)}</span>` : ''}
                    ${scenario ? `<span class="docMetaLabel">场景</span><span class="docMetaValue">${esc(scenario)}</span>` : ''}
                    ${tags.length ? `<span class="docMetaLabel">标签</span><span class="docMetaValue">${tags.map(t => `<span class="docTag">${esc(t)}</span>`).join(' ')}</span>` : ''}
                    ${d.archived_at ? `<span class="docMetaLabel">归档时间</span><span class="docMetaValue">${new Date(d.archived_at).toLocaleString()}</span>` : ''}
                    ${d.archive_reason ? `<span class="docMetaLabel">归档原因</span><span class="docMetaValue">${esc(d.archive_reason)}</span>` : ''}
                  </div>
                </div>
              </td>
            </tr>
          `}).join('')}
        </tbody>
      </table>`;

  container.innerHTML = `
    <div class="legacyPage">
      <h1 class="pageTitle">知识库</h1>
      <p class="pageMeta">上传、导入和管理当前工作区的知识文档。</p>
      ${uploadForm}${filterBar}${docTable}
    </div>
  `;

  container.querySelectorAll('.docFilters .taskFilter').forEach(btn => {
    btn.addEventListener('click', () => {
      const s = btn.dataset.status;
      location.hash = s ? `#/groups/${gid}/documents?status=${s}` : `#/groups/${gid}/documents`;
    });
  });

  container.querySelectorAll('.docRow').forEach(row => {
    row.addEventListener('click', () => {
      const docId = row.dataset.docId;
      const metaRow = document.getElementById(`meta-${docId}`);
      if (metaRow) metaRow.style.display = metaRow.style.display === 'table-row' ? 'none' : 'table-row';
    });
  });

  bindUploadActions(container, gid, params);
}

function bindUploadActions(container, gid, params) {
  document.getElementById('uploadDocBtn')?.addEventListener('click', async () => {
    const fileInput = document.getElementById('docFileInput');
    const msgEl = document.getElementById('uploadMsg');
    const queueEl = document.getElementById('uploadQueue');
    const uploadBtn = document.getElementById('uploadDocBtn');
    const importBtn = document.getElementById('importLocalBtn');
    const selectedFiles = Array.from(fileInput.files || []);
    const skippedFiles = selectedFiles.filter(shouldSkipUploadFile);
    const files = selectedFiles.filter((file) => !shouldSkipUploadFile(file));
    if (files.length === 0) {
      msgEl.textContent = selectedFiles.length === 0 ? '请至少选择一个文件。' : '选中的都是索引或模板文件，已跳过。';
      renderUploadQueue(queueEl, [], skippedFiles);
      return;
    }
    uploadBtn.disabled = true; importBtn.disabled = true;
    const results = files.map((file) => ({ file, status: 'pending', message: '' }));
    renderUploadQueue(queueEl, results, skippedFiles);
    let uploadedCount = 0;
    for (let i = 0; i < results.length; i += 1) {
      const item = results[i]; item.status = 'uploading';
      msgEl.textContent = `正在上传 ${i + 1}/${results.length}...`;
      renderUploadQueue(queueEl, results, skippedFiles);
      try {
        const formData = new FormData(); formData.append('file', item.file);
        const headers = state.accessToken ? { Authorization: `Bearer ${state.accessToken}` } : {};
        const res = await fetch(`/groups/${gid}/documents/upload`, { method: 'POST', headers, body: formData, credentials: 'include' });
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail || '上传失败'); }
        item.status = 'done'; item.message = '已上传'; uploadedCount += 1;
      } catch (err) { item.status = 'failed'; item.message = err.message; }
      renderUploadQueue(queueEl, results, skippedFiles);
    }
    const failedCount = results.length - uploadedCount;
    msgEl.textContent = failedCount === 0 ? `已上传 ${uploadedCount} 个文件，正在刷新...` : `已上传 ${uploadedCount}/${results.length}，失败 ${failedCount} 个。`;
    uploadBtn.disabled = false; importBtn.disabled = false;
    if (uploadedCount > 0) setTimeout(() => render(container, params), 500);
  });

  document.getElementById('importLocalBtn')?.addEventListener('click', async () => {
    const msgEl = document.getElementById('uploadMsg');
    const uploadBtn = document.getElementById('uploadDocBtn');
    const importBtn = document.getElementById('importLocalBtn');
    uploadBtn.disabled = true; importBtn.disabled = true;
    msgEl.textContent = '正在导入本地知识库...';
    try {
      const res = await api(`/groups/${gid}/documents/import-local`, { method: 'POST' });
      msgEl.textContent = `已导入 ${res.imported_count} 个，跳过 ${res.skipped_count} 个，正在刷新...`;
      setTimeout(() => render(container, params), 500);
    } catch (err) {
      msgEl.textContent = `错误：${err.detail || err.message}`;
      uploadBtn.disabled = false; importBtn.disabled = false;
    }
  });

  container.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    e.stopPropagation();
    const docId = btn.dataset.id;
    if (btn.classList.contains('archiveBtn')) {
      try { await api(`/groups/${gid}/documents/${docId}/archive`, { method: 'POST' }); render(container, params); }
      catch (err) { alert(err.detail || '归档失败'); }
    }
    if (btn.classList.contains('unarchiveBtn')) {
      try { await api(`/groups/${gid}/documents/${docId}/unarchive`, { method: 'POST' }); render(container, params); }
      catch (err) { alert(err.detail || '恢复失败'); }
    }
  });
}

function shouldSkipUploadFile(file) {
  const name = (file.name || '').toLowerCase();
  return name === 'index.md' || name === 'auto_index.md' || name === 'schema.md' || name === '_template.md';
}

function renderUploadQueue(queueEl, results, skippedFiles = []) {
  if (!queueEl) return;
  const labels = { pending: '等待上传', uploading: '上传中', done: '已上传', failed: '失败' };
  const rows = results.map((item) => `
    <li class="uploadQueueItem uploadQueueItem--${esc(item.status)}">
      <span>${esc(item.file.name)}</span><strong>${esc(item.message || labels[item.status] || item.status)}</strong>
    </li>`);
  const skipped = skippedFiles.map((file) => `
    <li class="uploadQueueItem uploadQueueItem--skipped">
      <span>${esc(file.name)}</span><strong>已跳过</strong>
    </li>`);
  queueEl.innerHTML = rows.length || skipped.length ? `<ul>${rows.join('')}${skipped.join('')}</ul>` : '';
}
