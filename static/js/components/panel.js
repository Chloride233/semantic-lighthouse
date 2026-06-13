export function panel(title, bodyHtml) {
  return `
    <section class="panel">
      <div class="panelHeader"><h2>${esc(title)}</h2></div>
      ${bodyHtml}
    </section>
  `;
}

export function panelGrid(panels) {
  return `<div class="grid">${panels.join('')}</div>`;
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
