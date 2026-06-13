import { api } from '../api.js';
import { state } from '../state.js';
import { panel } from '../components/panel.js';
import { statusBadge } from '../components/badge.js';

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!gid) { container.innerHTML = '<p>Please select a group first.</p>'; return; }

  container.innerHTML = '<h1 class="pageTitle">Documents</h1><p class="pageMeta">Upload, search, and manage knowledge base</p><div class="loading"><span class="spinner"></span>Loading documents...</div>';

  let docs = [];
  try {
    const res = await api(`/groups/${gid}/documents/search?q=a&limit=50`);
    docs = res || [];
  } catch (err) {
    container.innerHTML = `<h1 class="pageTitle">Documents</h1><div class="errorCard"><p class="errorTitle">Failed to load</p><p class="errorDetail">${esc(err.detail)}</p><button onclick="location.reload()">Retry</button></div>`;
    return;
  }

  const role = state.currentRole;
  const canManage = role === 'owner' || role === 'admin';

  const uploadForm = panel('Upload Markdown', `
    <label>File <input type="file" id="docFileInput" accept=".md,.txt" /></label>
    <button id="uploadDocBtn">Upload</button>
    <p id="uploadMsg" class="muted" style="margin-top:8px"></p>
  `);

  const docList = panel('Documents', docs.length === 0
    ? '<div class="emptyState"><div class="emptyIcon">&#x1f4c4;</div><p class="emptyTitle">No documents</p><p class="emptyHint">Upload a Markdown file to populate the knowledge base.</p></div>'
    : `<table class="dataTable">
        <thead><tr><th>Title</th><th>Status</th><th>Size</th>${canManage ? '<th>Actions</th>' : ''}</tr></thead>
        <tbody>
          ${docs.map((d) => `
            <tr>
              <td><strong>${esc(d.title)}</strong><br><span class="muted">${esc(d.file_name)}</span></td>
              <td>${statusBadge(d.status)}${d.ingestion_error ? `<br><span class="muted">${esc(d.ingestion_error.substring(0, 80))}</span>` : ''}</td>
              <td>${d.file_size ? Math.round(d.file_size / 1024) + ' KB' : '-'}</td>
              ${canManage ? `<td>
                ${d.status === 'ready' ? `<button class="secondary small archiveBtn" data-id="${d.id}">Archive</button>` : ''}
                ${d.status === 'archived' ? `<button class="secondary small unarchiveBtn" data-id="${d.id}">Unarchive</button>` : ''}
              </td>` : ''}
            </tr>
          `).join('')}
        </tbody>
      </table>`
  );

  container.innerHTML = `${uploadForm}${docList}`;

  document.getElementById('uploadDocBtn').addEventListener('click', async () => {
    const fileInput = document.getElementById('docFileInput');
    const msgEl = document.getElementById('uploadMsg');
    const file = fileInput.files?.[0];
    if (!file) { msgEl.textContent = 'Please select a file.'; return; }
    msgEl.textContent = 'Uploading...';
    try {
      const formData = new FormData();
      formData.append('file', file);
      const headers = state.accessToken ? { Authorization: `Bearer ${state.accessToken}` } : {};
      const res = await fetch(`/groups/${gid}/documents/upload`, { method: 'POST', headers, body: formData, credentials: 'include' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }
      msgEl.textContent = 'Uploaded! Refreshing...';
      setTimeout(() => render(container, params), 500);
    } catch (err) {
      msgEl.textContent = `Error: ${err.message}`;
    }
  });

  container.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const docId = btn.dataset.id;
    if (btn.classList.contains('archiveBtn')) {
      try {
        await api(`/groups/${gid}/documents/${docId}/archive`, { method: 'POST' });
        render(container, params);
      } catch (err) { alert(err.detail || 'Archive failed'); }
    }
    if (btn.classList.contains('unarchiveBtn')) {
      try {
        await api(`/groups/${gid}/documents/${docId}/unarchive`, { method: 'POST' });
        render(container, params);
      } catch (err) { alert(err.detail || 'Unarchive failed'); }
    }
  });
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
