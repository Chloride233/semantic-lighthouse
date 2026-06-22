/** Pilot project list — /groups/:gid/projects */
import { api, APIError } from '../api.js';
import { state } from '../state.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

const STAGE_LABELS = {
  goal: '目标', data: '数据', model: '模型', validate: '验证', pilot: 'Pilot',
};

const STAGE_ORDER = ['goal', 'data', 'model', 'validate', 'pilot'];

function stageRail(stage) {
  const idx = STAGE_ORDER.indexOf(stage);
  return `<div class="stageRail stageRailSm">
    ${STAGE_ORDER.map((s, i) => {
      let cls = 'stageDot';
      if (i < idx) cls += ' done';
      else if (i === idx) cls += ' current';
      return `<span class="${cls}" title="${STAGE_LABELS[s]}">${STAGE_LABELS[s]}</span>`;
    }).join('')}
  </div>`;
}

function fmtDate(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }); } catch (_) { return iso.slice(0, 10); }
}

export async function render(container, params) {
  const gid = params.gid;
  if (!gid) return;

  const isOwnerAdmin = state.currentRole === 'owner' || state.currentRole === 'admin';

  container.innerHTML = `
    <div class="pageHead">
      <h1 class="pageTitle">Pilot</h1>
      <p class="pageMeta">业务 Pilot 项目 — 从目标到运行时。</p>
    </div>
    <div class="loading"><span class="spinner"></span>加载中...</div>
  `;

  let projects = [];
  try {
    const data = await api(`/groups/${gid}/projects?limit=50`);
    projects = data.projects || [];
  } catch (err) {
    container.innerHTML = `<div class="error"><p>${esc(err.humanMessage || err.message)}</p></div>`;
    return;
  }

  const activeProjects = projects.filter(p => p.status === 'active');
  const archivedProjects = projects.filter(p => p.status === 'archived');

  const projectCard = (p) => `
    <a href="#/groups/${gid}/projects/${p.id}" class="projectCard">
      <div class="projectCardHead">
        <span class="projectName">${esc(p.name)}</span>
        <span class="badge ${p.status === 'archived' ? 'badgeMuted' : ''}">${esc(p.status === 'active' ? '进行中' : '已归档')}</span>
      </div>
      <p class="projectGoal">${esc((p.business_goal || '').slice(0, 120))}${(p.business_goal || '').length > 120 ? '…' : ''}</p>
      ${stageRail(p.stage)}
      <div class="projectMeta">
        <span>${esc(p.entry_mode === 'data_first' ? '数据驱动' : '问题驱动')}</span>
        ${p.industry_template ? `<span>${esc(p.industry_template)}</span>` : ''}
        <span class="muted">${fmtDate(p.updated_at)}</span>
      </div>
    </a>
  `;

  const emptyHTML = `
    <div class="emptyState">
      <div class="emptyIcon"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></div>
      <p class="emptyTitle">从一个业务 Pilot 开始</p>
      <p class="emptyHint">上传你的业务数据集（CSV / XLSX），生成 Ontology 草案，经过审核后进入可查询的语义运行时。Pilot 是进入 Ontology 语义操作层的最小产品起点。</p>
      ${isOwnerAdmin ? '<button class="primary" id="createFirstBtn">创建第一个 Pilot</button>' : '<p class="muted" style="margin-top:12px">需要 owner 或 admin 角色才能创建项目。</p>'}
      <div class="emptyFooter">
        <p class="muted" style="font-size:var(--text-xs)">本地演示可先运行 <code>scripts/generate_manufacturing_dataset.py --preset tiny</code> 生成示例数据。</p>
      </div>
    </div>
  `;

  const listHTML = `
    <div class="projectListHead">
      <span class="count">${activeProjects.length} 个进行中</span>
      ${isOwnerAdmin ? '<button class="primary small" id="createProjectBtn">新建 Pilot</button>' : ''}
    </div>
    <div class="projectGrid">${activeProjects.map(projectCard).join('')}</div>
    ${archivedProjects.length ? `
      <details class="archivedSection">
        <summary>已归档 (${archivedProjects.length})</summary>
        <div class="projectGrid">${archivedProjects.map(projectCard).join('')}</div>
      </details>
    ` : ''}
  `;

  container.innerHTML = `
    <div class="pageHead">
      <h1 class="pageTitle">Pilot</h1>
      <p class="pageMeta">业务 Pilot 项目 — 从目标到运行时。</p>
    </div>
    ${activeProjects.length === 0 && archivedProjects.length === 0 ? emptyHTML : listHTML}
  `;

  // Dialog for new project
  function openCreateDialog() {
    const overlay = document.createElement('div');
    overlay.className = 'dialogOverlay';
    overlay.innerHTML = `
      <div class="dialog" role="dialog" aria-label="新建 Pilot 项目">
        <h2 class="dialogTitle">新建 Pilot 项目</h2>
        <div class="dialogBody">
          <label class="field">
            <span>项目名称</span>
            <input id="npName" type="text" maxlength="160" required />
          </label>
          <label class="field">
            <span>业务目标</span>
            <textarea id="npGoal" rows="3" maxlength="2000" placeholder="例如：降低设备非计划停机，识别高风险工单，并生成可审计的 Ontology 建模与查询链路。"></textarea>
          </label>
          <fieldset class="segmented">
            <legend>进入方式</legend>
            <label class="segOption"><input type="radio" name="npMode" value="problem_first" checked /> 从业务问题开始</label>
            <label class="segOption"><input type="radio" name="npMode" value="data_first" /> 从现有数据开始</label>
          </fieldset>
          <label class="field">
            <span>行业模板 <em class="muted">（可选）</em></span>
            <input id="npTemplate" type="text" maxlength="80" placeholder="如：制造业、零售、金融" />
          </label>
        </div>
        <p class="formError" id="npError" style="display:none"></p>
        <div class="dialogActions">
          <button class="secondary" id="npCancel">取消</button>
          <button class="primary" id="npSubmit">创建</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const close = () => overlay.remove();

    document.getElementById('npCancel').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function escClose(e) {
      if (e.key === 'Escape') { close(); document.removeEventListener('keydown', escClose); }
    });

    document.getElementById('npSubmit').addEventListener('click', async () => {
      const name = document.getElementById('npName').value.trim();
      const goal = document.getElementById('npGoal').value.trim();
      const mode = document.querySelector('input[name="npMode"]:checked')?.value || 'problem_first';
      const tmpl = document.getElementById('npTemplate').value.trim() || undefined;
      const errEl = document.getElementById('npError');

      if (!name) { errEl.textContent = '项目名称不能为空'; errEl.style.display = 'block'; return; }

      try {
        const project = await api(`/groups/${gid}/projects`, {
          method: 'POST',
          body: JSON.stringify({ name, business_goal: goal, entry_mode: mode, industry_template: tmpl }),
        });
        close();
        showToast('项目已创建', 'success');
        const { navigate } = await import('../router.js');
        navigate(`/groups/${gid}/projects/${project.id}`);
      } catch (err) {
        errEl.textContent = err.humanMessage || err.message;
        errEl.style.display = 'block';
      }
    });
  }

  if (isOwnerAdmin) {
    document.getElementById('createFirstBtn')?.addEventListener('click', openCreateDialog);
    document.getElementById('createProjectBtn')?.addEventListener('click', openCreateDialog);
  }
}
