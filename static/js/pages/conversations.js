import { api } from '../api.js';
import { state } from '../state.js';
import { panel } from '../components/panel.js';
import { confidenceBadge } from '../components/badge.js';

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!gid) { container.innerHTML = '<p>请先选择工作区。</p>'; return; }

  container.innerHTML = '<h1 class="pageTitle">多轮对话</h1><p class="pageMeta">围绕同一咨询主题持续追问、补充背景和沉淀建议。</p><div class="loading"><span class="spinner"></span>正在加载对话...</div>';

  async function loadList() {
    try {
      return await api(`/groups/${gid}/conversations`) || [];
    } catch (_) { return []; }
  }

  const convs = await loadList();

  const newPanel = panel('新建对话', `
    <label>对话标题 <input id="convTitle" type="text" placeholder="客户 AI 转型诊断" /></label>
    <button id="createConvBtn">创建对话</button>
  `);

  const listHtml = convs.length === 0
    ? '<div class="emptyState"><div class="emptyIcon">问</div><p class="emptyTitle">还没有对话</p><p class="emptyHint">新建一个咨询对话，围绕客户画像和业务问题持续追问。</p></div>'
    : `<table class="dataTable">
        <thead><tr><th>标题</th><th>消息数</th><th>更新时间</th><th>打开</th></tr></thead>
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
    <h1 class="pageTitle">多轮对话</h1>
    <p class="pageMeta">围绕同一咨询主题持续追问、补充背景和沉淀建议。</p>
    ${newPanel}${panel('对话列表', listHtml)}
    <div id="chatArea" style="margin-top:16px"></div>
  `;

  document.getElementById('createConvBtn').addEventListener('click', async () => {
    const title = document.getElementById('convTitle').value.trim() || '新的咨询对话';
    try {
      await api(`/groups/${gid}/conversations`, { method: 'POST', body: JSON.stringify({ title }) });
      render(container, params);
    } catch (err) { alert(err.detail || '创建对话失败'); }
  });

  container.addEventListener('click', async (e) => {
    const btn = e.target.closest('.openConvBtn');
    if (!btn) return;
    await renderChat(container, gid, btn.dataset.id);
  });
}

async function renderChat(container, gid, convId) {
  const area = document.getElementById('chatArea');
  area.innerHTML = '<div class="loading"><span class="spinner"></span>正在加载消息...</div>';

  try {
    const detail = await api(`/groups/${gid}/conversations/${convId}`);
    const messages = detail.messages || [];
    area.innerHTML = `
      <div class="chatPanel">
        <h3>${esc(detail.title)}</h3>
        <div class="chatMessages" id="chatMessages">
          ${messages.map((m) => `
            <div class="chatMsg chatMsg-${m.role}">
              <div class="chatRole">${roleLabel(m.role)}</div>
              <div class="chatContent">${esc(m.content)}</div>
              ${m.confidence ? `<span class="chatConfidence">${confidenceBadge(m.confidence)}</span>` : ''}
              ${m.tool_calls?.length ? `<div class="chatToolCalls">工具：${esc(m.tool_calls[0]?.name || '')}</div>` : ''}
            </div>
          `).join('')}
        </div>
        <div class="chatInput">
          <input id="chatInput" type="text" placeholder="继续追问或补充客户背景..." />
          <button id="chatSendBtn">发送</button>
        </div>
      </div>
    `;

    const msgContainer = document.getElementById('chatMessages');
    if (msgContainer) msgContainer.scrollTop = msgContainer.scrollHeight;

    document.getElementById('chatSendBtn').addEventListener('click', async () => {
      const input = document.getElementById('chatInput');
      const question = input.value.trim();
      if (!question) return;
      input.value = '';
      input.disabled = true;
      try {
        await api(`/groups/${gid}/conversations/${convId}/messages`, {
          method: 'POST',
          body: JSON.stringify({ question, retrieval_method: 'hybrid' }),
        });
        await renderChat(container, gid, convId);
      } catch (err) { alert(err.detail || '发送失败'); input.disabled = false; }
    });

    document.getElementById('chatInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') document.getElementById('chatSendBtn').click();
    });
  } catch (err) {
    area.innerHTML = `<div class="error">加载对话失败：${esc(err.detail)}</div>`;
  }
}

function roleLabel(role) {
  if (role === 'user') return '你';
  if (role === 'tool') return '工具';
  return '顾问';
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
