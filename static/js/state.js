/**
 * Minimal reactive global store.
 * Subscribers are re-notified when any tracked key changes.
 * Group context is persisted to localStorage so the active workspace
 * survives reloads and navigation.
 */
const _listeners = [];
const STORAGE_KEY = 'sl_state';

export const state = {
  accessToken: '',
  currentUser: null,
  groups: [],
  currentGroupId: '',
  currentRole: '',
};

export function onStateChange(fn) {
  _listeners.push(fn);
}

function _notify() {
  for (const fn of _listeners) fn(state);
}

function _persist() {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ currentGroupId: state.currentGroupId, currentRole: state.currentRole }),
    );
  } catch (_) {
    // ignore private-mode / disabled storage
  }
}

export function setState(update) {
  Object.assign(state, update);
  _persist();
  _notify();
}

export function clearAuth() {
  setState({ accessToken: '', currentUser: null, groups: [], currentGroupId: '', currentRole: '' });
  try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
}

/**
 * Restore the last active group from localStorage if it is still valid.
 * Call after fetching the user's group list.
 */
export function restoreGroupContext(groups) {
  if (!Array.isArray(groups) || groups.length === 0) return;
  let stored = null;
  try {
    stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  } catch (_) {
    stored = {};
  }
  const match = groups.find((g) => g.group_id === stored?.currentGroupId);
  if (match) {
    setState({
      groups,
      currentGroupId: match.group_id,
      currentRole: match.role || '',
    });
  } else {
    setState({
      groups,
      currentGroupId: groups[0].group_id,
      currentRole: groups[0].role || '',
    });
  }
}

export function currentGroup() {
  return state.groups.find((g) => g.group_id === state.currentGroupId) || null;
}
