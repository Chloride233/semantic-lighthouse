import { api } from '../api.js';
import { state } from '../state.js';
import { panel } from '../components/panel.js';
import { confidenceBadge } from '../components/badge.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

const RETRIEVAL_LABELS = {
  hybrid: '混合检索', keyword: '关键词', semantic: '语义', auto: '自动',
};
const CITATION_LABELS = {
  keyword: '关键词', semantic: '语义', hybrid: '混合',
};

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!gid) { container.innerHTML = '<p class="muted">请先选择工作区。</p>'; return; }
  const hash = location.hash.replace('#', '');
  const qp = new URLSearchParams(hash.split('?')[1] || '');
  const targetConversationId = qp.get('conversation_id');

  container.innerHTML = '<div class="legacyPage"><h1 class="pageTitle">多轮对话</h1><p class="pageMeta">围绕同一咨询主题持续追问、补充背景和沉淀建议。</p><div class="loading"><span class="spinner"></span> 正在加载对话...</div>';

  const convs = await loadList(gid);

  const newPanelHtml = panel('新建对话', `
    <label class="formLabel">对话标题 <input id="convTitle" type="text" placeholder="客户 AI 转型诊断" /></label>
    <button id="createConvBtn">创建对话</button>
  `);

  const listHtml = convs.length === 0
    ? '<div class="emptyState"><div class="emptyIcon">问</div><p class="emptyTitle">还没有对话</p><p class="emptyHint">新建一个咨询对话，围绕客户画像和业务问题持续追问。</p></div>'
    : `<table class="dataTable legacyTable">
        <thead><tr><th>标题</th><th>消息数</th><th>更新时间</th><th>操作</th></tr></thead>
        <tbody>${convs.map((c) => `
          <tr>
            <td><strong>${esc(c.title)}</strong></td>
            <td>${c.message_count}</td>
            <td class="muted">${new Date(c.updated_at).toLocaleString()}</td>
            <td><button class="secondary small openConvBtn" data-id="${c.id}">打开</button></td>
          </tr>
        `).join('')}</tbody>
      </table>`;

  container.innerHTML = `
    <div class="legacyPage">
    <h1 class="pageTitle">多轮对话</h1>
    <p class="pageMeta">围绕同一咨询主题持续追问、补充背景和沉淀建议。</p>
    ${newPanelHtml}${panel('对话列表', listHtml)}
    <div id="chatArea" style="margin-top:16px"></div>
    </div>
  `;

  if (targetConversationId && convs.some((c) => c.id === targetConversationId)) {
    await renderChat(container, gid, targetConversationId);
  }

  document.getElementById('createConvBtn').addEventListener('click', async () => {
    const title = document.getElementById('convTitle').value.trim() || '新的咨询对话';
    try {
      await api(`/groups/${gid}/conversations`, { method: 'POST', body: JSON.stringify({ title }) });
      render(container, params);
    } catch (err) { showToast('创建对话失败：' + (err.detail || '请检查网络连接'), 'error'); }
  });

  container.addEventListener('click', async (e) => {
    const btn = e.target.closest('.openConvBtn');
    if (!btn) return;
    await renderChat(container, gid, btn.dataset.id);
  });
}

async function loadList(gid) {
  try { return await api(`/groups/${gid}/conversations`) || []; }
  catch (_) { return []; }
}

/* ── Chat View ──────────────────────────────────────────────────────── */

async function renderChat(container, gid, convId) {
  const area = document.getElementById('chatArea');
  area.innerHTML = '<div class="loading"><span class="spinner"></span> 正在加载消息...</div>';

  try {
    const detail = await api(`/groups/${gid}/conversations/${convId}`);
    const messages = detail.messages || [];
    area.innerHTML = `
      <div class="chatPanel">
        <h3>${esc(detail.title)}</h3>
        <div class="chatMessages" id="chatMessages">
          ${messages.map((m) => renderMessage(m)).join('')}
        </div>
        <p id="chatError" class="formError" style="display:none"></p>
        <div class="chatInput">
          <input id="chatInput" type="text" placeholder="继续追问或补充客户背景..." />
          <button id="chatSendBtn">发送</button>
        </div>
      </div>
    `;

    scrollToBottom();
    bindChatEvents(gid, convId);
  } catch (err) {
    area.innerHTML = `<div class="panel"><div class="panelBody" style="color:var(--danger, #e74c3c)">加载对话失败：${esc(err.detail || '请刷新页面重试')}</div></div>`;
  }
}

/* ── Message Rendering ──────────────────────────────────────────────── */

function renderMessage(m) {
  switch (m.role) {
    case 'user': return renderUserMessage(m);
    case 'assistant': return renderAssistantMessage(m);
    case 'tool': return renderToolMessage(m);
    default: return `<div class="chatMsg"><div class="chatContent">${esc(m.content)}</div></div>`;
  }
}

function renderUserMessage(m) {
  return `
    <div class="chatMsg chatMsg-user">
      <div class="chatRole">你</div>
      <div class="chatContent">${esc(m.content)}</div>
    </div>`;
}

function renderAssistantMessage(m) {
  const citations = m.citations || [];
  const gaps = m.knowledge_gaps || [];
  const retrievalLabel = RETRIEVAL_LABELS[m.retrieval_method] || m.retrieval_method || '';
  const citationCount = citations.length;

  let contextParts = [];
  if (retrievalLabel) contextParts.push(`<span>🔍 ${retrievalLabel}</span>`);
  if (citationCount > 0) contextParts.push(`<span>📄 ${citationCount} 条引用</span>`);
  if (m.model) contextParts.push(`<span class="muted">模型：${esc(m.model)}</span>`);
  const contextBar = contextParts.length
    ? `<div class="msgContext">${contextParts.join(' · ')}</div>`
    : '';

  let citationsHtml = '';
  if (citationCount > 0) {
    citationsHtml = `
      <details class="msgCitations">
        <summary>引用来源 (${citationCount})</summary>
        <ul class="citationList">
          ${citations.map((c, i) => `
            <li class="citationItem">
              <span class="citationIdx">[${i + 1}]</span>
              <span class="citationTitle">${esc(c.title || c.file_name || '未命名文档')}</span>
              ${c.retrieval_method ? `<span class="citationMethod muted">${CITATION_LABELS[c.retrieval_method] || c.retrieval_method}</span>` : ''}
              ${c.score != null ? `<span class="citationScore muted">相关度：${Number(c.score).toFixed(2)}</span>` : ''}
              ${c.snippet ? `<p class="citationSnippet">${esc(c.snippet)}</p>` : ''}
            </li>
          `).join('')}
        </ul>
      </details>`;
  }

  let gapsHtml = '';
  if (gaps.length > 0) {
    gapsHtml = `
      <div class="msgGaps">
        <strong>知识缺口：</strong>
        <ul>${gaps.map(g => `<li>${esc(g)}</li>`).join('')}</ul>
      </div>`;
  }

  return `
    <div class="chatMsg chatMsg-assistant">
      <div class="chatRole">顾问</div>
      <div class="chatContent">${esc(m.content)}</div>
      ${m.confidence ? `<span class="chatConfidence">${confidenceBadge(m.confidence)}</span>` : ''}
      ${contextBar}
      ${citationsHtml}
      ${gapsHtml}
    </div>`;
}

function renderToolMessage(m) {
  const toolCalls = m.tool_calls || [];
  const toolNames = toolCalls.map(tc => tc.name || '未知工具').join(', ');
  const args = toolCalls[0]?.arguments || {};
  const argsStr = Object.keys(args).length ? esc(JSON.stringify(args)) : '';

  let resultHtml = '';
  if (m.content) {
    const maxLen = 300;
    const full = esc(m.content);
    if (full.length > maxLen) {
      resultHtml = `
        <details class="msgToolResult">
          <summary>工具结果（${full.length} 字符，点击展开）</summary>
          <pre class="toolResultPre">${full}</pre>
        </details>`;
    } else {
      resultHtml = `<pre class="toolResultPre">${full}</pre>`;
    }
  }

  return `
    <div class="chatMsg chatMsg-tool">
      <div class="chatRole">🔧 工具</div>
      <div class="toolInfo">
        <span class="toolName">${esc(toolNames)}</span>
        ${argsStr ? `<span class="toolArgs">参数：${argsStr}</span>` : ''}
      </div>
      ${resultHtml}
    </div>`;
}

/* ── Chat Events ────────────────────────────────────────────────────── */

function bindChatEvents(gid, convId) {
  const sendBtn = document.getElementById('chatSendBtn');
  const input = document.getElementById('chatInput');
  const errEl = document.getElementById('chatError');

  sendBtn.addEventListener('click', () => sendMessage(gid, convId, input, sendBtn, errEl));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendBtn.click();
  });
}

async function sendMessage(gid, convId, input, sendBtn, errEl) {
  const question = input.value.trim();
  if (!question) return;

  input.disabled = true;
  sendBtn.disabled = true;
  sendBtn.textContent = '发送中...';
  if (errEl) errEl.style.display = 'none';

  try {
    await api(`/groups/${gid}/conversations/${convId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ question, retrieval_method: 'hybrid', limit: 8 }),
    });
    input.value = '';
    await renderChat(document.getElementById('outlet') || document.body, gid, convId);
  } catch (err) {
    const errMsg = '发送失败：' + (err.detail || '请检查服务是否正常运行');
    if (errEl) {
      errEl.textContent = errMsg;
      errEl.style.display = 'block';
    } else {
      showToast(errMsg, 'error');
    }
    input.disabled = false;
    sendBtn.disabled = false;
    sendBtn.textContent = '发送';
  }
}

function scrollToBottom() {
  const el = document.getElementById('chatMessages');
  if (el) el.scrollTop = el.scrollHeight;
}
