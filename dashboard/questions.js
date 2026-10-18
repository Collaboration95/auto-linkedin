/* Private exported data is rendered as text, never markup. */
(() => {
  const node = (tag, text) => { const n = document.createElement(tag); if (text != null) n.textContent = text; return n; };
  function render(data) {
    const list = document.getElementById('questions');
    list.replaceChildren();
    for (const q of data.questions || []) {
      const card = node('article'); card.className = 'question-card'; card.id = q.id;
      card.append(node('h3', q.text), node('p', q.status === 'resolved' ? 'Persisted answer' : 'Needs an answer'));
      if (q.options?.length) card.append(node('p', `Options: ${q.options.join(' · ')}`));
      const affected = node('ul');
      for (const o of q.occurrences || []) {
        const row = node('li'); const a = node('a', `${o.company}: ${o.text}`); a.href = '#app-' + o.application_id;
        a.addEventListener('click', () => select('history-panel'));
        const record = node('a', 'Saved record'); record.href = o.record_url;
        const job = node('a', 'Original listing');
        try { const u = new URL(o.listing_url); if (['http:', 'https:'].includes(u.protocol)) job.href = u.href; } catch {}
        row.append(a, ' · ', record, ' · ', job); affected.append(row);
      }
      card.append(affected); list.append(card);
    }
    if (!list.children.length) list.append(node('p', 'No questions yet.'));
    document.getElementById('question-count').textContent = (data.questions || []).filter(q => q.status !== 'resolved').length;
  }
  function select(id) {
    for (const b of document.querySelectorAll('[data-panel]')) {
      const active = b.dataset.panel === id; b.setAttribute('aria-selected', String(active));
      document.getElementById(b.dataset.panel).hidden = !active;
    }
  }
  for (const b of document.querySelectorAll('[data-panel]')) b.addEventListener('click', () => select(b.dataset.panel));
  window.QuestionInbox = { render, select };
})();
