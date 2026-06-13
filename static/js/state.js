/**
 * Minimal reactive global store.
 * Subscribers are re-notified when any tracked key changes.
 */
const _listeners = [];

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

export function setState(update) {
  Object.assign(state, update);
  _notify();
}

export function clearAuth() {
  setState({ accessToken: '', currentUser: null, groups: [], currentGroupId: '', currentRole: '' });
}
