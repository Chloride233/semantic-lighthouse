import { api } from '../api.js';
import { state, setState } from '../state.js';
import { esc } from '../util/esc.js';
import { answerCard } from '../components/answer-card.js';
import { confidenceBadge } from '../components/badge.js';

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
      <button id="askSubmitBtn">提问</button>
    </div>
    <p id="askError" class="formError" style="display:none"></p>
    <div id="askResult"></div>
    <div id="askRecent"></div>
  `;

  loadRecent(gid);

  const submit = async () => {
    const question = document.getElementById('askQuestion').value.trim();
    const errEl = document.getElementById('askError');
    const resultEl = document.getElementById('askResult');
    if (!question) { errEl.textContent = '请输入问题。'; errEl.style.display = 'block'; return; }
    errEl.style.display = 'none';
    resultEl.innerHTML = '<div class="loading"><span class="spinner"></span>正在检索知识库...</div>';
    try {
      const data = await api(`/groups/${gid}/rag/answer`, {
        method: 'POST',
        body: JSON.stringify({ question, retrieval_method: 'hybrid' }),
      });
      resultEl.innerHTML = answerCard(data);
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
          <div class="recentItem">
            <span class="recentItem-text">${esc(r.question.substring(0, 80))}</span>
            ${confidenceBadge(r.confidence)}
          </div>
        `).join('')}
      </div>`;
  } catch (_) { /* silently skip */ }
}
