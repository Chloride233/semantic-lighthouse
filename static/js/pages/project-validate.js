/** Validate stage — quality, contract, bindings, activation */
import { api } from '../api.js';
import { state } from '../state.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

export async function renderValidateStage(container, gid, pid, project, reloadProject, isOwnerAdmin) {
  const main = document.getElementById('projectMain');
  if (!main) return;
  main.innerHTML = '<div class="loading"><span class="spinner"></span>加载验证数据...</div>';

  let quality, pkgsData, bindings;
  try {
    [quality, pkgsData, bindings] = await Promise.all([
      api(`/groups/${gid}/projects/${pid}/model-drafts/quality`),
      api(`/groups/${gid}/projects/${pid}/model-drafts/packages?limit=5`),
      api(`/groups/${gid}/projects/${pid}/runtime/bindings`).catch(() => []),
    ]);
  } catch (err) {
    main.innerHTML = `<div class="error"><p>${esc(err.humanMessage || err.message)}</p></div>`;
    return;
  }

  const packages = pkgsData.packages || [];
  const latestPkg = packages[0];
  let contract = null;
  if (latestPkg) {
    try {
      contract = await api(`/groups/${gid}/projects/${pid}/model-drafts/packages/${latestPkg.id}/contract`);
    } catch (_) { contract = null; }
  }

  const qs = quality.status || 'PASS';
  const qBadge = qs === 'PASS' ? 'badgeOk' : qs === 'WARN' ? 'badgeWarn' : 'badgeDanger';

  main.innerHTML = `
    <div class="stagePanel"><div class="stagePanelHead"><h2>质量门禁</h2><span class="badge ${qBadge}">${esc(qs)}</span></div>
      <p>错误 ${quality.error_count || 0} · 警告 ${quality.warning_count || 0}</p>
      ${(quality.issues || []).length > 0 ? `<ul class="issueList">${quality.issues.slice(0, 10).map(i => `<li><span class="badge ${i.severity === 'error' ? 'badgeDanger' : 'badgeWarn'}">${esc(i.severity)}</span> ${esc(i.code)}: ${esc(i.message || '')}</li>`).join('')}</ul>` : ''}
    </div>

    <div class="stagePanel"><div class="stagePanelHead"><h2>业务合约</h2>${latestPkg ? `<span class="badge">v${latestPkg.version}</span>` : ''}</div>
      ${!latestPkg ? '<p class="muted">尚未构建 Package</p>' : `
        <div class="contractMeta">
          <span class="muted">semantic_hash: <code>${esc((contract?.manifest?.semantic_hash || latestPkg.content_hash || '').slice(0, 18))}…</code></span>
          <span class="muted">content_hash: <code>${esc(latestPkg.content_hash.slice(0, 16))}…</code></span>
        </div>
        ${contract ? contractSummaryHTML(contract) : '<p class="muted">合约编译结果不可用</p>'}
      `}
    </div>

    <div class="stagePanel"><div class="stagePanelHead"><h2>数据绑定</h2><span class="badge badgeMuted">${(bindings || []).length} 条</span></div>
      ${(bindings || []).length === 0 ? '<p class="muted">尚无数据绑定。请先生成。</p>' : bindingsListHTML(bindings)}
      ${isOwnerAdmin ? `
      <div class="stageCTAs" style="margin-top:12px">
        <button class="primary" id="genBindingsBtn">生成数据绑定</button>
        ${(bindings || []).length > 0 ? `<button class="primary" id="activateBtn" style="margin-left:8px">激活 Pilot</button>` : ''}
      </div>` : '<p class="muted">需要 owner 或 admin 角色才能操作。</p>'}
    </div>
  `;

  if (isOwnerAdmin) {
    document.getElementById('genBindingsBtn')?.addEventListener('click', async () => {
      const btn = document.getElementById('genBindingsBtn');
      btn.disabled = true; btn.textContent = '生成中...';
      try {
        const r = await api(`/groups/${gid}/projects/${pid}/runtime/bindings/generate`, { method: 'POST' });
        showToast(`已创建 ${r.created_count} 条绑定`, 'success');
        if (r.issues && r.issues.length) showIssues(r.issues);
        location.reload();
      } catch (err) { showToast(err.humanMessage || err.message, 'error'); }
      finally { btn.disabled = false; btn.textContent = '生成数据绑定'; }
    });

    document.getElementById('activateBtn')?.addEventListener('click', () => {
      openConfirmDialog('激活 Pilot', '确认激活 Pilot 运行时？此操作将项目从"验证"推进到"Pilot"阶段，并记录审计。', false, async () => {
        try {
          const r = await api(`/groups/${gid}/projects/${pid}/runtime/activate`, { method: 'POST' });
          showToast('Pilot 已激活', 'success');
          await reloadProject();
        } catch (err) { showToast(err.humanMessage || err.message, 'error'); }
      });
    });
  }
}

function contractSummaryHTML(contract) {
  const ots = contract.object_types || [];
  const props = contract.properties || [];
  const links = contract.link_types || [];
  const actions = contract.action_types || [];
  return `<div class="contractSummary">
    <p>${ots.length} 对象类型 · ${props.length} 属性 · ${links.length} 链接 · ${actions.length} 操作</p>
    <details><summary>查看类型详情</summary>
      ${ots.length ? `<h4>对象类型</h4><table class="profileTable"><tr><th>api_name</th><th>display_name</th><th>primary_key</th></tr>${ots.map(o => `<tr><td>${esc(o.api_name)}</td><td>${esc(o.display_name || '')}</td><td>${esc(o.primary_key || '')}</td></tr>`).join('')}</table>` : ''}
      ${props.length ? `<h4>属性</h4><table class="profileTable"><tr><th>api_name</th><th>object_type</th><th>value_type</th><th>required</th></tr>${props.map(p => `<tr><td>${esc(p.api_name)}</td><td>${esc(p.object_type)}</td><td><span class="typeTag txt">${esc(p.value_type)}</span></td><td>${p.required ? '✓' : ''}</td></tr>`).join('')}</table>` : ''}
    </details>
  </div>`;
}

function bindingsListHTML(bindings) {
  return `<div class="datasetList">${bindings.map(b => `
    <div class="datasetItem">
      <div class="datasetItemHead"><strong>${esc(b.object_type_api_name)}</strong> <span class="badge badgeOk">${esc(b.status)}</span></div>
      <div class="datasetItemMeta">
        <span>PK: ${esc(b.primary_key_column)}</span>
        <span>dataset: ${esc(b.dataset_id.slice(0, 8))}…</span>
        <span>${Object.keys(b.property_mappings || {}).length} 属性</span>
      </div>
    </div>`).join('')}</div>`;
}

function showIssues(issues) {
  const msgs = issues.map(i => `${i.code}: ${i.message}`).join('\n');
  alert('绑定问题:\n' + msgs);
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
  document.getElementById('dlgConfirm').addEventListener('click', () => { close(); onConfirm(); });
}
