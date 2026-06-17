import { api } from '../api.js';
import { state } from '../state.js';
import { taskCard, bindTaskCardEvents } from '../components/task-card.js';
import { answerCard } from '../components/answer-card.js';
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
    <div class="taskPage">
      <h1 class="pageTitle">轻量任务</h1>
      <p class="pageMeta">从问答确认的行动项，非全功能项目管理工具。</p>
      <div class="taskFilters">
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
      const detailEl = card.querySelector('.taskSourceDetail');
      if (!detailEl) return;

      // Toggle collapse
      if (detailEl.style.display === 'block') {
        detailEl.style.display = 'none';
        return;
      }

      if (sourceType !== 'rag_run') {
        detailEl.innerHTML = '<p class="muted" style="padding:12px">暂不支持预览此来源类型。</p>';
        detailEl.style.display = 'block';
        return;
      }

      detailEl.innerHTML = '<div class="loading" style="padding:16px"><span class="spinner"></span>加载来源...</div>';
      detailEl.style.display = 'block';

      const cacheKey = `${sourceType}:${sourceId}`;
      if (sourceCache.has(cacheKey)) {
        detailEl.innerHTML = sourceCache.get(cacheKey);
        return;
      }

      try {
        const run = await api(`/groups/${gid}/rag/runs/${sourceId}`);
        const html = buildSourceDetail(run, sourceId, gid);
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

function buildSourceDetail(run, sourceId, gid) {
  return `
    <div class="taskSourceHeader">
      <span>🔗 来源追溯 · RAG问答</span>
      <span class="taskSourceMeta">${new Date(run.created_at).toLocaleString()} · ${esc(retrievalLabel(run.retrieval_method))}</span>
    </div>
    <div class="taskSourceQuestion">原始提问：${esc(run.question)}</div>
    ${answerCard(run, { showConfirm: false, hideNextSteps: true })}
    <a class="taskSourceLink" href="#/groups/${gid}/rag">在调试台查看 →</a>`;
}

function retrievalLabel(m) {
  const map = { hybrid: '混合检索', keyword: '关键词检索', semantic: '语义检索', auto: '自动选择' };
  return map[m] || m;
}

export { STATUS_LABELS, SOURCE_LABELS };
