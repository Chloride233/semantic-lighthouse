import { api } from '../api.js';
import { state } from '../state.js';
import { panel } from '../components/panel.js';
import { statusBadge } from '../components/badge.js';

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!gid) { container.innerHTML = '<p>请先选择工作区。</p>'; return; }

  container.innerHTML = '<h1 class="pageTitle">ETL 任务</h1><p class="pageMeta">查看文档解析、清洗、切片和向量化处理状态。</p><div class="loading"><span class="spinner"></span>正在加载任务...</div>';

  let docs = [];
  try {
    docs = await api(`/groups/${gid}/documents`) || [];
  } catch (err) {
    container.innerHTML = `<div class="error">加载失败：${esc(err.detail)}</div>`;
    return;
  }

  const allJobs = [];
  for (const doc of docs) {
    try {
      const jobs = await api(`/groups/${gid}/documents/${doc.id}/ingestion-jobs`) || [];
      for (const job of jobs) job._docTitle = doc.title;
      allJobs.push(...jobs);
    } catch (_) { /* skip docs without jobs */ }
  }
  allJobs.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));

  const jobsPanel = panel('处理任务', allJobs.length === 0
    ? '<div class="emptyState"><div class="emptyIcon">流</div><p class="emptyTitle">暂无 ETL 任务</p><p class="emptyHint">文档上传并触发处理后，任务状态会显示在这里。</p></div>'
    : `<table class="dataTable">
        <thead><tr><th>文档</th><th>状态</th><th>当前步骤</th><th>重试次数</th><th>错误</th><th>操作</th></tr></thead>
        <tbody>
          ${allJobs.map((job) => `
            <tr>
              <td>${esc(job._docTitle || job.document_id)}</td>
              <td>${statusBadge(job.status)}</td>
              <td>${esc(job.current_step || '-')}</td>
              <td>${job.attempt_count}/${job.max_attempts}</td>
              <td class="muted">${esc((job.error_message || '').substring(0, 60))}</td>
              <td>${job.status === 'failed' ? `<button class="secondary small retryBtn" data-docid="${job.document_id}">重试</button>` : '-'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>`
  );

  container.innerHTML = `
    <h1 class="pageTitle">ETL 任务</h1>
    <p class="pageMeta">查看文档解析、清洗、切片和向量化处理状态。</p>
    ${jobsPanel}
  `;

  container.addEventListener('click', async (e) => {
    const btn = e.target.closest('.retryBtn');
    if (!btn) return;
    try {
      await api(`/groups/${gid}/documents/${btn.dataset.docid}/ingestion-jobs`, { method: 'POST' });
      render(container, params);
    } catch (err) { alert(err.detail || '重试失败'); }
  });
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;');
}
