import { api } from '../api.js';
import { state, setState } from '../state.js';
import { panel, panelGrid } from '../components/panel.js';
import { statusBadge } from '../components/badge.js';
import { showToast } from '../util/toast.js';

export async function render(container) {
  if (!state.accessToken) { container.innerHTML = '<p>请先登录。</p>'; return; }

  container.innerHTML = '<h1 class="pageTitle">工作区</h1><p class="pageMeta">管理团队空间、邀请加入和权限边界。</p><div class="loading"><span class="spinner"></span>正在加载工作区...</div>';

  try {
    const me = await api('/auth/me');
    setState({ groups: me.groups || [], currentUser: me });
  } catch (_) { /* ignore, use cached */ }

  const groups = state.groups || [];

  const listPanel = panel('我的工作区',
    groups.length === 0
      ? '<div class="emptyState"><div class="emptyIcon">组</div><p class="emptyTitle">还没有工作区</p><p class="emptyHint">创建一个工作区，或通过邀请码加入已有团队。</p></div>'
      : `<table class="dataTable">
          <thead><tr><th>名称</th><th>角色</th><th>操作</th></tr></thead>
          <tbody>
            ${groups.map((g) => `
              <tr>
                <td><strong>${esc(g.group_name)}</strong></td>
                <td>${statusBadge(g.role)}</td>
                <td><a href="#/groups/${g.group_id}/documents" class="btnLink">打开</a></td>
              </tr>
            `).join('')}
          </tbody>
        </table>`
  );

  const createPanel = panel('创建工作区', `
    <label>工作区名称 <input id="groupName" type="text" required maxlength="160" /></label>
    <p id="groupError" class="formError" style="display:none"></p>
    <button id="createGroupBtn">创建工作区</button>
  `);

  const joinPanel = panel('通过邀请码加入', `
    <label>邀请码 <input id="inviteCode" type="text" required /></label>
    <p id="joinError" class="formError" style="display:none"></p>
    <button id="joinGroupBtn">加入工作区</button>
  `);

  container.innerHTML = `
    <h1 class="pageTitle">工作区</h1>
    <p class="pageMeta">管理团队空间、邀请加入和权限边界。</p>
    ${panelGrid([listPanel, createPanel, joinPanel])}
  `;

  document.getElementById('createGroupBtn').addEventListener('click', async () => {
    const errEl = document.getElementById('groupError');
    try {
      await api('/groups', {
        method: 'POST',
        body: JSON.stringify({ name: document.getElementById('groupName').value.trim() }),
      });
      const me = await api('/auth/me');
      setState({ groups: me.groups || [] });
      showToast('工作区已创建。', 'success');
      render(container);
    } catch (err) {
      errEl.textContent = err.detail || '创建工作区失败';
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
      errEl.textContent = err.detail || '加入工作区失败';
      errEl.style.display = 'block';
    }
  });
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
