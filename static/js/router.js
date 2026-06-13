const _routes = [];
let _currentCleanup = null;

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export function route(pattern, renderFn) {
  _routes.push({ pattern, renderFn });
}

export function navigate(hash) {
  location.hash = hash;
}

function _match() {
  const raw = location.hash.replace('#', '') || '/login';
  for (const { pattern, renderFn } of _routes) {
    const keys = [];
    const regexStr = pattern.replace(/:(\w+)/g, (_, key) => {
      keys.push(key);
      return '([^/]+)';
    });
    const match = raw.match(new RegExp(`^${regexStr}$`));
    if (match) {
      const params = {};
      keys.forEach((k, i) => (params[k] = match[i + 1]));
      return { renderFn, params };
    }
  }
  return { renderFn: _routes.find((r) => r.pattern === '/login')?.renderFn, params: {} };
}

export function initRouter(outletId) {
  const outlet = document.getElementById(outletId);
  if (!outlet) return;

  async function _render() {
    if (_currentCleanup && typeof _currentCleanup === 'function') {
      _currentCleanup();
    }
    const { renderFn, params } = _match();
    if (renderFn) {
      outlet.innerHTML = '<div class="loading">Loading...</div>';
      try {
        _currentCleanup = await renderFn(outlet, params);
      } catch (err) {
        if (err.status === 401) {
          navigate('/login');
          return;
        }
        outlet.innerHTML = `<div class="error"><p>${esc(err.message)}</p><button onclick="location.reload()">Reload</button></div>`;
      }
    }
  }

  window.addEventListener('hashchange', _render);
  _render();
}
