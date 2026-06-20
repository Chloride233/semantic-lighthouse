import { api } from '../api.js';
import { state, setState } from '../state.js';
import { navigate } from '../router.js';
import { showToast } from '../util/toast.js';

export async function render(container) {
  if (!state.accessToken) {
    container.innerHTML = '<p class="muted">请先登录。</p>';
    return;
  }

  container.innerHTML = `
    <div class="onboardPage">
      <div class="onboardIcon">启</div>
      <h1 class="onboardTitle">创建你的第一个工作区</h1>
      <p class="onboardText">
        工作区用于隔离团队、文档和问答记录。<br>
        后续的知识检索和 RAG 回答都会继承这个权限边界。
      </p>
      <div class="onboardField">
        <label>工作区名称</label>
        <input id="onboardName" type="text" placeholder="企业 AI 转型知识库" maxlength="160" />
      </div>
      <p id="onboardError" class="formError" style="display:none"></p>
      <button id="onboardCreateBtn" class="onboardSubmit">创建工作区</button>
    </div>
  `;

  document.getElementById('onboardCreateBtn').addEventListener('click', async () => {
    const errEl = document.getElementById('onboardError');
    const name = document.getElementById('onboardName').value.trim() || '我的工作区';
    try {
      await api('/groups', {
        method: 'POST',
        body: JSON.stringify({ name }),
      });
      const me = await api('/auth/me');
      const groups = me.groups || [];
      const created = groups.find((g) => g.group_name === name) || groups[groups.length - 1];
      setState({
        groups,
        currentUser: me,
        currentGroupId: created?.group_id || '',
        currentRole: created?.role || 'owner',
      });
      showToast('工作区已创建。', 'success');
      navigate(`/groups/${state.currentGroupId}/projects`);
    } catch (err) {
      errEl.textContent = err.humanMessage || err.detail || '创建工作区失败';
      errEl.style.display = 'block';
    }
  });
}
