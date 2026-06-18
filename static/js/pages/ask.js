import { api } from '../api.js';
import { state, setState } from '../state.js';
import { esc } from '../util/esc.js';
import { answerCard } from '../components/answer-card.js';
import { confidenceBadge } from '../components/badge.js';
import { showToast } from '../util/toast.js';
import { confirmTask, markConfirmed } from '../util/task-confirm.js';
import { loadOntologyEntityIndex } from '../util/ontology-links.js';

export async function render(container) {
  if (state.accessToken && !state.currentUser) {
    try {
      const me = await api('/auth/me');
      const groups = me.groups || [];
      const gid = groups[0]?.group_id || '';
      const role = groups[0]?.role || '';
      setState({ currentUser: me, groups, currentGroupId: gid, currentRole: role });
    } catch (_) { /* router will handle 401 */ }
  }

  const gid = state.currentGroupId;

  if (!state.accessToken) {
    container.innerHTML = '<p class="muted">请先登录。</p>';
    return;
  }
  if (!gid) {
    renderNoWorkspace(container);
    return;
  }

  container.innerHTML = `
    <div class="askPage">
      <h1 class="pageTitle">知识问答</h1>
      <p class="pageMeta">基于当前工作区的知识库回答问题，并给出引用来源和可信度判断。</p>
      <div id="askInner"></div>
    </div>`;
  const inner = document.getElementById('askInner');

  const hasDocs = await checkHasDocs(gid);
  if (!hasDocs) {
    renderEmptyDocs(inner, gid);
    return;
  }

  renderQuestionUI(inner, gid);
}

function renderNoWorkspace(container) {
  container.innerHTML = `
    <div class="emptyState">
      <div class="emptyIcon">空</div>
      <p class="emptyTitle">还没有选择工作区</p>
      <p class="emptyHint">请选择一个工作区，或创建新的工作区后再开始问答。</p>
      <button onclick="location.hash='#/groups'">前往工作区</button>
    </div>`;
}

async function checkHasDocs(gid) {
  try {
    const docs = await api(`/groups/${gid}/documents`);
    return docs && docs.length > 0;
  } catch (_) { return false; }
}

function renderEmptyDocs(inner, gid) {
  inner.innerHTML = `
    <div class="emptyState">
      <div class="emptyIcon">文</div>
      <p class="emptyTitle">知识库还没有文档</p>
      <p class="emptyHint">请先上传文档或导入本地知识库，然后再开始问答。</p>
      <button onclick="location.hash='#/groups/${gid}/documents'">前往知识库</button>
    </div>`;
}

function renderQuestionUI(inner, gid) {
  inner.innerHTML = `
    <div class="askInput">
      <input id="askQuestion" type="text" placeholder="例如：企业为什么需要 Ontology？" autofocus />
      <label class="askLimitControl" for="askLimit">
        <span>引用数量</span>
        <select id="askLimit" aria-label="引用数量">
          <option value="5" selected>5 条</option>
          <option value="8">8 条</option>
          <option value="10">10 条</option>
        </select>
      </label>
      <button id="askSubmitBtn">提问</button>
    </div>
    <p id="askError" class="formError" style="display:none"></p>
    <div id="askResult"></div>
    <div id="askRecent"></div>
  `;

  loadRecent(gid);

  let currentRunId = '';

  const submit = async () => {
    const question = document.getElementById('askQuestion').value.trim();
    const errEl = document.getElementById('askError');
    const resultEl = document.getElementById('askResult');
    const limit = Number(document.getElementById('askLimit')?.value || 5);
    if (!question) { errEl.textContent = '请输入问题。'; errEl.style.display = 'block'; return; }
    errEl.style.display = 'none';
    resultEl.innerHTML = '<div class="loading"><span class="spinner"></span>正在检索知识库...</div>';
    try {
      const data = await api(`/groups/${gid}/rag/answer`, {
        method: 'POST',
        body: JSON.stringify({ question, retrieval_method: 'hybrid', limit }),
      });
      currentRunId = data.run_id || '';
      data._sourceId = currentRunId;
      const oIdx = await loadOntologyEntityIndex(gid);
      resultEl.innerHTML = answerCard(data, { showConfirm: true, groupId: gid, ontologyIndex: oIdx });
      loadRecent(gid);
    } catch (err) {
      errEl.textContent = err.detail || '获取回答失败';
      errEl.style.display = 'block';
      resultEl.innerHTML = '';
    }
  };

  document.getElementById('askSubmitBtn').addEventListener('click', submit);
  document.getElementById('askQuestion').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submit();
  });

  // Event delegation for confirm-task buttons on #askInner
  inner.addEventListener('click', async (e) => {
    const btn = e.target.closest('.confirmTaskBtn');
    if (!btn || btn.disabled) return;
    const title = btn.dataset.title;
    btn.disabled = true;
    btn.textContent = '...';
    const task = await confirmTask(gid, title, currentRunId);
    if (task) {
      markConfirmed(btn);
      showToast('任务已创建');
    } else {
      btn.disabled = false;
      btn.textContent = '✓ 确认任务';
    }
  });
}

async function loadRecent(gid) {
  const el = document.getElementById('askRecent');
  if (!el) return;
  try {
    const runs = await api(`/groups/${gid}/rag/runs?limit=8`);
    if (!runs || !runs.length) { el.innerHTML = ''; return; }
    el.innerHTML = `
      <div class="recentList">
        <div class="recentTitle">最近问题</div>
        ${runs.map((r) => `
          <div class="recentItem" data-run-id="${r.id}">
            <span class="recentItem-text">${esc(r.question.substring(0, 80))}</span>
            ${confidenceBadge(r.confidence)}
          </div>
        `).join('')}
      </div>
      <div id="recentDetail"></div>`;

    // Click handler: fetch full detail and display
    el.querySelectorAll('.recentItem').forEach((item) => {
      item.addEventListener('click', async () => {
        const runId = item.dataset.runId;
        const detailEl = document.getElementById('recentDetail');
        detailEl.innerHTML = '<div class="loading"><span class="spinner"></span>正在加载详情...</div>';
        try {
          const detail = await api(`/groups/${gid}/rag/runs/${runId}`);
          const normalized = { ...detail, _sourceId: detail.id || detail.run_id };
          const oIdx = await loadOntologyEntityIndex(gid);
          detailEl.innerHTML = `
            <div class="recentDetailCard">
              <div class="recentDetailMeta">
                <span><strong>运行 ID：</strong>${esc(detail.id)}</span>
                <span><strong>检索方式：</strong>${esc(retrievalMethodLabel(detail.retrieval_method))}</span>
                <span><strong>模型：</strong>${esc(detail.model)}</span>
                <span><strong>状态：</strong>${esc(statusLabel(detail.status))}</span>
                ${detail.duration_ms != null ? `<span><strong>耗时：</strong>${detail.duration_ms} ms</span>` : ''}
                ${detail.retrieved_count != null ? `<span><strong>检索数：</strong>${detail.retrieved_count}</span>` : ''}
                <span><strong>时间：</strong>${new Date(detail.created_at).toLocaleString()}</span>
              </div>
              ${detail.error_message ? `<div class="recentDetailError">错误信息：${esc(detail.error_message)}</div>` : ''}
              ${answerCard(normalized, { showConfirm: false, ontologyIndex: oIdx })}
            </div>`;
        } catch (err) {
          showToast('加载历史详情失败', 'error');
          detailEl.innerHTML = '';
        }
      });
    });
  } catch (_) { /* silently skip */ }
}

function retrievalMethodLabel(m) {
  const map = { hybrid: '混合检索', keyword: '关键词检索', semantic: '语义检索', auto: '自动选择' };
  return map[m] || m;
}

function statusLabel(s) {
  const map = { success: '成功', no_evidence: '无证据', error: '失败' };
  return map[s] || s;
}
