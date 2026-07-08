import { api } from '../api.js';
import { esc } from '../util/esc.js';
import { showToast } from '../util/toast.js';

const STATUS_LABELS = { pending: '待处理', in_progress: '进行中', done: '已完成', cancelled: '已取消' };
const STATUS_NEXT = {
  pending: { label: '开始处理', target: 'in_progress' },
  in_progress: { label: '标记完成', target: 'done' },
  done: { label: '重新打开', target: 'pending' },
  cancelled: { label: '重新打开', target: 'pending' },
};
const STATUS_COLOR = {
  pending: 'var(--brand-amber)',
  in_progress: 'var(--brand-blue)',
  done: 'var(--ok-strong)',
  cancelled: '#9ca3af',
};

/** Pure render function for a single task card. */
export function taskCard(task, gid, onStatusChange, sourceLabels) {
  const srcLabel = sourceLabels?.[task.source_type] || task.source_type || '未知';
  const color = STATUS_COLOR[task.status] || '#999';
  const next = STATUS_NEXT[task.status];
  const isCancelled = task.status === 'cancelled';

  return `
    <div class="taskCard${isCancelled ? ' cancelled' : ''}"
         data-task-id="${task.id}"
         data-status="${task.status}"
         data-source-type="${task.source_type}"
         data-source-id="${task.source_id}">
      <div class="taskBar" style="background:${color}"></div>
      <div class="taskBody">
        <div class="taskHeader">
          <span class="taskTitle">${esc(task.title)}</span>
          <span class="taskStatus" style="background:${color}20;color:${color}">${STATUS_LABELS[task.status] || task.status}</span>
        </div>
        ${task.description ? `<p class="taskDesc">${esc(task.description)}</p>` : ''}
        <div class="taskMeta">
          <span class="taskSource">来源：${srcLabel}</span>
          <span class="taskTime">${new Date(task.created_at).toLocaleString()}</span>
        </div>
        <div class="taskActions">
          ${next ? `<button class="taskStatusBtn" data-task-id="${task.id}" data-new-status="${next.target}">${next.label}</button>` : ''}
        </div>
        <div class="taskSourceDetail" style="display:none"></div>
      </div>
    </div>`;
}

/** Bind status-toggle click events on rendered task cards. */
export function bindTaskCardEvents(container, gid, onStatusChange) {
  container.querySelectorAll('.taskStatusBtn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const taskId = btn.dataset.taskId;
      const newStatus = btn.dataset.newStatus;
      const currentStatus = btn.closest('.taskCard')?.dataset.status;
      btn.disabled = true;
      btn.textContent = '...';
      try {
        await api(`/groups/${gid}/tasks/${taskId}`, {
          method: 'PATCH',
          body: JSON.stringify({ status: newStatus }),
        });
        showToast('任务状态已更新');
        if (onStatusChange) await onStatusChange();
      } catch (err) {
        showToast(err.detail || '更新失败', 'error');
        btn.disabled = false;
        btn.textContent = STATUS_NEXT[currentStatus]?.label || '重试';
      }
    });
  });
}
