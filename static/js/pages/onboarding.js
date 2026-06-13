import { api } from '../api.js';
import { state, setState } from '../state.js';
import { navigate } from '../router.js';
import { showToast } from '../util/toast.js';

export async function render(container) {
  if (!state.accessToken) {
    container.innerHTML = '<p class="muted">Please sign in first.</p>';
    return;
  }

  container.innerHTML = `
    <div class="onboardPage">
      <div class="onboardIcon">👋</div>
      <h1 class="onboardTitle">Welcome to Semantic Lighthouse</h1>
      <p class="onboardText">
        Create a workspace to organize your team's knowledge<br>
        and start asking questions grounded in your documents.
      </p>
      <div class="onboardField">
        <label>Workspace Name</label>
        <input id="onboardName" type="text" placeholder="My Team Workspace" maxlength="160" />
      </div>
      <p id="onboardError" class="formError" style="display:none"></p>
      <button id="onboardCreateBtn" class="onboardSubmit">Create Workspace →</button>
    </div>
  `;

  document.getElementById('onboardCreateBtn').addEventListener('click', async () => {
    const errEl = document.getElementById('onboardError');
    const name = document.getElementById('onboardName').value.trim() || 'My Workspace';
    try {
      const group = await api('/groups', {
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
      showToast('Workspace created!', 'success');
      navigate(`/groups/${state.currentGroupId}/documents`);
    } catch (err) {
      errEl.textContent = err.detail || 'Failed to create workspace';
      errEl.style.display = 'block';
    }
  });
}
