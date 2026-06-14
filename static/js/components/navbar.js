import { state, onStateChange, setState } from '../state.js';
import { navigate } from '../router.js';
import { api } from '../api.js';
import { esc } from '../util/esc.js';

export function initNavbar(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;

  function render() {
    const signedIn = !!state.accessToken;
    const groups = state.groups || [];
    const gid = state.currentGroupId;

    const groupOptions = groups
      .map((g) => `<option value="${g.group_id}" ${g.group_id === gid ? 'selected' : ''}>${esc(g.group_name)}</option>`)
      .join('');

    const hash = location.hash.replace('#', '');
    const isActive = (path) => hash.startsWith(path) ? ' active' : '';

    el.innerHTML = `
      <div class="navLeft">
        <a class="navBrand" href="#/ask">语义灯塔</a>
        <nav class="navLinks">
          ${signedIn ? `<a href="#/ask" class="${isActive('/ask')}">问答</a>` : ''}
          ${signedIn && gid ? `
            <a href="#/groups/${gid}/documents" class="${isActive(`/groups/${gid}/documents`)}">知识库</a>
            <a href="#/groups/${gid}/conversations" class="${isActive(`/groups/${gid}/conversations`)}">对话</a>
          ` : ''}
          ${signedIn ? `<a href="#/groups" class="${isActive('/groups') && !gid ? 'active' : ''}">工作区</a>` : ''}
        </nav>
      </div>
      <div class="navRight">
        ${signedIn && groups.length ? `
          <select class="groupSelect" id="navGroupSelect">
            <option value="">切换工作区...</option>
            ${groupOptions}
          </select>
        ` : ''}
        <span class="navStatus ${signedIn ? 'signedIn' : ''}">
          ${signedIn ? esc(state.currentUser?.email || '') : '未登录'}
        </span>
        ${signedIn ? '<button class="secondary small" id="navLogoutBtn">退出</button>' : ''}
      </div>
    `;

    if (signedIn) {
      document.getElementById('navLogoutBtn')?.addEventListener('click', async () => {
        try { await api('/auth/logout', { method: 'POST' }); } catch (_) {}
        setState({ accessToken: '', currentUser: null, groups: [], currentGroupId: '', currentRole: '' });
        navigate('/login');
      });
      document.getElementById('navGroupSelect')?.addEventListener('change', (e) => {
        const newGid = e.target.value;
        const grp = groups.find((g) => g.group_id === newGid);
        setState({ currentGroupId: newGid, currentRole: grp?.role || '' });
        if (newGid) {
          navigate('/ask');
        }
      });
    }
  }

  onStateChange(render);
  render();
}
