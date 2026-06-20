/** Shared confirm dialog for project workflow stages.
 *  Lifecycle: focus-trap, escape/click-outside close, async confirm,
 *  button disable during action, error display, focus restore.
 *
 *  Accessibility: aria-modal, aria-labelledby, tab trap,
 *  Escape/overlay/cancel all clean up listeners.
 */
import { esc } from '../util/esc.js';

const DIALOG_TITLE_ID = 'dlgTitle';

export function openProjectDialog(title, message, { needsReason = false, confirmLabel = '确认' } = {}, onConfirm) {
  const prevFocus = document.activeElement;
  const overlay = document.createElement('div');
  overlay.className = 'dialogOverlay';
  overlay.setAttribute('role', 'presentation');
  overlay.innerHTML = `<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="${DIALOG_TITLE_ID}">
    <h2 class="dialogTitle" id="${DIALOG_TITLE_ID}">${esc(title)}</h2>
    <div class="dialogBody"><p>${esc(message)}</p>${needsReason ? '<label class="field"><span>原因（必填）</span><textarea id="dlgReason" rows="2" required></textarea></label>' : ''}</div>
    <p class="formError" id="dlgError" style="display:none" role="alert"></p>
    <div class="dialogActions"><button class="secondary" id="dlgCancel" type="button">取消</button><button class="primary" id="dlgConfirm" type="button">${esc(confirmLabel)}</button></div></div>`;
  document.body.appendChild(overlay);

  let closed = false;

  function getFocusable() {
    const dlg = overlay.querySelector('.dialog');
    if (!dlg) return [];
    return [...dlg.querySelectorAll(
      'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )];
  }

  function cleanup() {
    if (closed) return;
    closed = true;
    document.removeEventListener('keydown', onKey);
    overlay.remove();
    if (prevFocus && typeof prevFocus.focus === 'function') {
      try { prevFocus.focus(); } catch (_) { /* ignore detached node */ }
    }
  }

  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); cleanup(); return; }
    if (e.key === 'Tab') {
      const focusable = getFocusable();
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
  }

  document.getElementById('dlgCancel').addEventListener('click', cleanup);
  overlay.addEventListener('click', e => { if (e.target === overlay) cleanup(); });
  document.addEventListener('keydown', onKey);

  // Focus first input or confirm button
  const firstInput = document.getElementById('dlgReason') || document.getElementById('dlgConfirm');
  if (firstInput) firstInput.focus();

  const confirmBtn = document.getElementById('dlgConfirm');
  const cancelBtn = document.getElementById('dlgCancel');
  const errEl = document.getElementById('dlgError');

  confirmBtn.addEventListener('click', async () => {
    const reason = needsReason ? document.getElementById('dlgReason')?.value.trim() : '';
    if (needsReason && !reason) {
      errEl.textContent = '原因不能为空';
      errEl.style.display = 'block';
      document.getElementById('dlgReason')?.focus();
      return;
    }
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;
    try {
      await onConfirm(reason || undefined);
      cleanup();
    } catch (err) {
      errEl.textContent = err.humanMessage || err.message || '操作失败';
      errEl.style.display = 'block';
    } finally {
      confirmBtn.disabled = false;
      cancelBtn.disabled = false;
    }
  });
}
