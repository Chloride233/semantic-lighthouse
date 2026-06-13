import { api } from '../api.js';
import { state } from '../state.js';
import { panel } from '../components/panel.js';
import { confidenceBadge } from '../components/badge.js';

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!gid) { container.innerHTML = '<p>Please select a group first.</p>'; return; }

  container.innerHTML = '<h1 class="pageTitle">RAG Console</h1><p class="pageMeta">Ask questions, review citations</p><div id="ragInner"></div>';
  const inner = document.getElementById('ragInner');

  const askPanel = panel('Ask a Question', `
    <label>Question <input id="ragQuestion" type="text" placeholder="What is the ETL pipeline architecture?" /></label>
    <label style="display:inline-flex;align-items:center;gap:8px">
      Method:
      <select id="ragMethod">
        <option value="hybrid" selected>Hybrid</option>
        <option value="keyword">Keyword</option>
        <option value="semantic">Semantic</option>
        <option value="auto">Auto</option>
      </select>
    </label>
    <button id="ragAskBtn">Ask</button>
    <p id="ragError" class="formError" style="display:none"></p>
    <div id="ragResult" style="margin-top:16px"></div>
  `);

  const historyPanel = panel('Recent Runs', '<div id="ragRuns">Loading...</div>');

  inner.innerHTML = `${askPanel}${historyPanel}`;

  async function loadRuns() {
    try {
      const runs = await api(`/groups/${gid}/rag/runs?limit=10`);
      const el = document.getElementById('ragRuns');
      if (!runs || !runs.length) { el.innerHTML = '<p class="muted">No runs yet.</p>'; return; }
      el.innerHTML = `<table class="dataTable">
        <thead><tr><th>Question</th><th>Confidence</th><th>Method</th><th>Citations</th><th>Time</th></tr></thead>
        <tbody>${runs.map((r) => `
          <tr>
            <td>${esc(r.question.substring(0, 70))}</td>
            <td>${confidenceBadge(r.confidence)}</td>
            <td>${esc(r.retrieval_method)}</td>
            <td>${r.citation_count}</td>
            <td class="muted">${new Date(r.created_at).toLocaleString()}</td>
          </tr>
        `).join('')}</tbody>
      </table>`;
    } catch (_) { document.getElementById('ragRuns').innerHTML = '<p class="muted">Could not load runs.</p>'; }
  }

  loadRuns();

  document.getElementById('ragAskBtn').addEventListener('click', async () => {
    const errEl = document.getElementById('ragError');
    const resultEl = document.getElementById('ragResult');
    const question = document.getElementById('ragQuestion').value.trim();
    if (!question) { errEl.textContent = 'Please enter a question.'; errEl.style.display = 'block'; return; }
    errEl.style.display = 'none';
    resultEl.innerHTML = '<div class="loading"><span class="spinner"></span>Asking...</div>';
    try {
      const data = await api(`/groups/${gid}/rag/answer`, {
        method: 'POST',
        body: JSON.stringify({
          question,
          retrieval_method: document.getElementById('ragMethod').value,
        }),
      });
      resultEl.innerHTML = `
        <div class="ragAnswer">
          <div class="ragAnswerHeader">
            ${confidenceBadge(data.confidence)}
            <span class="muted">Model: ${esc(data.model)} | Method: ${esc(data.retrieval_method)}</span>
          </div>
          <p class="ragAnswerText">${esc(data.answer)}</p>
          ${data.knowledge_gaps?.length ? `<div class="ragGaps"><strong>Knowledge Gaps:</strong><ul>${data.knowledge_gaps.map((g) => `<li>${esc(g)}</li>`).join('')}</ul></div>` : ''}
          ${data.next_steps?.length ? `<div class="ragNext"><strong>Next Steps:</strong><ul>${data.next_steps.map((s) => `<li>${esc(s)}</li>`).join('')}</ul></div>` : ''}
          ${data.citations?.length ? `
            <details class="ragCitations">
              <summary>Citations (${data.citations.length})</summary>
              ${data.citations.map((c, i) => `
                <div class="citationItem">
                  <strong>[${i + 1}] ${esc(c.title)}</strong>
                  <span class="muted">score: ${c.score?.toFixed(3) || '-'}</span>
                  <p>${esc(c.snippet || '')}</p>
                </div>
              `).join('')}
            </details>
          ` : ''}
        </div>
      `;
      loadRuns();
    } catch (err) {
      errEl.textContent = err.detail || 'RAG request failed';
      errEl.style.display = 'block';
    }
  });
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
