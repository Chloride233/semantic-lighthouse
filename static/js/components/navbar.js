import { state, onStateChange, setState, currentGroup } from '../state.js';
import { navigate } from '../router.js';
import { api } from '../api.js';
import { esc } from '../util/esc.js';

const NAV_SECTIONS = [
  { label: '问答', path: '/ask', needsGroup: false },
  { label: '知识库', path: '/groups/{gid}/documents', needsGroup: true },
  { label: '对话', path: '/groups/{gid}/conversations', needsGroup: true },
  { label: '任务', path: '/groups/{gid}/tasks', needsGroup: true },
  { label: 'Agent', path: '/groups/{gid}/agent', needsGroup: true },
  { label: 'Ontology', path: '/groups/{gid}/ontology', needsGroup: true },
  { label: '工作区', path: '/groups', needsGroup: false },
];

export function initNavbar(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;

  function render() {
    const signedIn = !!state.accessToken;
    const groups = state.groups || [];
    const gid = state.currentGroupId;
    const group = currentGroup();

    const hash = location.hash.replace('#', '') || '/';
    const isActive = (path) => {
      if (path === '/ask') return hash === '/ask' || hash === '/';
      if (path === '/groups') return hash === '/groups' || hash.startsWith('/groups?');
      return hash.startsWith(path.replace('{gid}', gid || '___'));
    };

    const groupOptions = groups
      .map((g) => `<option value="${g.group_id}" ${g.group_id === gid ? 'selected' : ''}>${esc(g.group_name)}</option>`)
      .join('');

    const navLinks = NAV_SECTIONS.map((section) => {
      if (!signedIn) return '';
      if (section.needsGroup && !gid) return '';
      const href = section.needsGroup ? `#${section.path.replace('{gid}', gid)}` : `#${section.path}`;
      const active = isActive(section.path) ? ' active' : '';
      return `<a href="${href}" class="${active}">${esc(section.label)}</a>`;
    }).join('');

    el.innerHTML = `
      <div class="navLeft">
        <a class="navBrand" href="#/ask">语义灯塔</a>
        <nav class="navLinks" aria-label="主导航">
          ${navLinks}
        </nav>
      </div>
      <div class="navRight">
        ${signedIn && groups.length ? `
          <div class="navContext">
            <span id="navGroupName">${group ? esc(group.group_name) : '未选择'}</span>
            <span class="badge badgeMuted" id="navGroupRole">${esc(state.currentRole || '-')}</span>
          </div>
          <select class="groupSelect" id="navGroupSelect" aria-label="切换工作区">
            <option value="">切换工作区…</option>
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
        if (!grp) return;
        setState({ currentGroupId: newGid, currentRole: grp.role || '' });
        navigate('/ask');
      });
    }
  }

  onStateChange(render);
  render();
}
