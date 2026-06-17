import { api } from '../api.js';
import { showToast } from './toast.js';

/** Confirm a RAG next_step into a lightweight task.
 *  Returns the created task or null on failure.
 */
export async function confirmTask(gid, title, sourceId) {
  try {
    const task = await api(`/groups/${gid}/tasks`, {
      method: 'POST',
      body: JSON.stringify({
        title,
        source_type: 'rag_run',
        source_id: sourceId || '',
      }),
    });
    return task;
  } catch (err) {
    showToast(err.detail || '任务创建失败', 'error');
    return null;
  }
}

/** Update button to confirmed state. */
export function markConfirmed(btn) {
  btn.textContent = '✓ 已确认';
  btn.disabled = true;
  btn.classList.add('confirmed');
}
