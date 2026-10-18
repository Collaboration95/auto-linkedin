/* Browser-native local fixture adapter. No employer or submit capability. */
(() => {
  const normalized = value => value.normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();
  const hash = async file => [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))].map(b => b.toString(16).padStart(2, '0')).join('');
  async function fill(root, plan) {
    if (!['file:', 'http:', 'https:'].includes(location.protocol) || (location.protocol !== 'file:' && !['127.0.0.1', 'localhost', '[::1]'].includes(location.hostname))) throw Error('unsupported_live_capability');
    if (root.dataset.jobUrl !== plan.jobUrl) throw Error('observed_job_mismatch');
    const controls = [...root.querySelectorAll('input,select')];
    if (controls.length !== plan.fields.length) throw Error('page_changed');
    const bindings = plan.fields.map(field => {
      const matches = controls.filter(input => [...input.labels || []].some(label => normalized(label.textContent) === normalized(field.label)));
      if (matches.length !== 1) throw Error('page_changed');
      const input = matches[0], kind = input.tagName === 'SELECT' ? 'select' : input.type === 'file' ? 'upload' : input.type;
      if (kind !== field.type) throw Error('page_changed');
      if (kind === 'select' && JSON.stringify([...input.options].map(o => o.value)) !== JSON.stringify(field.options)) throw Error('page_changed');
      if (kind === 'select' && !field.options.includes(field.value)) throw Error('unknown_answer');
      if (kind === 'upload' && (!(field.file instanceof File) || !field.sha256)) throw Error('resume_stale');
      return { field, input };
    });
    if (root.querySelector('[data-history]').textContent !== plan.history) throw Error('outdated_fact');
    for (const { field, input } of bindings) {
      if (field.type === 'upload') {
        if (await hash(field.file) !== field.sha256) throw Error('resume_stale');
        const transfer = new DataTransfer(); transfer.items.add(field.file); input.files = transfer.files;
      } else input.value = field.value;
      input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
    }
    for (const { field, input } of bindings) {
      if (field.type === 'upload' ? input.files.length !== 1 || await hash(input.files[0]) !== field.sha256 : input.value !== field.value) throw Error('page_changed');
    }
    return { verified: true, fields: bindings.length, uploadVerified: true, historyVerified: true };
  }
  window.LocalForm = { fill, hash };
})();
