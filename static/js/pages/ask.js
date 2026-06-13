import { api } from '../api.js';
import { state, setState } from '../state.js';
import { esc } from '../util/esc.js';
import { answerCard } from '../components/answer-card.js';
import { confidenceBadge } from '../components/badge.js';

export async function render(container) {
  // Auto-hydrate user state on direct navigation (cold load)
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
    container.innerHTML = '<p class="muted">Please sign in first.</p>';
    return;
  }
  if (!gid) {
    renderNoWorkspace(container);
    return;
  }

  // Shell
  container.innerHTML = `
    <div class="askPage">
      <h1 class="pageTitle">Ask</h1>
      <p class="pageMeta">Ask anything about your knowledge base</p>
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

/* ── sub-renderers ─────────────────────────────────────────── */

function renderNoWorkspace(container) {
  container.innerHTML = `
    <div class="emptyState">
      <div class="emptyIcon">👋</div>
      <p class="emptyTitle">No workspace selected</p>
      <p class="emptyHint">Select a workspace from the navbar or create one to get started.</p>
      <button onclick="location.hash='#/groups'">Go to Workspaces</button>
    </div>`;
}

async function checkHasDocs(gid) {
  try {
    const docs = await api(`/groups/${gid}/documents/search?q=a&limit=1`);
    return docs && docs.length > 0;
  } catch (_) { return false; }
}

function renderEmptyDocs(inner, gid) {
  inner.innerHTML = `
    <div class="emptyState">
      <div class="emptyIcon">📄</div>
      <p class="emptyTitle">No documents yet</p>
      <p class="emptyHint">Upload documents to your knowledge base to start asking questions.</p>
      <button onclick="location.hash='#/groups/${gid}/documents'">Go to Knowledge →</button>
    </div>`;
}

function renderQuestionUI(inner, gid) {
  inner.innerHTML = `
    <div class="askInput">
      <input id="askQuestion" type="text" placeholder="Type your question…" autofocus />
      <button id="askSubmitBtn">Ask →</button>
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
    if (!question) { errEl.textContent = 'Please enter a question.'; errEl.style.display = 'block'; return; }
    errEl.style.display = 'none';
    resultEl.innerHTML = '<div class="loading"><span class="spinner"></span>Searching your knowledge base…</div>';
    try {
      const data = await api(`/groups/${gid}/rag/answer`, {
        method: 'POST',
        body: JSON.stringify({ question, retrieval_method: 'hybrid' }),
      });
      resultEl.innerHTML = answerCard(data);
      loadRecent(gid);
    } catch (err) {
      errEl.textContent = err.detail || 'Failed to get answer';
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
        <div class="recentTitle">Recent Questions</div>
        ${runs.map((r) => `
          <div class="recentItem">
            <span class="recentItem-text">${esc(r.question.substring(0, 80))}</span>
            ${confidenceBadge(r.confidence)}
          </div>
        `).join('')}
      </div>`;
  } catch (_) { /* silently skip */ }
}
