const STATUS_LABELS = {
  ready: '可检索',
  uploaded: '已上传',
  processing: '处理中',
  failed: '失败',
  archived: '已归档',
  pending: '待处理',
  running: '运行中',
  completed: '已完成',
  owner: '所有者',
  admin: '管理员',
  member: '成员',
};

const CONFIDENCE_LABELS = {
  high: '高可信',
  medium: '中等可信',
  low: '低可信',
  unknown: '未知',
};

export function statusBadge(status) {
  const cls = {
    ready: 'badgeOk', uploaded: 'badgeInfo', processing: 'badgeWarn',
    failed: 'badgeErr', archived: 'badgeMuted',
    pending: 'badgeInfo', running: 'badgeWarn', completed: 'badgeOk',
    owner: 'badgeOk', admin: 'badgeInfo', member: 'badgeMuted',
  };
  return `<span class="badge ${cls[status] || ''}">${esc(STATUS_LABELS[status] || status)}</span>`;
}

export function confidenceBadge(level) {
  const cls = { high: 'badgeOk', medium: 'badgeWarn', low: 'badgeErr', unknown: 'badgeMuted' };
  const label = CONFIDENCE_LABELS[level] || CONFIDENCE_LABELS.unknown;
  return `<span class="badge ${cls[level] || cls.unknown}">${esc(label)}</span>`;
}

export function confidenceLabel(level) {
  return CONFIDENCE_LABELS[level] || CONFIDENCE_LABELS.unknown;
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
