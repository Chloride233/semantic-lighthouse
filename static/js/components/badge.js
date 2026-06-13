export function statusBadge(status) {
  const cls = {
    ready: 'badgeOk', uploaded: 'badgeInfo', processing: 'badgeWarn',
    failed: 'badgeErr', archived: 'badgeMuted',
    pending: 'badgeInfo', running: 'badgeWarn', completed: 'badgeOk',
    owner: 'badgeOk', admin: 'badgeInfo', member: 'badgeMuted',
  };
  return `<span class="badge ${cls[status] || ''}">${esc(status)}</span>`;
}

export function confidenceBadge(level) {
  const cls = { high: 'badgeOk', medium: 'badgeWarn', low: 'badgeErr' };
  return `<span class="badge ${cls[level] || ''}">${esc(level)}</span>`;
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
