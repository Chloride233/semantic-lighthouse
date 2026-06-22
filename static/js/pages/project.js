/** Pilot project detail — /groups/:gid/projects/:pid */
import { api } from '../api.js';
import { state } from '../state.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';
import { answerCard } from '../components/answer-card.js';

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

  async function loadSummary() {
    return api(`/groups/${gid}/projects/${pid}/summary`);
  }

  async function renderFull() {
    container.innerHTML = '<div class="loading"><span class="spinner"></span>加载 Pilot 详情...</div>';

    let project, datasets, summary;
    try {
      [project, datasets, summary] = await Promise.all([loadProject(), loadDatasets(), loadSummary()]);
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

        ${summaryStripHTML(summary)}

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
    renderStageContent(main, stage, project, dsList, summary);
  }

  function renderStageContent(main, stage, project, dsList, summary) {
    const reloadProject = () => {
      container.innerHTML = ''; renderFull();
    };
    switch (stage) {
      case 'goal': return renderGoalStage(main, dsList, summary, project);
      case 'data': return renderDataStage(main, dsList);
      case 'model': return import('./project-model.js').then(m => m.renderModelStage(container, gid, pid, project, reloadProject, isOwnerAdmin)).catch(e => { main.innerHTML = `<div class="error"><p>加载模型模块失败: ${esc(e.message)}</p></div>`; });
      case 'validate': return import('./project-validate.js').then(m => m.renderValidateStage(container, gid, pid, project, reloadProject, isOwnerAdmin)).catch(e => { main.innerHTML = `<div class="error"><p>加载验证模块失败: ${esc(e.message)}</p></div>`; });
      case 'pilot': return import('./project-pilot.js').then(m => m.renderPilotStage(container, gid, pid, project, reloadProject, isOwnerAdmin)).catch(e => { main.innerHTML = `<div class="error"><p>加载 Pilot 模块失败: ${esc(e.message)}</p></div>`; });
      default: return renderFutureStage(main, stage);
    }
  }

  // ── Goal stage ────────────────────────────────────────────────────────

  function renderGoalStage(main, dsList, summary, project) {
    const hasDatasets = dsList.filter(d => d.status === 'ready').length > 0;
    const evidenceCount = summary?.evidence_count ?? 0;
    const recentEvidence = summary?.recent_evidence ?? [];
    const canPropose = isOwnerAdmin && project.status !== 'archived';
    container._canPropose = canPropose;
    container._evidenceSelection.clear();
    container._recentEvidence = recentEvidence;

    main.innerHTML = `
      <div class="stagePanel">
        <div class="stagePanelHead">
          <h2>目标 — 定义业务问题</h2>
          <span class="badge badgeOk">已完成</span>
          <p class="stageGuide">确认这个 Pilot 要解决的业务问题。上传证据文档，通过项目内问答探索背景，为后续建模提供上下文。</p>
        </div>
        <p>项目已创建，业务目标已记录。下一步是为 Pilot 项目上传业务数据集。</p>

        ${renderEvidenceInGoal(recentEvidence, evidenceCount, canPropose)}

        ${renderAskPanel(evidenceCount)}

        ${isOwnerAdmin ? `
          <div class="stageCTAs">
            <p class="stageHint">${hasDatasets ? '已有就绪数据集。数据阶段已自动推进。' : '先上传一到多张业务 CSV/XLSX。推荐从工单、设备、产品、维护记录等核心表开始。'}</p>
            ${!hasDatasets ? '<button class="primary" id="uploadFirstBtn">上传数据集</button>' : ''}
            ${!hasDatasets ? '<button class="secondary" id="loadDemoBtn">载入制造业示例数据</button>' : ''}
          </div>
        ` : '<p class="muted">需要 owner 或 admin 角色才能上传数据。</p>'}
        <div class="stageSupport">
          <p class="muted" style="font-size:var(--text-xs);margin:0 0 6px">准备阶段补充业务背景（尚未关联当前项目）：</p>
          <a id="goalKnowledgeLink" href="#/groups/${gid}/documents" class="supportLink">查看知识库</a>
          <a id="goalAskLink" href="#/ask" class="supportLink">知识问答</a>
        </div>
      </div>
      ${dsList.length > 0 ? datasetListHTML(dsList) : ''}
    `;
    if (isOwnerAdmin && !hasDatasets) {
      document.getElementById('uploadFirstBtn')?.addEventListener('click', () => openUploadDialog());
      document.getElementById('loadDemoBtn')?.addEventListener('click', importDemoData);
    }
    if (canPropose) {
      bindEvidenceSelection();
      document.getElementById('proposeDraftBtn')?.addEventListener('click', openProposeDraftDialog);
    }
    bindGoalAsk(project);
  }

  // ── Goal evidence summary ───────────────────────────────────────────

  const EVIDENCE_TYPE_LABELS = {
    document: '文档',
    rag_run: 'RAG 问答',
  };
  const EVIDENCE_ROLE_LABELS = {
    context: '背景',
    requirement: '需求',
    decision: '决策',
    validation: '验证',
  };

  function evidenceDisplayTitle(ev) {
    const prov = ev?.provenance || {};
    if (ev?.evidence_type === 'rag_run') return prov.question || 'RAG 问答';
    return prov.evidence_title || prov.file_name || '未命名';
  }

  function evidenceMetaText(ev) {
    const prov = ev?.provenance || {};
    if (ev?.evidence_type === 'rag_run') {
      const parts = [];
      if (prov.confidence) parts.push(`可信度 ${prov.confidence}`);
      if (Number.isFinite(prov.citation_count)) parts.push(`${prov.citation_count} 条引用`);
      if (prov.retrieval_method) parts.push(prov.retrieval_method);
      return parts.join(' · ');
    }
    return prov.source_label || prov.file_name || '';
  }

  function renderEvidenceInGoal(recentEvidence, evidenceCount, canPropose = false) {
    if (!recentEvidence.length) {
      return `
        <div class="goalEvidenceSummary noEvidenceHint" id="goalEvidenceSummary">
          <span>该项目尚未关联任何证据文档。请先在知识库上传文档并添加为项目证据。</span>
          <a href="#/groups/${gid}/documents" class="supportLink" style="margin-left:8px">前往知识库</a>
        </div>`;
    }
    const shown = recentEvidence.slice(0, 5);
    const items = shown.map(ev => {
      const prov = ev?.provenance || {};
      const typeLabel = EVIDENCE_TYPE_LABELS[ev.evidence_type] || ev.evidence_type || '证据';
      const roleLabel = EVIDENCE_ROLE_LABELS[ev.role] || ev.role || '未分类';
      const unavailable = prov.unavailable || prov.evidence_status === 'gone';
      const meta = evidenceMetaText(ev);
      return `
      <li class="goalEvidenceItem${canPropose && ev.id && !unavailable ? ' goalEvidenceItemSelectable' : ''}">
        ${canPropose && ev.id ? `
          <label class="goalEvidenceCheck">
            <input type="checkbox" class="goalEvidenceCheckbox" value="${esc(ev.id)}" data-evidence-link-id="${esc(ev.id)}" ${unavailable ? 'disabled' : ''} />
            <span class="checkboxMark"></span>
          </label>
        ` : ''}
        <div class="goalEvidenceMain">
          <span class="goalEvidenceTitle">${esc(evidenceDisplayTitle(ev))}</span>
          ${meta ? `<span class="goalEvidenceMeta">${esc(meta)}</span>` : ''}
        </div>
        <div class="goalEvidenceBadges">
          <span class="badge badgeMuted">${esc(typeLabel)}</span>
          <span class="badge badgeMuted">${esc(roleLabel)}</span>
          ${unavailable ? '<span class="badge badgeDanger">不可用</span>' : ''}
          ${ev.created_at ? `<span class="muted goalEvidenceTime">${fmtDate(ev.created_at)}</span>` : ''}
        </div>
      </li>`;
    }).join('');
    const hiddenCount = Math.max((evidenceCount || 0) - shown.length, 0);
    const toolbarHTML = canPropose ? `
      <div class="goalEvidenceToolbar" id="goalEvidenceToolbar">
        <span class="muted" style="font-size:var(--text-xs)" id="goalEvidenceSelectCount">已选 0 条</span>
        <button class="primary small" id="proposeDraftBtn" disabled>提出建模草案</button>
      </div>
    ` : '';
    return `
      <div class="goalEvidenceSummary" id="goalEvidenceSummary">
        <h4 class="goalEvidenceSummaryTitle">项目证据（${evidenceCount}）</h4>
        <ul class="goalEvidenceList">${items}</ul>
        ${hiddenCount > 0 ? `<p class="muted" style="font-size:var(--text-xs);margin:4px 0 0">还有 ${hiddenCount} 条证据...</p>` : ''}
        ${toolbarHTML}
        <a href="#/groups/${gid}/documents" class="supportLink" style="margin-top:6px">管理证据</a>
      </div>`;
  }

  function refreshEvidenceSummary(summary) {
    const stripEl = document.getElementById('projectSummaryStrip');
    if (stripEl) stripEl.outerHTML = summaryStripHTML(summary);
    const evidenceEl = document.getElementById('goalEvidenceSummary');
    if (evidenceEl) {
      const canPropose = container._canPropose ?? false;
      evidenceEl.outerHTML = renderEvidenceInGoal(
        summary?.recent_evidence || [],
        summary?.evidence_count ?? 0,
        canPropose,
      );
      bindEvidenceSelection();
    }
  }

  // ── Evidence selection for draft proposal ────────────────────────────

  container._evidenceSelection = new Set();

  function bindEvidenceSelection() {
    const checkboxes = document.querySelectorAll('.goalEvidenceCheckbox');
    const btn = document.getElementById('proposeDraftBtn');
    const countEl = document.getElementById('goalEvidenceSelectCount');

    checkboxes.forEach(cb => {
      cb.addEventListener('change', () => {
        const linkId = cb.getAttribute('data-evidence-link-id');
        if (cb.checked) {
          container._evidenceSelection.add(linkId);
        } else {
          container._evidenceSelection.delete(linkId);
        }
        const count = container._evidenceSelection.size;
        if (countEl) countEl.textContent = `已选 ${count} 条`;
        if (btn) btn.disabled = count === 0;
      });
    });
  }

  // ── Proposal dialog ──────────────────────────────────────────────────

  function openProposeDraftDialog() {
    const selectedIds = [...container._evidenceSelection];
    if (!selectedIds.length) return;

    const overlay = document.createElement('div');
    overlay.className = 'dialogOverlay';
    overlay.id = 'proposeDraftOverlay';
    overlay.innerHTML = `
      <div class="dialog" role="dialog" aria-label="提出建模草案">
        <h2 class="dialogTitle">提出建模草案</h2>
        <div class="dialogBody">
          <p class="muted">基于 ${selectedIds.length} 条已选证据创建建模草案。草案将进入提案状态，需人工审核，不会自动发布。</p>
          <label class="field">
            <span>草案类型 <span style="color:var(--danger)">*</span></span>
            <select id="proposeDraftType">
              <option value="object_type">Object Type（对象类型）</option>
              <option value="property">Property（属性）</option>
              <option value="link_type">Link Type（链接类型）</option>
              <option value="action_type">Action Type（操作类型）</option>
            </select>
          </label>
          <label class="field">
            <span>名称 <span style="color:var(--danger)">*</span></span>
            <input id="proposeDraftName" type="text" maxlength="240" placeholder="例：Manufacturing Work Order" autocomplete="off" />
          </label>
          <label class="field">
            <span>描述</span>
            <textarea id="proposeDraftDesc" rows="3" maxlength="2000" placeholder="基于证据说明为何提出此草案..."></textarea>
          </label>
          <div class="proposeEvidenceSummary">
            <h4>已选证据</h4>
            <ul>
              ${selectedIds.map(lid => {
                const cache = container._recentEvidence || [];
                const ev = cache.find(e => e.id === lid);
                if (!ev) return `<li class="muted">证据 ${esc(lid.slice(0, 8))}...</li>`;
                return `<li>${esc(evidenceDisplayTitle(ev))} <span class="badge badgeMuted">${esc(EVIDENCE_TYPE_LABELS[ev.evidence_type] || ev.evidence_type)}</span></li>`;
              }).join('')}
            </ul>
          </div>
        </div>
        <p class="formError" id="proposeDraftError" style="display:none;padding:0 20px"></p>
        <div class="dialogActions">
          <button class="secondary" id="proposeDraftCancel">取消</button>
          <button class="primary" id="proposeDraftSubmit">提交草案</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const close = () => {
      overlay.remove();
      document.removeEventListener('keydown', escClose);
    };

    document.getElementById('proposeDraftCancel').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

    function escClose(e) {
      if (e.key === 'Escape') { close(); }
    }
    document.addEventListener('keydown', escClose);

    document.getElementById('proposeDraftSubmit').addEventListener('click', async () => {
      const draftType = document.getElementById('proposeDraftType').value;
      const name = document.getElementById('proposeDraftName').value.trim();
      const description = document.getElementById('proposeDraftDesc').value.trim();
      const errEl = document.getElementById('proposeDraftError');
      const submitBtn = document.getElementById('proposeDraftSubmit');

      if (!name) {
        errEl.textContent = '请输入草案名称。';
        errEl.style.display = 'block';
        return;
      }

      submitBtn.disabled = true;
      errEl.style.display = 'none';

      try {
        const result = await api(
          `/groups/${gid}/projects/${pid}/evidence-draft`,
          {
            method: 'POST',
            body: JSON.stringify({
              draft_type: draftType,
              name,
              description,
              evidence_link_ids: selectedIds,
            }),
          },
        );
        showToast(`已创建建模草案「${esc(name)}」（提案状态）`, 'success');
        // Clear selection and refresh evidence
        container._evidenceSelection.clear();
        try {
          const summary = await loadSummary();
          refreshEvidenceSummary(summary);
        } catch (_) { /* summary refresh is best-effort */ }
        close();
      } catch (err) {
        errEl.textContent = err.humanMessage || err.message || '提交失败';
        errEl.style.display = 'block';
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  // ── Goal scoped Ask panel ────────────────────────────────────────────

  function renderAskPanel(evidenceCount) {
    const hint = evidenceCount === 0
      ? '<div class="noEvidenceHint"><span>尚无项目证据。仍可提问，系统会返回项目级无证据结果，不会回退到全工作区检索。</span></div>'
      : '<p class="muted" style="font-size:var(--text-xs);margin:4px 0 8px">基于项目关联的证据文档检索回答，给出引用来源和可信度判断。</p>';
    return `
      <div class="goalAskPanel">
        <h4 class="goalAskTitle">项目内知识问答</h4>
        ${hint}
        <div class="goalAskInput">
          <input id="goalAskQuestion" type="text" placeholder="基于项目证据提问..." autocomplete="off" />
          <button id="goalAskSubmitBtn" class="primary">提问</button>
        </div>
        <p id="goalAskError" class="formError" style="display:none"></p>
        <div id="goalAskResult"></div>
      </div>`;
  }

  function bindGoalAsk(project) {
    const input = document.getElementById('goalAskQuestion');
    const btn = document.getElementById('goalAskSubmitBtn');
    const errEl = document.getElementById('goalAskError');
    const resultEl = document.getElementById('goalAskResult');
    if (!input || !btn || !errEl || !resultEl) return;
    const canSaveEvidence = isOwnerAdmin && project.status !== 'archived';

    const submit = async () => {
      const question = input.value.trim();
      if (!question) { errEl.textContent = '请输入问题。'; errEl.style.display = 'block'; return; }
      errEl.style.display = 'none';
      btn.disabled = true;
      resultEl.innerHTML = '<div class="loading"><span class="spinner"></span>正在检索项目证据...</div>';
      try {
        const data = await api(`/groups/${gid}/projects/${pid}/rag/answer`, {
          method: 'POST',
          body: JSON.stringify({ question, retrieval_method: 'hybrid' }),
        });
        data._sourceId = data.run_id || '';
        const cardHTML = answerCard(data, { showConfirm: false, groupId: gid, hideNextSteps: true });
        resultEl.innerHTML = cardHTML + renderSaveAnswerAction(data, canSaveEvidence);
        bindSaveAnswerAction(data);
      } catch (err) {
        errEl.textContent = err.humanMessage || err.message || '获取回答失败';
        errEl.style.display = 'block';
        resultEl.innerHTML = '';
      } finally {
        btn.disabled = false;
      }
    };

    btn.addEventListener('click', submit);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submit();
    });
  }

  function renderSaveAnswerAction(data, canSaveEvidence) {
    const canSaveRun = data.run_id && Array.isArray(data.citations) && data.citations.length > 0;
    if (!canSaveEvidence || !canSaveRun) return '';
    return `
      <div class="goalAskSaveRow">
        <button id="goalAskSaveEvidenceBtn" class="secondary small">保存为项目证据</button>
        <span id="goalAskSaveStatus" class="muted">保存后会作为用户确认的项目证据，不会自动写入 Ontology。</span>
      </div>`;
  }

  function bindSaveAnswerAction(data) {
    const btn = document.getElementById('goalAskSaveEvidenceBtn');
    const statusEl = document.getElementById('goalAskSaveStatus');
    if (!btn || !statusEl || !data.run_id) return;

    btn.addEventListener('click', async () => {
      btn.disabled = true;
      statusEl.textContent = '保存中...';
      try {
        await api(`/groups/${gid}/projects/${pid}/evidence-links`, {
          method: 'POST',
          body: JSON.stringify({
            evidence_type: 'rag_run',
            evidence_id: data.run_id,
            role: 'decision',
            note: '从 Pilot 项目问答保存',
          }),
        });
        btn.textContent = '已保存';
        statusEl.textContent = '已保存为项目证据。重复保存会复用已有证据链接。';
        try {
          const summary = await loadSummary();
          refreshEvidenceSummary(summary);
        } catch (_) {
          showToast('证据已保存，摘要刷新失败', 'info');
        }
      } catch (err) {
        btn.disabled = false;
        statusEl.textContent = err.humanMessage || err.message || '保存失败';
      }
    });
  }

  // ── Summary strip (header, all stages) ──────────────────────────────

  function summaryStripHTML(summary) {
    if (!summary) return '';
    const tk = summary.task_count || {};
    return `
      <div class="summaryStrip" id="projectSummaryStrip">
        <span class="summaryCount">证据 ${summary.evidence_count ?? 0}</span>
        <span class="summaryCount">对话 ${summary.conversation_count ?? 0}</span>
        <span class="summaryCount">任务 ${(tk.pending ?? 0) + (tk.in_progress ?? 0) + (tk.done ?? 0) + (tk.cancelled ?? 0)}</span>
        <span class="summaryCount">Agent ${summary.agent_run_count ?? 0}</span>
      </div>`;
  }

  // ── Data stage ─────────────────────────────────────────────────────────

  function renderDataStage(main, dsList) {
    main.innerHTML = `
      <div class="stagePanel">
        <div class="stagePanelHead">
          <h2>数据 — 数据集已就绪</h2>
          <span class="badge badgeOk">已完成</span>
          <p class="stageGuide">上传 CSV/XLSX 数据集，系统会自动分析字段类型、主键候选和外键关系，为生成 Ontology 草案做准备。</p>
        </div>
        <p>数据集已上传并完成分析。后端已识别字段类型、主键候选和外键建议。</p>
        ${isOwnerAdmin ? `
          <div class="stageCTAs">
            <button class="primary" id="genFromDataBtn">生成模型草案</button>
            <button class="secondary" id="uploadMoreBtn">上传更多数据</button>
            <p class="stageHint">数据准备就绪后即可开始建模。本地演示可先运行 <code>scripts/generate_manufacturing_dataset.py --preset tiny</code> 生成示例数据。</p>
          </div>
        ` : ''}
      </div>
      ${datasetListHTML(dsList)}
    `;
    if (isOwnerAdmin) {
      document.getElementById('uploadMoreBtn')?.addEventListener('click', () => openUploadDialog());
      document.getElementById('genFromDataBtn')?.addEventListener('click', async () => {
        const btn = document.getElementById('genFromDataBtn');
        btn.disabled = true; btn.textContent = '生成中...';
        try {
          const result = await api(`/groups/${gid}/projects/${pid}/model-drafts/generate`, { method: 'POST' });
          showToast(`已生成 ${result.generated_count} 条草案`, 'success');
          await renderFull();
        } catch (err) { showToast(err.humanMessage || err.message, 'error'); }
        finally { btn.disabled = false; btn.textContent = '生成模型草案'; }
      });
    }
  }

  async function importDemoData() {
    const btn = document.getElementById('loadDemoBtn');
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '导入中...';
    try {
      const result = await api(`/groups/${gid}/projects/${pid}/datasets/demo-data`, { method: 'POST' });
      showToast(`已导入 ${result.datasets_imported} 个数据集（${result.total_rows} 行），跳过 ${result.datasets_skipped} 个重复`, 'success');
      await renderFull();
    } catch (err) {
      showToast(err.humanMessage || err.message || '导入失败', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '载入制造业示例数据';
    }
  }

  // ── Future stages (model/validate/pilot) ───────────────────────────────

  function renderFutureStage(main, stage) {
    main.innerHTML = `
      <div class="stagePanel">
        <div class="stagePanelHead">
          <h2>${STAGE_LABELS[stage]} — 阶段进行中</h2>
          <p class="stageGuide">${stage === "model" ? "从已上传数据集生成 Ontology 草案，并由人工审核通过。每条草案都会携带数据集证据来源。" : stage === "validate" ? "构建模型包并生成数据绑定，将 Ontology 属性绑定到实际数据集字段。验证通过后即可进入 Pilot 阶段。" : stage === "pilot" ? "通过 Ontology runtime 查询业务对象，形成后续行动。Pilot 阶段可创建任务和项目专属对话。" : ""}</p>
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

    let html = '<div class="tableWrap"><table class="profileTable"><thead><tr><th scope="col">字段</th><th scope="col">类型</th><th scope="col">可空</th><th scope="col">非空</th><th scope="col">去重</th><th scope="col">PK</th></tr></thead><tbody>';
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
    html += '</tbody></table></div>';

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

  // ── Profile expand/collapse — stable delegated handler ──────────────────
  container._dsToggleHandler?.();
  const dsHandler = (e) => {
    const btn = e.target.closest('[id^="dsToggle-"]');
    if (!btn) return;
    const dsId = btn.id.replace('dsToggle-', '');
    const profileEl = document.getElementById('dsProfile-' + dsId);
    if (profileEl) {
      profileEl.hidden = !profileEl.hidden;
      btn.textContent = profileEl.hidden ? '查看字段▼' : '收起▲';
    }
  };
  container.addEventListener('click', dsHandler);
  container._dsToggleHandler = () => container.removeEventListener('click', dsHandler);

  await renderFull();
}
