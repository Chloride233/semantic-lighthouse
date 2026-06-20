import { state, onStateChange, setState, currentGroup } from '../state.js';
import { navigate } from '../router.js';
import { api } from '../api.js';
import { esc } from '../util/esc.js';

const PRIMARY = [
  { label: 'Pilot', path: '/groups/{gid}/projects', needsGroup: true },
  { label: 'Ontology', path: '/groups/{gid}/ontology', needsGroup: true },
  { label: '工作区', path: '/groups', needsGroup: false },
];

const TOOLS = [
  { label: '问答', path: '/ask', needsGroup: false },
  { label: '知识库', path: '/groups/{gid}/documents', needsGroup: true },
  { label: '对话', path: '/groups/{gid}/conversations', needsGroup: true },
  { label: '任务', path: '/groups/{gid}/tasks', needsGroup: true },
  { label: 'Agent', path: '/groups/{gid}/agent', needsGroup: true },
];

let _docListenersSetup = false;

function _closeMenu() {
  const btn = document.getElementById('navMoreBtn');
  const menu = document.getElementById('navMoreMenu');
  if (menu) menu.hidden = true;
  if (btn) btn.setAttribute('aria-expanded', 'false');
}

function _setupDocListeners() {
  if (_docListenersSetup) return;
  _docListenersSetup = true;
  document.addEventListener('click', (e) => {
    const btn = document.getElementById('navMoreBtn');
    const menu = document.getElementById('navMoreMenu');
    if (!btn || !menu) return;
    if (btn.contains(e.target)) {
      e.stopPropagation();
      const open = menu.hidden;
      menu.hidden = !open;
      btn.setAttribute('aria-expanded', String(open));
      if (open) {
        const first = menu.querySelector('a');
        if (first) first.focus();
      }
      return;
    }
    if (!menu.contains(e.target)) {
      _closeMenu();
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') _closeMenu();
  });
}

export function initNavbar(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  _setupDocListeners();

  function render() {
    const signedIn = !!state.accessToken;
    const groups = state.groups || [];
    const gid = state.currentGroupId;
    const group = currentGroup();

    const hash = location.hash.replace('#', '') || '/';
    const isActive = (path) => {
      if (path === '/groups') return hash === '/groups' || hash.startsWith('/groups?');
      if (!gid) return false;
      return hash.startsWith(path.replace('{gid}', gid));
    };

    const groupOptions = groups
      .map((g) => `<option value="${g.group_id}" ${g.group_id === gid ? 'selected' : ''}>${esc(g.group_name)}</option>`)
      .join('');

    const makeLink = (section) => {
      if (!signedIn) return '';
      if (section.needsGroup && !gid) return '';
      const href = section.needsGroup
        ? `#${section.path.replace('{gid}', gid)}`
        : `#${section.path}`;
      const active = isActive(section.path) ? ' active' : '';
      return `<a href="${href}" class="${active}">${esc(section.label)}</a>`;
    };

    const primaryLinks = PRIMARY.map(makeLink).filter(Boolean).join('');
    const toolsLinks = TOOLS.map(makeLink).filter(Boolean).join('');

    el.innerHTML = `
      <div class="navLeft">
        <a class="navBrand" href="${gid ? '#/groups/' + gid + '/projects' : '#/groups'}">语义灯塔</a>
        <nav class="navLinks" aria-label="主导航">
          ${primaryLinks}
          ${toolsLinks ? `
          <div class="navMore">
            <button class="navMoreBtn" id="navMoreBtn" aria-expanded="false" aria-haspopup="true">更多工具 ▾</button>
            <div class="navMoreMenu" id="navMoreMenu" role="menu" hidden>
              ${toolsLinks.replace(/<a /g, '<a role="menuitem" ')}
            </div>
          </div>` : ''}
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
        navigate(`/groups/${newGid}/projects`);
      });
    }
  }

  onStateChange(render);
  render();
}
