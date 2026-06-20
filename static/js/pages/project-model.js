/** Model stage — /groups/:gid/projects/:pid (stage=model) */
import { api } from '../api.js';
import { state } from '../state.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

const DRAFT_TYPES = { object_type: '对象类型', property: '属性', link_type: '链接类型', action_type: '操作类型' };

export async function renderModelStage(container, gid, pid, project, reloadProject, isOwnerAdmin) {
  const main = document.getElementById('projectMain');
  if (!main) return;

  main.innerHTML = '<div class="loading"><span class="spinner"></span>加载模型数据...</div>';

  let draftsData, qualityData;
  try {
    [draftsData, qualityData] = await Promise.all([
      api(`/groups/${gid}/ontology/drafts?project_id=${pid}&limit=200`),
      api(`/groups/${gid}/projects/${pid}/model-drafts/quality`),
    ]);
  } catch (err) {
    main.innerHTML = `<div class="error"><p>${esc(err.humanMessage || err.message)}</p></div>`;
    return;
  }

  const drafts = draftsData.drafts || [];
  const quality = qualityData;
  const props = drafts.filter(d => d.draft_type === 'property');
  const objs = drafts.filter(d => d.draft_type === 'object_type');
  const links = drafts.filter(d => d.draft_type === 'link_type');
  const actions = drafts.filter(d => d.draft_type === 'action_type');
  const proposed = drafts.filter(d => d.status === 'proposed');
  const accepted = drafts.filter(d => d.status === 'accepted');
  const rejected = drafts.filter(d => d.status === 'rejected');

  main.innerHTML = buildHTML(drafts, quality, props, objs, links, actions, proposed, accepted, rejected);

  // Generation button
  if (isOwnerAdmin) {
    document.getElementById('genDraftsBtn')?.addEventListener('click', async () => {
      const btn = document.getElementById('genDraftsBtn');
      btn.disabled = true;
      btn.textContent = '生成中...';
      try {
        const result = await api(`/groups/${gid}/projects/${pid}/model-drafts/generate`, { method: 'POST' });
        showToast(`已生成 ${result.generated_count} 条草案`, 'success');
        await reloadProject();
      } catch (err) {
        showToast(err.humanMessage || err.message, 'error');
      } finally { btn.disabled = false; btn.textContent = '生成模型草案'; }
    });
  }

  // Review select-all
  document.getElementById('selectAllProposed')?.addEventListener('change', (e) => {
    document.querySelectorAll('.draftCheck:not(:disabled)').forEach(cb => { cb.checked = e.target.checked; });
  });
  // Batch accept
  document.getElementById('batchAcceptBtn')?.addEventListener('click', () => batchReview('accepted'));
  // Batch reject
  document.getElementById('batchRejectBtn')?.addEventListener('click', () => batchReview('rejected'));

  // Package build
  document.getElementById('buildPkgBtn')?.addEventListener('click', () => buildPackage());

  // Quality expand
  document.getElementById('toggleQuality')?.addEventListener('click', () => {
    const el = document.getElementById('qualityIssues');
    if (el) el.hidden = !el.hidden;
  });
}

function buildHTML(drafts, quality, props, objs, links, actions, proposed, accepted, rejected) {
  const isOwnerAdmin = state.currentRole === 'owner' || state.currentRole === 'admin';

  // Quality summary
  const qs = quality.status || 'PASS';
  const qBadge = qs === 'PASS' ? 'badgeOk' : qs === 'WARN' ? 'badgeWarn' : 'badgeDanger';
  const issues = quality.issues || [];
  const canBuild = qs !== 'FAIL' && proposed.length === 0;
  const blockReason = qs === 'FAIL' ? '质量门禁未通过 (FAIL)' :
    proposed.length > 0 ? `还有 ${proposed.length} 条草案待审核` : '';

  const counts = [
    { label: '对象类型', n: objs.length },
    { label: '属性', n: props.length },
    { label: '链接类型', n: links.length },
    { label: '操作类型', n: actions.length },
  ];

  return `
    <div class="stagePanel">
      <div class="stagePanelHead"><h2>模型 — 草案与审核</h2><span class="badge ${qBadge}">${qs}</span></div>
      <p>草案状态：${accepted.length} 已接受 · ${rejected.length} 已拒绝 · ${proposed.length} 待审核</p>
      ${isOwnerAdmin ? `
      <div class="stageCTAs">
        <button class="primary" id="genDraftsBtn">生成模型草案</button>
        ${proposed.length > 0 ? `
          <div class="reviewActions">
            <label class="fieldCheck"><input type="checkbox" id="selectAllProposed" /> 全选待审核</label>
            <button class="primary small" id="batchAcceptBtn">接受所选</button>
            <button class="secondary small" id="batchRejectBtn">拒绝所选</button>
          </div>
        ` : ''}
      </div>` : '<p class="muted">需要 owner 或 admin 角色才能操作。</p>'}
    </div>

    ${counts.some(c => c.n > 0) ? `
    <div class="draftSummary">
      ${counts.filter(c => c.n > 0).map(c => `<span class="badge badgeMuted">${c.label} ${c.n}</span>`).join(' ')}
    </div>` : ''}

    ${drafts.length === 0 ? '<p class="muted">尚无草案。点击"生成模型草案"从数据集创建。</p>' : `
    <div class="draftList">
      ${drafts.map(d => draftRowHTML(d, isOwnerAdmin)).join('')}
    </div>`}

    <div class="stagePanel" style="margin-top:20px">
      <div class="stagePanelHead"><h2>质量门禁</h2><span class="badge ${qBadge}">${qs}</span></div>
      <p>错误 ${quality.error_count || 0} · 警告 ${quality.warning_count || 0} · 草案 ${quality.draft_count || 0}</p>
      ${issues.length > 0 ? `<button class="linkBtn" id="toggleQuality">查看详情▼</button>
      <div id="qualityIssues" hidden><ul class="issueList">${issues.map(i => `<li><span class="badge ${i.severity === 'error' ? 'badgeDanger' : 'badgeWarn'}">${esc(i.severity)}</span> ${esc(i.code)}: ${esc(i.message || '')}</li>`).join('')}</ul></div>` : ''}
      ${isOwnerAdmin ? `
      <div class="stageCTAs" style="margin-top:12px">
        ${canBuild ? `<button class="primary" id="buildPkgBtn">构建 Package</button>` : `<button class="primary" disabled>构建 Package</button><p class="muted" style="margin:0">${esc(blockReason)}</p>`}
      </div>` : ''}
    </div>
  `;
}

function draftRowHTML(d, isOwnerAdmin) {
  const p = d.payload || {};
  const evidence = d.evidence_refs || [];
  const ev = evidence[0] || {};
  const safeEvidence = [];
  if (ev.dataset_id) safeEvidence.push(`dataset:${esc(ev.dataset_id.slice(0, 8))}`);
  if (ev.column) safeEvidence.push(`col:${esc(ev.column)}`);
  if (ev.role) safeEvidence.push(`role:${esc(ev.role)}`);
  if (p.generator) safeEvidence.push(esc(p.generator));

  const canSelect = d.status === 'proposed' && isOwnerAdmin;
  return `<div class="draftRow ${d.status === 'accepted' ? 'draftAccepted' : d.status === 'rejected' ? 'draftRejected' : ''}">
    <div class="draftRowHead">
      ${canSelect ? `<input type="checkbox" class="draftCheck" value="${esc(d.id)}" />` : ''}
      <span class="badge">${esc(DRAFT_TYPES[d.draft_type] || d.draft_type)}</span>
      <strong>${esc(d.name)}</strong>
      <span class="badge ${d.status === 'accepted' ? 'badgeOk' : d.status === 'rejected' ? 'badgeDanger' : 'badgeMuted'}">${esc(d.status)}</span>
    </div>
    <div class="draftRowBody">
      <span class="muted">${esc(p.api_name || '')}</span>
      ${p.object_type ? `<span>→ ${esc(p.object_type)}</span>` : ''}
      ${p.value_type ? `<span class="typeTag txt">${esc(p.value_type)}</span>` : ''}
      ${p.cardinality ? `<span>${esc(p.cardinality)}</span>` : ''}
      ${safeEvidence.length ? `<span class="muted">${safeEvidence.join(' · ')}</span>` : ''}
      ${d.reviewed_by ? `<span class="muted">审核: ${esc(d.reviewed_by.slice(0, 8))} ${esc(d.review_note || '')}</span>` : ''}
    </div>
    ${d.description ? `<div class="draftDesc">${esc(d.description.slice(0, 200))}</div>` : ''}
  </div>`;
}

async function batchReview(status) {
  const checked = [...document.querySelectorAll('.draftCheck:checked')];
  if (checked.length === 0) { showToast('请先选择要审核的草案', 'error'); return; }
  const ids = checked.map(cb => cb.value);

  if (status === 'rejected') {
    openConfirmDialog(`拒绝 ${ids.length} 条草案`, '请输入拒绝原因（必填）：', true, async (reason) => {
      await doReview(ids, status, reason);
    });
  } else {
    openConfirmDialog(`接受 ${ids.length} 条草案`, `确认接受 ${ids.length} 条草案吗？此操作不可撤销。`, false, async () => {
      await doReview(ids, status, 'ok');
    });
  }
}

async function doReview(ids, status, note) {
  try {
    await api(`/groups/${state.currentGroupId}/ontology/drafts/review-batch`, {
      method: 'POST',
      body: JSON.stringify({ draft_ids: ids, status, review_note: note }),
    });
    showToast(`已${status === 'accepted' ? '接受' : '拒绝'} ${ids.length} 条草案`, 'success');
    location.reload();
  } catch (err) {
    showToast(err.humanMessage || err.message, 'error');
  }
}

function openConfirmDialog(title, message, needsReason, onConfirm) {
  const overlay = document.createElement('div');
  overlay.className = 'dialogOverlay';
  overlay.innerHTML = `<div class="dialog" role="dialog"><h2 class="dialogTitle">${esc(title)}</h2>
    <div class="dialogBody"><p>${esc(message)}</p>${needsReason ? '<label class="field"><span>原因</span><textarea id="dlgReason" rows="2"></textarea></label>' : ''}</div>
    <p class="formError" id="dlgError" style="display:none"></p>
    <div class="dialogActions"><button class="secondary" id="dlgCancel">取消</button><button class="primary" id="dlgConfirm">确认</button></div></div>`;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  document.getElementById('dlgCancel').addEventListener('click', close);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  document.addEventListener('keydown', function esc(e) { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); } });

  document.getElementById('dlgConfirm').addEventListener('click', () => {
    const reason = needsReason ? document.getElementById('dlgReason')?.value.trim() : '';
    if (needsReason && !reason) {
      document.getElementById('dlgError').textContent = '拒绝原因不能为空';
      document.getElementById('dlgError').style.display = 'block';
      return;
    }
    close();
    onConfirm(reason || undefined);
  });
}

async function buildPackage() {
  const qualityEl = document.querySelector('.stagePanel .badge');
  const qs = qualityEl?.textContent || '';
  if (qs.includes('WARN')) {
    openConfirmDialog('构建 Package', '质量状态为 WARN。确认使用当前警告状态构建 Package？', true, async (reason) => {
      await doBuild(reason);
    });
  } else {
    await doBuild();
  }
}

async function doBuild(reason) {
  const gid = state.currentGroupId;
  const hash = location.hash.replace('#', '');
  const pid = hash.split('/')[3];
  try {
    const body = reason ? { allow_warnings: true, override_reason: reason } : {};
    const result = await api(`/groups/${gid}/projects/${pid}/model-drafts/packages`, {
      method: 'POST', body: JSON.stringify(body),
    });
    showToast(`Package v${result.version} 已构建`, 'success');
    location.reload();
  } catch (err) {
    showToast(err.humanMessage || err.message, 'error');
  }
}
