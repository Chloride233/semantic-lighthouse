import { api } from '../api.js';
import { state } from '../state.js';
import { taskCard, bindTaskCardEvents } from '../components/task-card.js';
import { answerCard } from '../components/answer-card.js';
import { loadOntologyEntityIndex } from '../util/ontology-links.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

const STATUS_LABELS = { pending: '待处理', in_progress: '进行中', done: '已完成', cancelled: '已取消' };
const SOURCE_LABELS = { rag_run: 'RAG问答', conversation: '对话', agent_run: 'Agent运行', manual: '手动创建' };
const STATUSES = ['pending', 'in_progress', 'done', 'cancelled'];

const sourceCache = new Map();

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;

  if (!state.accessToken) {
    container.innerHTML = '<p class="muted">请先登录。</p>';
    return;
  }
  if (!gid) {
    container.innerHTML = '<p class="muted">请先选择工作区。</p>';
    return;
  }

  const hash = location.hash.replace('#', '');
  const urlParams = new URLSearchParams(hash.split('?')[1] || '');
  const activeStatus = urlParams.get('status') || '';

  container.innerHTML = `
    <div class="legacyPage">
      <h1 class="pageTitle">轻量任务</h1>
      <p class="pageMeta">从问答确认的行动项，非全功能项目管理工具。</p>
      <div class="legacyFilters taskFilters">
        <button class="taskFilter ${activeStatus === '' ? 'active' : ''}" data-status="">全部</button>
        ${STATUSES.map(s => `
          <button class="taskFilter ${activeStatus === s ? 'active' : ''}" data-status="${s}">${STATUS_LABELS[s]}</button>
        `).join('')}
      </div>
      <div id="taskList"></div>
    </div>`;

  container.querySelectorAll('.taskFilter').forEach(btn => {
    btn.addEventListener('click', () => {
      const s = btn.dataset.status;
      location.hash = s ? `#/groups/${gid}/tasks?status=${s}` : `#/groups/${gid}/tasks`;
    });
  });

  await loadTasks(gid, activeStatus);
}

async function loadTasks(gid, statusFilter) {
  const el = document.getElementById('taskList');
  if (!el) return;

  try {
    const qs = statusFilter ? `?status=${statusFilter}` : '';
    const data = await api(`/groups/${gid}/tasks${qs}`);
    const tasks = data.tasks || [];

    if (!tasks.length) {
      el.innerHTML = `
        <div class="emptyState">
          <div class="emptyIcon">任</div>
          <p class="emptyTitle">暂无任务</p>
          <p class="emptyHint">从问答页面的「下一步建议」中确认任务。</p>
          <button onclick="location.hash='#/ask'">前往问答</button>
        </div>`;
      return;
    }

    const onStatusChange = async () => { await loadTasks(gid, statusFilter); };
    sourceCache.clear();
    el.innerHTML = tasks.map(t => taskCard(t, gid, onStatusChange, SOURCE_LABELS)).join('');
    bindTaskCardEvents(el, gid, onStatusChange);
    bindExpandEvents(el, gid);
  } catch (err) {
    el.innerHTML = '<p class="muted">任务加载失败。</p>';
  }
}

function bindExpandEvents(container, gid) {
  container.querySelectorAll('.taskCard').forEach(card => {
    card.addEventListener('click', async () => {
      const sourceType = card.dataset.sourceType;
      const sourceId = card.dataset.sourceId;
      const taskId = card.dataset.taskId;
      const detailEl = card.querySelector('.taskSourceDetail');
      if (!detailEl) return;

      // Toggle collapse
      if (detailEl.style.display === 'block') {
        detailEl.style.display = 'none';
        return;
      }

      detailEl.innerHTML = '<div class="loading" style="padding:16px"><span class="spinner"></span>加载证据...</div>';
      detailEl.style.display = 'block';

      const cacheKey = `task:${taskId}`;
      if (sourceCache.has(cacheKey)) {
        detailEl.innerHTML = sourceCache.get(cacheKey);
        return;
      }

      try {
        const task = await api(`/groups/${gid}/tasks/${taskId}`);
        const packetHtml = buildEvidencePacket(task.evidence_packet);
        if (sourceType !== 'rag_run') {
          sourceCache.set(cacheKey, packetHtml);
          detailEl.innerHTML = packetHtml;
          return;
        }

        let sourceHtml;
        try {
          const run = await api(`/groups/${gid}/rag/runs/${sourceId}`);
          const oIdx = await loadOntologyEntityIndex(gid);
          sourceHtml = buildSourceDetail(run, sourceId, gid, oIdx);
        } catch (err) {
          let errMsg = '加载来源失败';
          if (err.status === 404) errMsg = '来源已删除';
          else if (err.status === 403) errMsg = '无权访问该 RAG 运行记录';
          sourceHtml = `<p class="muted" style="padding:12px">${errMsg}</p>`;
        }
        const html = `${packetHtml}${sourceHtml}`;
        sourceCache.set(cacheKey, html);
        detailEl.innerHTML = html;
      } catch (err) {
        let errMsg = '加载来源失败';
        if (err.status === 404) errMsg = '来源已删除';
        else if (err.status === 403) errMsg = '无权访问该 RAG 运行记录';
        detailEl.innerHTML = `<p class="muted" style="padding:12px">${errMsg}</p>`;
      }
    });
  });
}

function buildEvidencePacket(packet) {
  if (!packet) return '<p class="muted" style="padding:12px">暂无证据包。</p>';
  const riskClass = { low: 'badgeOk', medium: 'badgeWarn', high: 'badgeErr' }[packet.risk?.level] || 'badgeMuted';
  const riskLabel = { low: '低风险', medium: '中风险', high: '高风险' }[packet.risk?.level] || packet.risk?.level || '-';
  const source = packet.source || {};
  const action = packet.proposed_action || {};
  const scope = packet.affected_scope || {};
  const link = source.project_evidence_link;
  const reasons = packet.risk?.reasons || [];
  const checks = packet.review_requirements?.required_checks || [];
  const anchors = packet.evidence_anchors || [];

  return `
    <div class="taskEvidencePacket">
      <div class="taskEvidenceHead">
        <span>证据包 v${esc(packet.packet_version || '1.0')}</span>
        <span class="badge ${riskClass}">${esc(riskLabel)}</span>
      </div>
      <div class="taskEvidenceGrid">
        <div><span>来源</span><strong>${esc(sourceLabel(source.source_type))}</strong></div>
        <div><span>状态</span><strong>${esc(source.source_status || '-')}</strong></div>
        <div><span>置信</span><strong>${esc(source.confidence || '-')}</strong></div>
        <div><span>引用</span><strong>${source.citation_count ?? 0}</strong></div>
      </div>
      ${source.question ? `<div class="taskEvidenceLine"><span>问题</span><p>${esc(source.question)}</p></div>` : ''}
      <div class="taskEvidenceLine"><span>行动</span><p>${esc(action.title || '')}${action.description ? ` · ${esc(action.description)}` : ''}</p></div>
      <div class="taskEvidenceLine"><span>范围</span><p>${esc(scope.project_id || '无项目')} · ${esc(scope.source_type || '-')} · ${esc(scope.source_id || '-')}</p></div>
      ${link ? `<div class="taskEvidenceLine"><span>项目证据</span><p>${esc(link.role || '-')} · ${esc(link.status || '-')}</p></div>` : ''}
      ${reasons.length ? `<ul class="taskEvidenceList">${reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}
      ${anchors.length ? `<div class="taskEvidenceAnchors">${anchors.map(a => `
        <div class="taskEvidenceAnchor">
          <strong>${esc(a.title || '未命名证据')}</strong>
          <span>${esc(a.file_name || '-')} · #${esc(String(a.chunk_index ?? '-'))} · ${esc(a.retrieval_method || '-')}</span>
          ${a.heading_path ? `<span>${esc(a.heading_path)}</span>` : ''}
          ${a.match_reason ? `<p>${esc(a.match_reason)}</p>` : ''}
        </div>`).join('')}</div>` : ''}
      ${checks.length ? `<div class="taskEvidenceChecks">${checks.map(c => `<span>${esc(c)}</span>`).join('')}</div>` : ''}
      <div class="taskEvidenceRollback">${esc(packet.rollback_note || '')}</div>
    </div>`;
}

function buildSourceDetail(run, sourceId, gid, ontologyIndex = null) {
  return `
    <div class="taskSourceHeader">
      <span>🔗 来源追溯 · RAG问答</span>
      <span class="taskSourceMeta">${new Date(run.created_at).toLocaleString()} · ${esc(retrievalLabel(run.retrieval_method))}</span>
    </div>
    <div class="taskSourceQuestion">原始提问：${esc(run.question)}</div>
    ${answerCard(run, { showConfirm: false, hideNextSteps: true, groupId: gid, ontologyIndex })}
    <a class="taskSourceLink" href="#/groups/${gid}/rag">在调试台查看 →</a>`;
}

function retrievalLabel(m) {
  const map = { hybrid: '混合检索', keyword: '关键词检索', semantic: '语义检索', auto: '自动选择' };
  return map[m] || m;
}

function sourceLabel(type) {
  return SOURCE_LABELS[type] || type || '未知';
}

export { STATUS_LABELS, SOURCE_LABELS };
