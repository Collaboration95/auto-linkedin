/* Private exported data is rendered as text, never markup. */
(() => {
  const node = (tag, text) => { const n = document.createElement(tag); if (text != null) n.textContent = text; return n; };
  let current = {}, edits = new Map();
  function render(data) {
    current = data; edits = new Map();
    const pending = sessionStorage.getItem('answer-change-id');
    document.getElementById('answer-state').textContent = pending && data.answer_import_ids?.includes(pending) ? 'Persisted after import and refresh.' : pending ? 'Changes exported; not yet persisted. Import the downloaded file, then refresh.' : 'Edits are pending until imported and refreshed.';
    const list = document.getElementById('questions');
    list.replaceChildren();
    for (const q of data.questions || []) {
      const card = node('article'); card.className = 'question-card'; card.id = q.id;
      card.append(node('h3', q.text), node('p', q.status === 'resolved' ? 'Persisted answer' : 'Needs an answer'));
      if (q.options?.length) card.append(node('p', `Options: ${q.options.join(' · ')}`));
      card.append(node('p', `${q.unlock_count || 0} application(s) unlock when this answer is resolved.`));
      const label = node('label', 'Reviewed answer'); label.className = 'answer-editor';
      let input;
      if (q.field_type === 'select' || q.field_type === 'boolean') {
        input = node('select'); const empty = node('option', 'Choose an answer'); empty.value = ''; input.append(empty);
        for (const value of q.field_type === 'boolean' ? [true, false] : q.options || []) { const opt = node('option', String(value)); opt.value = String(value); input.append(opt); }
      } else { input = node('input'); input.type = q.field_type === 'number' ? 'number' : 'text'; if (input.type === 'number') input.step = 'any'; }
      input.value = q.saved_value == null ? '' : String(q.saved_value); input.setAttribute('aria-label', q.text);
      label.append(input); card.append(label);
      const scope = node('p', `Scope: ${Object.entries(q.scope || {}).map(([k,v]) => `${k}: ${v}`).join(' · ') || 'General'}${q.units ? ' · ' + q.units : ''}. Review valid for 30 days.`); card.append(scope);
      input.addEventListener('change', () => {
        let value = input.value;
        if (q.field_type === 'number') value = value === '' ? null : Number(value);
        if (q.field_type === 'boolean') value = value === '' ? null : value === 'true';
        edits.set(q.id, { question_id: q.id, question_version: q.question_version, value, scope: q.scope || {}, review_due_at: new Date(Date.now() + 30 * 86400000).toISOString() });
        document.getElementById('answer-state').textContent = `${edits.size} pending edit(s). Export, import once, then refresh.`;
      });
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
    const attention = document.getElementById('attention-items'); attention.replaceChildren();
    const unresolved = (data.questions || []).filter(q => q.status !== 'resolved').length;
    const review = node('button', `${unresolved} unresolved question(s)`); review.type = 'button'; review.addEventListener('click', () => select('questions-panel')); attention.append(review);
    for (const id of data.attention?.uncertain || []) {
      const app = data.applications.find(a => a.id === id), a = node('a', `Check uncertain submission: ${app?.company || id}`); a.href = '#app-' + id; a.addEventListener('click', () => select('history-panel')); attention.append(a);
    }
    for (const fact of data.attention?.outdated_facts || []) attention.append(node('p', `Outdated fact requires review: ${fact.answer_id}`));
    document.getElementById('question-count').textContent = (data.questions || []).filter(q => q.status !== 'resolved').length;
  }
  function select(id) {
    for (const b of document.querySelectorAll('[data-panel]')) {
      const active = b.dataset.panel === id; b.setAttribute('aria-selected', String(active)); b.tabIndex = active ? 0 : -1;
      document.getElementById(b.dataset.panel).hidden = !active;
    }
  }
  for (const b of document.querySelectorAll('[data-panel]')) {
    b.addEventListener('click', () => select(b.dataset.panel));
    b.addEventListener('keydown', event => {
      const tabs = [...document.querySelectorAll('[data-panel]')]; let i = tabs.indexOf(b);
      if (event.key === 'ArrowRight') i = (i + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') i = (i + tabs.length - 1) % tabs.length;
      else if (event.key === 'Home') i = 0;
      else if (event.key === 'End') i = tabs.length - 1;
      else return;
      event.preventDefault(); select(tabs[i].dataset.panel); tabs[i].focus();
    });
  }
  select('questions-panel');
  document.getElementById('export-answers').addEventListener('click', () => {
    if (!edits.size) { document.getElementById('answer-state').textContent = 'Change at least one answer before exporting.'; return; }
    const id = 'changes-' + (globalThis.crypto?.randomUUID?.() || Date.now() + '-' + Math.random().toString(36).slice(2));
    const payload = { schema_version: 1, change_id: id, base_revision: current.answer_revision || 0, changes: [...edits.values()] };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
    const a = node('a'); a.href = url; a.download = 'answer-changes.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    sessionStorage.setItem('answer-change-id', id);
    document.getElementById('answer-state').textContent = 'Changes exported; not yet persisted. Run import-answers with the downloaded file, then refresh.';
  });
  window.QuestionInbox = { render, select };
})();
