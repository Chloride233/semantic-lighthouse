/** Pilot project detail — /groups/:gid/projects/:pid */
import { api } from '../api.js';
import { state } from '../state.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

const STAGE_LABELS = {
  goal: '目标', data: '数据', model: '模型', validate: '验证', pilot: 'Pilot',
};
const STAGE_ORDER = ['goal', 'data', 'model', 'validate', 'pilot'];

function fiveStageRail(current) {
  const idx = STAGE_ORDER.indexOf(current);
  return `<div class="stageRail stageRailLg">
    ${STAGE_ORDER.map((s, i) => {
      let cls = 'stageStep';
      if (i < idx) cls += ' done';
      else if (i === idx) cls += ' current';
      return `
        <div class="${cls}">
          <span class="stageDot"></span>
          <span class="stageLabel">${STAGE_LABELS[s]}</span>
        </div>`;
    }).join('<span class="stageConnector"></span>')}
  </div>`;
}

function fmtDate(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch (_) { return iso.slice(0, 16); }
}

function colTypeClass(type) {
  const map = { integer: 'num', number: 'num', boolean: 'bool', date: 'dt', datetime: 'dt' };
  return map[type] || 'txt';
}

export async function render(container, params) {
  const { gid, pid } = params;
  if (!gid || !pid) return;
  const isOwnerAdmin = state.currentRole === 'owner' || state.currentRole === 'admin';

  async function loadProject() {
    return api(`/groups/${gid}/projects/${pid}`);
  }

  async function loadDatasets() {
    return api(`/groups/${gid}/projects/${pid}/datasets?limit=50`);
  }

  async function renderFull() {
    container.innerHTML = '<div class="loading"><span class="spinner"></span>加载 Pilot 详情...</div>';

    let project, datasets;
    try {
      [project, datasets] = await Promise.all([loadProject(), loadDatasets()]);
    } catch (err) {
      container.innerHTML = `<div class="error"><p>${esc(err.humanMessage || err.message)}</p></div>`;
      return;
    }

    const stage = project.stage;
    const dsList = datasets.datasets || [];

    container.innerHTML = `
      <div class="projectDetail">
        <div class="projectHeader">
          <a href="#/groups/${gid}/projects" class="backLink">← 返回 Pilot 列表</a>
          <h1 class="projectTitle">${esc(project.name)}</h1>
          <div class="projectSubtitle">
            <span class="badge">${esc(project.status === 'active' ? '进行中' : '已归档')}</span>
            <span class="badge badgeMuted">${esc(project.entry_mode === 'data_first' ? '数据驱动' : '问题驱动')}</span>
            ${project.industry_template ? `<span class="badge badgeMuted">${esc(project.industry_template)}</span>` : ''}
          </div>
        </div>

        ${fiveStageRail(stage)}

        <div class="projectBody">
          <div class="projectMain" id="projectMain"></div>
          <aside class="projectAside">
            <div class="contextCard">
              <h3 class="contextTitle">业务目标</h3>
              <p>${esc(project.business_goal || '（未填写）')}</p>
            </div>
            <div class="contextCard">
              <h3 class="contextTitle">信息</h3>
              <dl class="contextDL">
                <dt>进入方式</dt><dd>${esc(project.entry_mode === 'data_first' ? '数据驱动' : '问题驱动')}</dd>
                <dt>行业模板</dt><dd>${esc(project.industry_template || '—')}</dd>
                <dt>更新时间</dt><dd>${fmtDate(project.updated_at)}</dd>
              </dl>
            </div>
          </aside>
        </div>
      </div>
    `;

    const main = document.getElementById('projectMain');
    renderStageContent(main, stage, project, dsList);
  }

  function renderStageContent(main, stage, project, dsList) {
    switch (stage) {
      case 'goal': return renderGoalStage(main, dsList);
      case 'data': return renderDataStage(main, dsList);
      default: return renderFutureStage(main, stage);
    }
  }

  // ── Goal stage ────────────────────────────────────────────────────────

  function renderGoalStage(main, dsList) {
    const hasDatasets = dsList.filter(d => d.status === 'ready').length > 0;
    main.innerHTML = `
      <div class="stagePanel">
        <div class="stagePanelHead">
          <h2>目标 — 定义业务问题</h2>
          <span class="badge badgeOk">已完成</span>
        </div>
        <p>项目已创建，业务目标已记录。下一步是为 Pilot 项目上传业务数据集。</p>
        ${isOwnerAdmin ? `
          <div class="stageCTAs">
            <p class="stageHint">${hasDatasets ? '已有就绪数据集。数据阶段已自动推进。' : '上传 CSV 或 XLSX 数据集开始数据阶段。'}</p>
            ${!hasDatasets ? '<button class="primary" id="uploadFirstBtn">上传数据集</button>' : ''}
          </div>
        ` : '<p class="muted">需要 owner 或 admin 角色才能上传数据。</p>'}
      </div>
      ${dsList.length > 0 ? datasetListHTML(dsList) : ''}
    `;
    if (isOwnerAdmin && !hasDatasets) {
      document.getElementById('uploadFirstBtn')?.addEventListener('click', () => openUploadDialog());
    }
  }

  // ── Data stage ─────────────────────────────────────────────────────────

  function renderDataStage(main, dsList) {
    main.innerHTML = `
      <div class="stagePanel">
        <div class="stagePanelHead">
          <h2>数据 — 数据集已就绪</h2>
          <span class="badge badgeOk">已完成</span>
        </div>
        <p>数据集已上传并完成分析。后端已识别字段类型、主键候选和外键建议。</p>
        ${isOwnerAdmin ? `
          <div class="stageCTAs">
            <button class="primary" id="uploadMoreBtn">上传更多数据</button>
            <p class="stageHint">下一步：生成模型草案 — 数据准备就绪后即可开始建模</p>
          </div>
        ` : ''}
      </div>
      ${datasetListHTML(dsList)}
    `;
    if (isOwnerAdmin) {
      document.getElementById('uploadMoreBtn')?.addEventListener('click', () => openUploadDialog());
    }
  }

  // ── Future stages (model/validate/pilot) ───────────────────────────────

  function renderFutureStage(main, stage) {
    main.innerHTML = `
      <div class="stagePanel">
        <div class="stagePanelHead">
          <h2>${STAGE_LABELS[stage]} — 阶段进行中</h2>
        </div>
        <p>当前项目处于 <strong>${STAGE_LABELS[stage]}</strong> 阶段。后续操作将在模型工作区中提供。</p>
      </div>
    `;
  }

  // ── Dataset list ───────────────────────────────────────────────────────

  function datasetListHTML(dsList) {
    if (!dsList.length) return '';
    return `
      <div class="datasetSection">
        <h3>数据集 (${dsList.length})</h3>
        <div class="datasetList">
          ${dsList.map(ds => `
            <div class="datasetItem" id="ds-${ds.id}">
              <div class="datasetItemHead">
                <span class="datasetName">${esc(ds.original_name)}</span>
                <span class="badge ${ds.status === 'ready' ? 'badgeOk' : ds.status === 'failed' ? 'badgeDanger' : 'badgeMuted'}">${esc(ds.status)}</span>
                <span class="muted">${esc(ds.file_format.toUpperCase())}</span>
                <span class="muted" style="margin-left:auto">${fmtDate(ds.created_at)}</span>
              </div>
              <div class="datasetItemMeta">
                <span>${ds.row_count || 0} 行 · ${ds.column_count || 0} 列</span>
                <button class="linkBtn" id="dsToggle-${ds.id}">查看字段▼</button>
              </div>
              <div class="datasetProfile" id="dsProfile-${ds.id}" hidden>
                ${profileHTML(ds)}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  function profileHTML(ds) {
    const profile = ds.profile_json || {};
    const columns = profile.columns || [];
    const pks = profile.primary_key_candidates || [];
    const fks = profile.foreign_key_suggestions || [];
    const pkCols = new Set(pks.map(p => p.column));

    let html = '<table class="profileTable"><thead><tr><th>字段</th><th>类型</th><th>可空</th><th>非空</th><th>去重</th><th>PK</th></tr></thead><tbody>';
    for (const col of columns) {
      const isPK = pkCols.has(col.name);
      html += `<tr>
        <td><strong>${esc(col.name)}</strong>${isPK ? ' <span class="pkTag">PK</span>' : ''}</td>
        <td><span class="typeTag ${colTypeClass(col.inferred_type)}">${esc(col.inferred_type)}</span></td>
        <td>${col.nullable ? '✓' : '✗'}</td>
        <td>${col.non_null_count ?? '-'}</td>
        <td>${col.distinct_count ?? '-'}${col.distinct_count_capped ? '*' : ''}</td>
        <td>${isPK ? esc(pks.find(p => p.column === col.name)?.confidence || '') : ''}</td>
      </tr>`;
    }
    html += '</tbody></table>';

    if (fks.length) {
      html += '<div class="profileFKs"><h4>外键建议</h4><ul>';
      for (const fk of fks) {
        html += `<li>${esc(fk.source_column)} → ${esc(fk.target_dataset_name || fk.target_dataset_id)}.${esc(fk.target_column)} <span class="muted">(${esc(fk.confidence)})</span></li>`;
      }
      html += '</ul></div>';
    }

    return html;
  }

  // ── Upload dialog ──────────────────────────────────────────────────────

  function openUploadDialog() {
    const overlay = document.createElement('div');
    overlay.className = 'dialogOverlay';
    overlay.innerHTML = `
      <div class="dialog" role="dialog" aria-label="上传数据集">
        <h2 class="dialogTitle">上传数据集</h2>
        <div class="dialogBody">
          <p class="muted">支持 CSV 和 XLSX 格式。文件大小上限 50 MiB。</p>
          <label class="field">
            <span>选择文件</span>
            <input id="upFile" type="file" accept=".csv,.xlsx" required />
          </label>
          <label class="fieldCheck">
            <input id="upSamples" type="checkbox" />
            <span>包含样本值（最多 3 个/列，自动脱敏）</span>
          </label>
          <div id="upProgress" style="display:none" class="uploadProgress">
            <div class="progressBar"><div class="progressFill" id="upProgressFill"></div></div>
            <p class="muted" id="upProgressText">上传中...</p>
          </div>
        </div>
        <p class="formError" id="upError" style="display:none"></p>
        <div class="dialogActions">
          <button class="secondary" id="upCancel">取消</button>
          <button class="primary" id="upSubmit">上传并分析</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const close = () => overlay.remove();
    document.getElementById('upCancel').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function escClose(e) {
      if (e.key === 'Escape') { close(); document.removeEventListener('keydown', escClose); }
    });

    document.getElementById('upSubmit').addEventListener('click', async () => {
      const fileInput = document.getElementById('upFile');
      const file = fileInput.files[0];
      const errEl = document.getElementById('upError');
      const submitBtn = document.getElementById('upSubmit');
      const progressDiv = document.getElementById('upProgress');
      const progressText = document.getElementById('upProgressText');

      if (!file) { errEl.textContent = '请选择文件'; errEl.style.display = 'block'; return; }

      const formData = new FormData();
      formData.append('file', file);
      formData.append('include_sample_values', document.getElementById('upSamples').checked ? 'true' : 'false');

      submitBtn.disabled = true;
      progressDiv.style.display = 'block';
      progressText.textContent = '上传中...';
      errEl.style.display = 'none';

      try {
        await api(`/groups/${gid}/projects/${pid}/datasets`, {
          method: 'POST',
          body: formData,
        });
        close();
        showToast('数据集已上传并完成分析', 'success');
        await renderFull();
      } catch (err) {
        errEl.textContent = err.humanMessage || err.message;
        errEl.style.display = 'block';
        progressDiv.style.display = 'none';
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  // ── Profile expand/collapse listeners ──────────────────────────────────
  container.addEventListener('click', (e) => {
    const btn = e.target.closest('[id^="dsToggle-"]');
    if (!btn) return;
    const dsId = btn.id.replace('dsToggle-', '');
    const profile = document.getElementById('dsProfile-' + dsId);
    if (profile) {
      profile.hidden = !profile.hidden;
      btn.textContent = profile.hidden ? '查看字段▼' : '收起▲';
    }
  });

  await renderFull();
}
