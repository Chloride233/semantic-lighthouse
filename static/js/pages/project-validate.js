/** Validate stage */
import { api } from '../api.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';
import { openProjectDialog } from './project-dialog.js';

export async function renderValidateStage(container, gid, pid, project, reloadProject, isOwnerAdmin) {
  const main = document.getElementById('projectMain');
  if (!main) return;

  async function loadAndRender() {
    main.innerHTML = '<div class="loading"><span class="spinner"></span>加载验证数据...</div>';

    let quality, pkgsData, bindings, contract = null, bindingsError = null, contractError = null;

    try {
      [quality, pkgsData] = await Promise.all([
        api(`/groups/${gid}/projects/${pid}/model-drafts/quality`),
        api(`/groups/${gid}/projects/${pid}/model-drafts/packages?limit=5`),
      ]);
    } catch (err) {
      main.innerHTML = `<div class="error"><p>${esc(err.humanMessage || err.message)}</p></div>`;
      return;
    }

    // Bindings — may legitimately not exist yet
    try {
      bindings = await api(`/groups/${gid}/projects/${pid}/runtime/bindings`);
    } catch (err) {
      if (err.status === 404) { bindings = []; }
      else { bindingsError = err.humanMessage || err.message; }
    }

    const packages = pkgsData.packages || [];
    const latestPkg = packages[0];
    if (latestPkg) {
      try {
        contract = await api(`/groups/${gid}/projects/${pid}/model-drafts/packages/${latestPkg.id}/contract`);
      } catch (err) {
        if (err.status === 404) { contract = null; }
        else { contractError = err.humanMessage || err.message; }
      }
    }

    const qs = quality.status || 'PASS';
    const qBadge = qs === 'PASS' ? 'badgeOk' : qs === 'WARN' ? 'badgeWarn' : 'badgeDanger';
    const bindingList = bindings || [];

    // Determine which Object Types from the contract need bindings
    const contractOTs = (contract?.object_types || []).map(o => o.api_name);
    const boundOTs = bindingList.map(b => b.object_type_api_name);
    const missingOTs = contractOTs.filter(ot => !boundOTs.includes(ot));
    const hasAllBindings = contractOTs.length > 0 && missingOTs.length === 0;
    const allActive = bindingList.every(b => b.status === 'active');

    main.innerHTML = `
      <div class="stagePanel"><div class="stagePanelHead"><h2>验证 — 构建与绑定</h2></div><p class="stageGuide">将已审核通过的模型草案固化为不可变的 Ontology 模型包（Package），然后生成数据绑定，把 Ontology 业务属性映射到数据集的实际字段。验证通过后即可激活 Pilot 进入查询运行时。</p></div>
      <div class="stagePanel"><div class="stagePanelHead"><h2>质量门禁</h2><span class="badge ${qBadge}">${esc(qs)}</span></div>
        <p>错误 ${quality.error_count || 0} · 警告 ${quality.warning_count || 0}</p>
        ${(quality.issues || []).length > 0 ? `<ul class="issueList">${quality.issues.slice(0, 10).map(i => `<li><span class="badge ${i.severity === 'error' ? 'badgeDanger' : 'badgeWarn'}">${esc(i.severity)}</span> ${esc(i.code)}: ${esc(i.message || '')}</li>`).join('')}</ul>` : ''}
      </div>

      <div class="stagePanel"><div class="stagePanelHead"><h2>业务合约</h2>${latestPkg ? `<span class="badge">v${latestPkg.version}</span>` : ''}</div>
        ${!latestPkg ? '<p class="muted">尚未构建 Package</p>' : contractError ? `<div class="error"><p>${esc(contractError)}</p></div>` :
          `<div class="contractMeta"><span class="muted">semantic_hash: <code>${esc((contract?.manifest?.semantic_hash || latestPkg.content_hash || '').slice(0, 18))}…</code></span><span class="muted">content_hash: <code>${esc(latestPkg.content_hash.slice(0, 16))}…</code></span></div>
          ${contract ? contractSummaryHTML(contract) : ''}`}
      </div>

      <div class="stagePanel"><div class="stagePanelHead"><h2>数据绑定</h2><span class="badge badgeMuted">${bindingList.length} 条</span></div>
        ${bindingsError ? `<div class="error"><p>${esc(bindingsError)}</p></div>` : ''}
        ${bindingList.length === 0 ? '<p class="muted">尚无数据绑定。点击下方按钮，系统自动将已审核的 Ontology 属性绑定到数据集字段，生成可查询的 typed binding。</p>' : bindingsListHTML(bindingList)}
        ${missingOTs.length > 0 ? `<p class="muted">缺失绑定：${missingOTs.map(esc).join(', ')}</p>` : ''}
        ${isOwnerAdmin ? `
        <div class="stageCTAs" style="margin-top:12px">
          <button class="primary" id="genBindingsBtn">生成数据绑定</button>
          ${hasAllBindings && allActive ? '<button class="primary" id="activateBtn" style="margin-left:8px">激活 Pilot</button>' : ''}
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
          if (r.issues && r.issues.length > 0) {
            // Render issues in page rather than alert
            renderGenIssues(r.issues);
          }
          await loadAndRender();
        } catch (err) { showToast(err.humanMessage || err.message, 'error'); }
        finally { btn.disabled = false; btn.textContent = '生成数据绑定'; }
      });

      document.getElementById('activateBtn')?.addEventListener('click', () => {
        openProjectDialog('激活 Pilot', '确认激活 Pilot 运行时？此操作将项目从"验证"推进到"Pilot"阶段，并记录审计。', {}, async () => {
          const r = await api(`/groups/${gid}/projects/${pid}/runtime/activate`, { method: 'POST' });
          showToast('Pilot 已激活', 'success');
          await reloadProject();
        });
      });
    }
  }

  function renderGenIssues(issues) {
    // Add issues display below bindings section
    const container = document.querySelector('.stagePanel:last-of-type');
    if (!container) return;
    const existing = document.getElementById('genIssues');
    if (existing) existing.remove();
    const div = document.createElement('div');
    div.id = 'genIssues';
    div.style.marginTop = '8px';
    div.innerHTML = `<ul class="issueList">${issues.map(i => `<li><span class="badge ${i.severity === 'error' ? 'badgeDanger' : 'badgeWarn'}">${esc(i.severity)}</span> ${esc(i.code)}: ${esc(i.message || '')}</li>`).join('')}</ul>`;
    container.appendChild(div);
  }

  await loadAndRender();
}

function contractSummaryHTML(contract) {
  const ots = contract.object_types || [];
  const props = contract.properties || [];
  const links = contract.link_types || [];
  const actions = contract.action_types || [];
  return `<div class="contractSummary"><p>${ots.length} 对象类型 · ${props.length} 属性 · ${links.length} 链接 · ${actions.length} 操作</p>
    <details><summary>查看类型详情</summary>
      ${ots.length ? `<h4>对象类型</h4><table class="profileTable"><tr><th>api_name</th><th>display_name</th><th>primary_key</th></tr>${ots.map(o => `<tr><td>${esc(o.api_name)}</td><td>${esc(o.display_name || '')}</td><td>${esc(o.primary_key || '')}</td></tr>`).join('')}</table>` : ''}
      ${props.length ? `<h4>属性</h4><table class="profileTable"><tr><th>api_name</th><th>object_type</th><th>value_type</th><th>required</th></tr>${props.map(p => `<tr><td>${esc(p.api_name)}</td><td>${esc(p.object_type)}</td><td><span class="typeTag txt">${esc(p.value_type)}</span></td><td>${p.required ? '✓' : ''}</td></tr>`).join('')}</table>` : ''}
    </details></div>`;
}

function bindingsListHTML(bindings) {
  return `<div class="datasetList">${bindings.map(b => `
    <div class="datasetItem"><div class="datasetItemHead"><strong>${esc(b.object_type_api_name)}</strong> <span class="badge badgeOk">${esc(b.status)}</span></div>
    <div class="datasetItemMeta"><span>PK: ${esc(b.primary_key_column)}</span><span>${Object.keys(b.property_mappings || {}).length} 属性</span></div></div>`).join('')}</div>`;
}
