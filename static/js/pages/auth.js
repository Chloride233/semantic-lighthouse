import { api } from '../api.js';
import { state, setState } from '../state.js';
import { navigate } from '../router.js';
import { showToast } from '../util/toast.js';

export async function render(container) {
  container.innerHTML = `
    <div class="authPage">
      <div class="authBrandIcon">🔦</div>
      <h1 class="authTitle">Semantic Lighthouse</h1>
      <p class="authTagline">Enterprise AI Knowledge Advisor</p>

      <div id="authSuccess" class="authSuccess">Account created! You can now sign in.</div>

      <div class="authCard">
        <div class="authTabs" role="tablist" aria-label="Authentication">
          <button class="authTab active" data-tab="signin" role="tab" aria-selected="true" tabindex="0">Sign In</button>
          <button class="authTab" data-tab="register" role="tab" aria-selected="false" tabindex="-1">Register</button>
        </div>

        <form id="signinForm">
          <div class="authField">
            <label>Email</label>
            <input id="loginEmail" type="email" autocomplete="username" required />
            <p class="authFieldError" id="loginEmailError"></p>
          </div>
          <div class="authField">
            <label>Password</label>
            <input id="loginPassword" type="password" autocomplete="current-password" required />
            <p class="authFieldError" id="loginPasswordError"></p>
          </div>
          <p id="loginError" class="formError" style="display:none"></p>
          <button type="submit" class="authSubmit">Sign In →</button>
        </form>

        <form id="registerForm" style="display:none">
          <div class="authField">
            <label>Email</label>
            <input id="registerEmail" type="email" autocomplete="username" required />
          </div>
          <div class="authField">
            <label>Display Name</label>
            <input id="registerName" type="text" autocomplete="name" required />
          </div>
          <div class="authField">
            <label>Password</label>
            <input id="registerPassword" type="password" autocomplete="new-password" required minlength="8" />
          </div>
          <p id="registerError" class="formError" style="display:none"></p>
          <button type="submit" class="authSubmit">Create Account →</button>
        </form>
      </div>

      <p class="authSwitch" id="authSwitchText">
        No account? <a id="authSwitchLink">Create one</a>
      </p>
    </div>
  `;

  let activeTab = 'signin';

  function switchTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.authTab').forEach((el) => {
      const selected = el.dataset.tab === tab;
      el.classList.toggle('active', selected);
      el.setAttribute('aria-selected', String(selected));
      el.setAttribute('tabindex', selected ? '0' : '-1');
    });
    document.getElementById('signinForm').style.display = tab === 'signin' ? '' : 'none';
    document.getElementById('registerForm').style.display = tab === 'register' ? '' : 'none';
    document.getElementById('authSwitchText').innerHTML =
      tab === 'signin'
        ? 'No account? <a id="authSwitchLink">Create one</a>'
        : 'Already have an account? <a id="authSwitchLink">Sign in</a>';
    document.getElementById('authSwitchLink').addEventListener('click', () => {
      switchTab(tab === 'signin' ? 'register' : 'signin');
    });
    document.getElementById('authSuccess').style.display = 'none';
  }

  document.querySelectorAll('.authTab').forEach((tab) => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
  document.getElementById('authSwitchLink').addEventListener('click', () => {
    switchTab('register');
  });

  // ── Register ───────────────────────────────────────────
  document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('registerError');
    errEl.style.display = 'none';
    try {
      const data = await api('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          email: document.getElementById('registerEmail').value.trim(),
          display_name: document.getElementById('registerName').value.trim(),
          password: document.getElementById('registerPassword').value,
        }),
      });
      document.getElementById('loginEmail').value = data.email || document.getElementById('registerEmail').value.trim();
      document.getElementById('authSuccess').style.display = 'block';
      showToast('Account created! You can now sign in.', 'success');
      switchTab('signin');
    } catch (err) {
      errEl.textContent = err.detail || 'Registration failed';
      errEl.style.display = 'block';
    }
  });

  // ── Sign In ─────────────────────────────────────────────
  document.getElementById('signinForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('loginError');
    errEl.style.display = 'none';
    try {
      const data = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: document.getElementById('loginEmail').value.trim(),
          password: document.getElementById('loginPassword').value,
        }),
      });
      state.accessToken = data.access_token;
      const me = await api('/auth/me');
      const groups = me.groups || [];

      if (groups.length > 0) {
        setState({
          accessToken: data.access_token,
          currentUser: me,
          groups,
          currentGroupId: groups[0].group_id,
          currentRole: groups[0].role,
        });
        navigate('/ask');
      } else {
        setState({
          accessToken: data.access_token,
          currentUser: me,
          groups: [],
          currentGroupId: '',
          currentRole: '',
        });
        navigate('/onboarding');
      }
    } catch (err) {
      errEl.textContent = err.detail || 'Login failed';
      errEl.style.display = 'block';
    }
  });
}
