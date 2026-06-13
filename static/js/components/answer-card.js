import { esc } from '../util/esc.js';

/**
 * Render a RAG answer with confidence bar, citations, knowledge gaps, and next steps.
 * @param {object} data — API response from POST /groups/{gid}/rag/answer
 * @returns {string} HTML
 */
export function answerCard(data) {
  const level = data.confidence || 'medium';
  const levelCap = level.charAt(0).toUpperCase() + level.slice(1);
  const pct = confidencePct(level, data.confidence_score);
  const gaps = data.knowledge_gaps || [];
  const next = data.next_steps || [];
  const citations = data.citations || [];

  return `
    <div class="answerCard">
      <div class="confidenceBar">
        <div class="confidenceBar-track">
          <div class="confidenceBar-fill ${level}" style="width:${pct}%"></div>
        </div>
        <span class="confidenceBar-label ${level}">${levelCap} confidence${data.confidence_score != null ? ' (' + data.confidence_score + ')' : ''}</span>
      </div>

      <div class="answerCard-text">${esc(data.answer)}</div>

      ${citations.length ? `
        <div class="citationList">
          <div class="citationList-title">📎 Citations (${citations.length})</div>
          ${citations.map((c, i) => `
            <div class="citationCard">
              <div class="citationCard-header">
                <span class="citationCard-index">[${i + 1}]</span>
                <span class="citationCard-title">${esc(c.title || 'Untitled')}</span>
                ${c.score != null ? `<span class="citationCard-score">score ${c.score.toFixed(2)}</span>` : ''}
              </div>
              ${c.snippet ? `<p class="citationCard-snippet">${esc(c.snippet)}</p>` : ''}
            </div>
          `).join('')}
        </div>
      ` : ''}

      ${gaps.length ? `
        <div class="answerGaps">
          <strong>⚠️ Knowledge Gaps</strong>
          <ul>${gaps.map((g) => `<li>${esc(g)}</li>`).join('')}</ul>
        </div>
      ` : ''}

      ${next.length ? `
        <div class="answerNext">
          <strong>💡 Next Steps</strong>
          <ul>${next.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>
        </div>
      ` : ''}
    </div>
  `;
}

const CONFIDENCE_MAP = { high: 85, medium: 60, low: 30 };

function confidencePct(level, score) {
  if (typeof score === 'number' && !isNaN(score)) return Math.round(score * 100);
  return CONFIDENCE_MAP[level] ?? 60;
}
