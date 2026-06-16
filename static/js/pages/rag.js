import { api } from '../api.js';
import { state } from '../state.js';
import { panel } from '../components/panel.js';
import { confidenceBadge } from '../components/badge.js';

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!gid) { container.innerHTML = '<p>请先选择工作区。</p>'; return; }

  container.innerHTML = '<h1 class="pageTitle">RAG 调试台</h1><p class="pageMeta">测试检索方式、查看引用和历史运行记录。</p><div id="ragInner"></div>';
  const inner = document.getElementById('ragInner');

  const askPanel = panel('测试问题', `
    <label>问题 <input id="ragQuestion" type="text" placeholder="例如：企业 AI 转型为什么需要 Ontology？" /></label>
    <label style="display:inline-flex;align-items:center;gap:8px">
      检索方式：
      <select id="ragMethod">
        <option value="hybrid" selected>混合检索</option>
        <option value="keyword">关键词检索</option>
        <option value="semantic">语义检索</option>
        <option value="auto">自动选择</option>
      </select>
    </label>
    <label style="display:inline-flex;align-items:center;gap:8px">
      引用数量：
      <select id="ragLimit">
        <option value="5" selected>5 条</option>
        <option value="8">8 条</option>
        <option value="10">10 条</option>
      </select>
    </label>
    <button id="ragAskBtn">提问</button>
    <p id="ragError" class="formError" style="display:none"></p>
    <div id="ragResult" style="margin-top:16px"></div>
  `);

  const historyPanel = panel('最近运行', '<div id="ragRuns">正在加载...</div>');

  inner.innerHTML = `${askPanel}${historyPanel}`;

  async function loadRuns() {
    try {
      const runs = await api(`/groups/${gid}/rag/runs?limit=10`);
      const el = document.getElementById('ragRuns');
      if (!runs || !runs.length) { el.innerHTML = '<p class="muted">暂无运行记录。</p>'; return; }
      el.innerHTML = `<table class="dataTable">
        <thead><tr><th>问题</th><th>可信度</th><th>检索方式</th><th>引用数</th><th>时间</th></tr></thead>
        <tbody>${runs.map((r) => `
          <tr>
            <td>${esc(r.question.substring(0, 70))}</td>
            <td>${confidenceBadge(r.confidence)}</td>
            <td>${esc(retrievalMethodLabel(r.retrieval_method))}</td>
            <td>${r.citation_count}</td>
            <td class="muted">${new Date(r.created_at).toLocaleString()}</td>
          </tr>
        `).join('')}</tbody>
      </table>`;
    } catch (_) { document.getElementById('ragRuns').innerHTML = '<p class="muted">运行记录加载失败。</p>'; }
  }

  loadRuns();

  document.getElementById('ragAskBtn').addEventListener('click', async () => {
    const errEl = document.getElementById('ragError');
    const resultEl = document.getElementById('ragResult');
    const question = document.getElementById('ragQuestion').value.trim();
    if (!question) { errEl.textContent = '请输入问题。'; errEl.style.display = 'block'; return; }
    errEl.style.display = 'none';
    resultEl.innerHTML = '<div class="loading"><span class="spinner"></span>正在生成回答...</div>';
    try {
      const data = await api(`/groups/${gid}/rag/answer`, {
        method: 'POST',
        body: JSON.stringify({
          question,
          retrieval_method: document.getElementById('ragMethod').value,
          limit: Number(document.getElementById('ragLimit').value || 5),
        }),
      });
      resultEl.innerHTML = `
        <div class="ragAnswer">
          <div class="ragAnswerHeader">
            ${confidenceBadge(data.confidence)}
            <span class="muted">模型：${esc(data.model)} | 检索方式：${esc(retrievalMethodLabel(data.retrieval_method))}</span>
          </div>
          <p class="ragAnswerText">${esc(data.answer)}</p>
          ${data.knowledge_gaps?.length ? `<div class="ragGaps"><strong>知识缺口：</strong><ul>${data.knowledge_gaps.map((g) => `<li>${esc(g)}</li>`).join('')}</ul></div>` : ''}
          ${data.next_steps?.length ? `<div class="ragNext"><strong>下一步建议：</strong><ul>${data.next_steps.map((s) => `<li>${esc(s)}</li>`).join('')}</ul></div>` : ''}
          ${data.citations?.length ? `
            <details class="ragCitations">
              <summary>引用来源（${data.citations.length}）</summary>
              ${data.citations.map((c, i) => `
                <div class="citationItem">
                  <strong>[${i + 1}] ${esc(c.title)}</strong>
                  <span class="muted">${typeof c.score === 'number' && c.score > 0 ? '匹配分：' + c.score.toFixed(3) : ''}</span>
                  <p>${esc(c.snippet || '')}</p>
                </div>
              `).join('')}
            </details>
          ` : ''}
        </div>
      `;
      loadRuns();
    } catch (err) {
      errEl.textContent = err.detail || 'RAG 请求失败';
      errEl.style.display = 'block';
    }
  });
}

function retrievalMethodLabel(method) {
  return {
    hybrid: '混合检索',
    keyword: '关键词检索',
    semantic: '语义检索',
    auto: '自动选择',
  }[method] || method;
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
