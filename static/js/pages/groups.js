import { api } from '../api.js';
import { state, setState } from '../state.js';
import { panel, panelGrid } from '../components/panel.js';
import { statusBadge } from '../components/badge.js';
import { showToast } from '../util/toast.js';

export async function render(container) {
  if (!state.accessToken) { container.innerHTML = '<p>Please sign in first.</p>'; return; }

  container.innerHTML = '<h1 class="pageTitle">Groups</h1><p class="pageMeta">Manage your team workspaces</p><div class="loading"><span class="spinner"></span>Loading groups...</div>';

  try {
    const me = await api('/auth/me');
    setState({ groups: me.groups || [], currentUser: me });
  } catch (_) { /* ignore, use cached */ }

  const groups = state.groups || [];

  const listPanel = panel('Your Groups',
    groups.length === 0
      ? '<div class="emptyState"><div class="emptyIcon">&#x1f465;</div><p class="emptyTitle">No groups yet</p><p class="emptyHint">Create a group or join one via invite code to get started.</p></div>'
      : `<table class="dataTable">
          <thead><tr><th>Name</th><th>Role</th><th>Actions</th></tr></thead>
          <tbody>
            ${groups.map((g) => `
              <tr>
                <td><strong>${esc(g.group_name)}</strong></td>
                <td>${statusBadge(g.role)}</td>
                <td><a href="#/groups/${g.group_id}/documents" class="btnLink">Open</a></td>
              </tr>
            `).join('')}
          </tbody>
        </table>`
  );

  const createPanel = panel('Create Group', `
    <label>Group Name <input id="groupName" type="text" required maxlength="160" /></label>
    <p id="groupError" class="formError" style="display:none"></p>
    <button id="createGroupBtn">Create Group</button>
  `);

  const joinPanel = panel('Join by Invite Code', `
    <label>Invite Code <input id="inviteCode" type="text" required /></label>
    <p id="joinError" class="formError" style="display:none"></p>
    <button id="joinGroupBtn">Join Group</button>
  `);

  container.innerHTML = panelGrid([listPanel, createPanel, joinPanel]);

  document.getElementById('createGroupBtn').addEventListener('click', async () => {
    const errEl = document.getElementById('groupError');
    try {
      await api('/groups', {
        method: 'POST',
        body: JSON.stringify({ name: document.getElementById('groupName').value.trim() }),
      });
      const me = await api('/auth/me');
      setState({ groups: me.groups || [] });
      showToast('Group created', 'success');
      render(container);
    } catch (err) {
      errEl.textContent = err.detail || 'Failed to create group';
      errEl.style.display = 'block';
    }
  });

  document.getElementById('joinGroupBtn').addEventListener('click', async () => {
    const errEl = document.getElementById('joinError');
    try {
      await api('/groups/join-by-invite', {
        method: 'POST',
        body: JSON.stringify({ invite_code: document.getElementById('inviteCode').value.trim() }),
      });
      const me = await api('/auth/me');
      setState({ groups: me.groups || [] });
      render(container);
    } catch (err) {
      errEl.textContent = err.detail || 'Failed to join group';
      errEl.style.display = 'block';
    }
  });
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
