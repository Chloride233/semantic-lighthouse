/** Shared confirm dialog for project workflow stages.
 *  Lifecycle: focus-trap, escape/click-outside close, async confirm,
 *  button disable during action, error display, focus restore.
 */
import { esc } from '../util/esc.js';

export function openProjectDialog(title, message, { needsReason = false, confirmLabel = '确认' } = {}, onConfirm) {
  const prevFocus = document.activeElement;
  const overlay = document.createElement('div');
  overlay.className = 'dialogOverlay';
  overlay.innerHTML = `<div class="dialog" role="dialog"><h2 class="dialogTitle">${esc(title)}</h2>
    <div class="dialogBody"><p>${esc(message)}</p>${needsReason ? '<label class="field"><span>原因（必填）</span><textarea id="dlgReason" rows="2"></textarea></label>' : ''}</div>
    <p class="formError" id="dlgError" style="display:none"></p>
    <div class="dialogActions"><button class="secondary" id="dlgCancel">取消</button><button class="primary" id="dlgConfirm">${esc(confirmLabel)}</button></div></div>`;
  document.body.appendChild(overlay);

  let closed = false;

  function cleanup() {
    if (closed) return;
    closed = true;
    document.removeEventListener('keydown', onKey);
    overlay.remove();
    if (prevFocus && typeof prevFocus.focus === 'function') {
      try { prevFocus.focus(); } catch (_) {}
    }
  }

  function onKey(e) { if (e.key === 'Escape') cleanup(); }

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
