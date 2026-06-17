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

const ONTOLOGY_STATUS_LABELS = {
  canonical: '权威', reviewed: '已审校', draft: '草稿',
  outdated: '过时', stub: '存根',
};
const SOURCE_LABELS_MAP = {
  'official-doc': '官方文档', 'market-research': '市场调研',
  'public-article': '公开文章', 'case-report': '案例复盘',
  'personal-analysis': '个人分析',
};

export function ontologyStatusBadge(status) {
  const cls = {
    canonical: 'badgeOk', reviewed: 'badgeInfo', draft: 'badgeWarn',
    outdated: 'badgeMuted', stub: 'badgeMuted',
  };
  const label = ONTOLOGY_STATUS_LABELS[status] || status || '未知';
  return `<span class="badge ${cls[status] || 'badgeMuted'}">${esc(label)}</span>`;
}

export function sourceBadge(source) {
  const cls = {
    'official-doc': 'badgeOk', 'market-research': 'badgeInfo',
    'case-report': 'badgeInfo', 'public-article': 'badgeWarn',
    'personal-analysis': 'badgeMuted',
  };
  const label = SOURCE_LABELS_MAP[source] || source || '未知';
  return `<span class="badge ${cls[source] || 'badgeMuted'}">${esc(label)}</span>`;
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
