import { esc } from '../util/esc.js';
import { confidenceLabel } from './badge.js';
import { findEntityForCitation } from '../util/ontology-links.js';

const VALID_LEVELS = new Set(['high', 'medium', 'low']);

const CONFIDENCE_PCT = { high: 85, medium: 60, low: 30, unknown: 0 };

export function answerCard(data, opts = {}) {
  const { showConfirm = false, groupId = '', hideNextSteps = false, ontologyIndex = null } = opts;
  const taskBoardLink = showConfirm && groupId
    ? `<a class="answerNextLink" href="#/groups/${groupId}/tasks">查看任务 →</a>`
    : '';
  const rawLevel = data.confidence;
  const level = (typeof rawLevel === 'string' && VALID_LEVELS.has(rawLevel)) ? rawLevel : 'unknown';
  const pct = CONFIDENCE_PCT[level];
  const gaps = data.knowledge_gaps || [];
  const next = hideNextSteps ? [] : (data.next_steps || []);
  const citations = data.citations || [];
  const answerText = data.answer || '暂未生成回答，请检查检索结果或尝试重试。';

  return `
    <div class="answerCard">
      <div class="confidenceBar">
        <div class="confidenceBar-track">
          <div class="confidenceBar-fill ${level}" style="width:${pct}%"></div>
        </div>
        <span class="confidenceBar-label ${level}">
          ${esc(confidenceLabel(level))}
        </span>
      </div>

      ${data.confidence_reason ? `
        <div class="confidenceReason">
          <span class="confidenceReason-icon">?</span>
          <span>${esc(data.confidence_reason)}</span>
        </div>
      ` : ''}

      ${renderEvidenceQuality(data.evidence_quality)}

      <div class="answerCard-text">${esc(answerText)}</div>

      ${gaps.length ? `
        <div class="answerGaps">
          <strong>知识缺口</strong>
          <ul>${gaps.map((g) => `<li>${esc(g)}</li>`).join('')}</ul>
        </div>
      ` : ''}

      ${next.length ? `
        <div class="answerNext">
          <strong>下一步建议</strong>
          <ul>${next.map((s, i) => `
            <li>
              <span>${esc(s)}</span>
              ${showConfirm ? `<button class="confirmTaskBtn" data-index="${i}" data-title="${esc(s).replace(/"/g, '&quot;')}">✓ 确认任务</button>` : ''}
            </li>
          `).join('')}</ul>
          ${taskBoardLink}
        </div>
      ` : ''}

      ${citations.length ? `
        <div class="citationList">
          <div class="citationList-title">引用来源（${citations.length}）</div>
          ${citations.map((c, i) => {
            const onto = findEntityForCitation(c, ontologyIndex);
            const ontoBadge = onto && groupId
              ? `<a class="citationOntoLink" href="#/groups/${groupId}/ontology?entity_id=${onto.id}" title="Ontology: ${esc(onto.title)}">🔗 ${esc(trunc(onto.title, 20))}</a>`
              : '';
            return `<div class="citationCard">
              <div class="citationCard-header">
                <span class="citationCard-index">[${i + 1}]</span>
                <span class="citationCard-title">${esc(c.title || '未命名文档')}</span>
                ${typeof c.score === 'number' && c.score > 0 ? `<span class="citationCard-score">匹配分 ${c.score.toFixed(2)}</span>` : ''}
                ${ontoBadge}
              </div>
              ${c.snippet ? `<p class="citationCard-snippet">${esc(c.snippet)}</p>` : ''}
              ${c.match_reason ? `<p class="citationMatchReason">${esc(c.match_reason)}</p>` : ''}
            </div>`;
          }).join('')}
        </div>
      ` : ''}
    </div>
  `;
}

function renderEvidenceQuality(eq) {
  if (!eq) return '';
  const labels = [
    { key: 'retrieval_coverage', label: '检索覆盖', values: { full: '全面', partial: '部分', weak: '弱', none: '无' } },
    { key: 'source_maturity', label: '来源成熟度', values: { strong: '强', medium: '中', weak: '弱', unknown: '未知' } },
    { key: 'citation_diversity', label: '引用多样性', values: { high: '高', medium: '中', low: '低', none: '无' } },
    { key: 'score_distribution', label: '匹配分分布', values: { strong: '强', medium: '中', weak: '弱', unknown: '未知' } },
  ];
  const tags = labels.map(({ key, label, values }) => {
    const val = eq[key] || 'unknown';
    return `<span class="eqTag eqTag-${val}">${esc(label)}：${esc(values[val] || val)}</span>`;
  }).join('');
  return `
    <div class="evidenceQuality">
      <div class="evidenceQuality-tags">${tags}</div>
      ${eq.summary ? `<p class="evidenceQuality-summary">${esc(eq.summary)}</p>` : ''}
    </div>
  `;
}

function trunc(s, n) { return s && s.length > n ? s.slice(0, n) + '...' : s; }
