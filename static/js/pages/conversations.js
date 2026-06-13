import { api } from '../api.js';
import { state } from '../state.js';
import { panel } from '../components/panel.js';
import { confidenceBadge } from '../components/badge.js';

export async function render(container, params) {
  const gid = params.gid || state.currentGroupId;
  if (!gid) { container.innerHTML = '<p>Please select a group first.</p>'; return; }

  container.innerHTML = '<h1 class="pageTitle">Conversations</h1><p class="pageMeta">Multi-turn consulting dialogue</p><div class="loading"><span class="spinner"></span>Loading conversations...</div>';

  async function loadList() {
    try {
      return await api(`/groups/${gid}/conversations`) || [];
    } catch (_) { return []; }
  }

  const convs = await loadList();

  const newPanel = panel('New Conversation', `
    <label>Title <input id="convTitle" type="text" placeholder="Consulting session" /></label>
    <button id="createConvBtn">Create</button>
  `);

  const listHtml = convs.length === 0
    ? '<div class="emptyState"><div class="emptyIcon">&#x1f4ac;</div><p class="emptyTitle">No conversations</p><p class="emptyHint">Start a consulting dialogue with your knowledge base.</p></div>'
    : `<table class="dataTable">
        <thead><tr><th>Title</th><th>Messages</th><th>Updated</th><th>Open</th></tr></thead>
        <tbody>${convs.map((c) => `
          <tr>
            <td><strong>${esc(c.title)}</strong></td>
            <td>${c.message_count}</td>
            <td class="muted">${new Date(c.updated_at).toLocaleString()}</td>
            <td><button class="secondary small openConvBtn" data-id="${c.id}">Open</button></td>
          </tr>
        `).join('')}</tbody>
      </table>`;

  container.innerHTML = `${newPanel}${panel('Conversations', listHtml)}<div id="chatArea" style="margin-top:16px"></div>`;

  document.getElementById('createConvBtn').addEventListener('click', async () => {
    const title = document.getElementById('convTitle').value.trim() || 'New Conversation';
    try {
      await api(`/groups/${gid}/conversations`, { method: 'POST', body: JSON.stringify({ title }) });
      render(container, params);
    } catch (err) { alert(err.detail || 'Failed to create'); }
  });

  container.addEventListener('click', async (e) => {
    const btn = e.target.closest('.openConvBtn');
    if (!btn) return;
    await renderChat(container, gid, btn.dataset.id);
  });
}

async function renderChat(container, gid, convId) {
  const area = document.getElementById('chatArea');
  area.innerHTML = '<div class="loading"><span class="spinner"></span>Loading messages...</div>';

  try {
    const detail = await api(`/groups/${gid}/conversations/${convId}`);
    const messages = detail.messages || [];
    area.innerHTML = `
      <div class="chatPanel">
        <h3>${esc(detail.title)}</h3>
        <div class="chatMessages" id="chatMessages">
          ${messages.map((m) => `
            <div class="chatMsg chatMsg-${m.role}">
              <div class="chatRole">${m.role === 'user' ? 'You' : m.role === 'tool' ? 'Tool' : 'Assistant'}</div>
              <div class="chatContent">${esc(m.content)}</div>
              ${m.confidence ? `<span class="chatConfidence">${confidenceBadge(m.confidence)}</span>` : ''}
              ${m.tool_calls?.length ? `<div class="chatToolCalls">Tool: ${esc(m.tool_calls[0]?.name || '')}</div>` : ''}
            </div>
          `).join('')}
        </div>
        <div class="chatInput">
          <input id="chatInput" type="text" placeholder="Type your message..." />
          <button id="chatSendBtn">Send</button>
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
      } catch (err) { alert(err.detail || 'Failed to send'); input.disabled = false; }
    });

    document.getElementById('chatInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') document.getElementById('chatSendBtn').click();
    });
  } catch (err) {
    area.innerHTML = `<div class="error">Failed to load conversation: ${esc(err.detail)}</div>`;
  }
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
