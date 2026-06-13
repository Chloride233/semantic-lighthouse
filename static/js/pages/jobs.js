import { api } from '../api.js';
import { state } from '../state.js';
import { panel } from '../components/panel.js';
import { statusBadge } from '../components/badge.js';

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!gid) { container.innerHTML = '<p>Please select a group first.</p>'; return; }

  container.innerHTML = '<h1 class="pageTitle">Ingestion Jobs</h1><p class="pageMeta">Monitor document processing</p><div class="loading"><span class="spinner"></span>Loading jobs...</div>';

  let docs = [];
  try {
    docs = await api(`/groups/${gid}/documents/search?q=&limit=50`) || [];
  } catch (err) {
    container.innerHTML = `<div class="error">Failed to load: ${esc(err.detail)}</div>`;
    return;
  }

  let allJobs = [];
  for (const doc of docs) {
    try {
      const jobs = await api(`/groups/${gid}/documents/${doc.id}/ingestion-jobs`) || [];
      for (const j of jobs) j._docTitle = doc.title;
      allJobs.push(...jobs);
    } catch (_) { /* skip docs without jobs */ }
  }
  allJobs.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));

  container.innerHTML = panel('Ingestion Jobs', allJobs.length === 0
    ? '<div class="emptyState"><div class="emptyIcon">&#x2699;</div><p class="emptyTitle">No ingestion jobs</p><p class="emptyHint">Jobs appear after document uploads complete processing.</p></div>'
    : `<table class="dataTable">
        <thead><tr><th>Document</th><th>Status</th><th>Step</th><th>Attempt</th><th>Error</th><th>Actions</th></tr></thead>
        <tbody>
          ${allJobs.map((j) => `
            <tr>
              <td>${esc(j._docTitle || j.document_id)}</td>
              <td>${statusBadge(j.status)}</td>
              <td>${esc(j.current_step || '-')}</td>
              <td>${j.attempt_count}/${j.max_attempts}</td>
              <td class="muted">${esc((j.error_message || '').substring(0, 60))}</td>
              <td>${j.status === 'failed' ? `<button class="secondary small retryBtn" data-docid="${j.document_id}">Retry</button>` : '-'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>`
  );

  container.addEventListener('click', async (e) => {
    const btn = e.target.closest('.retryBtn');
    if (!btn) return;
    try {
      await api(`/groups/${gid}/documents/${btn.dataset.docid}/ingestion-jobs`, { method: 'POST' });
      render(container, params);
    } catch (err) { alert(err.detail || 'Retry failed'); }
  });
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;');
}
