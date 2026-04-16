// Tool detail page with runner. Dynamic form from input_schema + output rendering per output_type.

(function () {
  let tool = null;
  let lastRun = null;
  let recentRuns = [];

  function init() {
    Forge.renderLayout('catalog');
    Forge.renderFooter();
    const slug = Forge.getQueryParam('slug');
    const id = Forge.getQueryParam('id');
    if (!slug && !id) return showError('Missing tool identifier.');
    load(slug, id);
  }

  async function load(slug, id) {
    try {
      tool = slug ? await ForgeApi.getToolBySlug(slug) : await ForgeApi.getTool(id);
      if (!tool || tool.error) return showError(tool?.error || 'Tool not found.');
      document.title = `${tool.name} — Forge`;
      Forge.qs('#tool-loading').remove();
      Forge.qs('#tool-content').classList.remove('hidden');
      renderInfo();
      renderRunner();
      loadRecentRuns();
    } catch (err) {
      showError(err.message || 'Failed to load tool');
    }
  }

  function showError(msg) {
    const loading = Forge.qs('#tool-loading');
    if (loading) loading.remove();
    Forge.qs('#tool-content').classList.add('hidden');
    const el = Forge.qs('#tool-error');
    el.classList.remove('hidden');
    el.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">⚠</div>
      <h3>${Forge.escapeHtml(msg)}</h3>
      <p><a class="btn btn-secondary mt-3" href="/index.html">Back to catalog</a></p>
    </div>`;
  }

  function renderInfo() {
    const info = Forge.qs('#tool-info');
    const tier = Forge.computeTrustTier(tool);
    const trust = Forge.TRUST_INFO[tier] || Forge.TRUST_INFO.unverified;
    const tags = (tool.tags || '').split(',').map((t) => t.trim()).filter(Boolean);

    info.innerHTML = `
      <div class="tool-info">
        <h1>${Forge.escapeHtml(tool.name)}</h1>
        <p class="tool-info-tagline">${Forge.escapeHtml(tool.tagline || '')}</p>
        <div class="tool-info-meta">
          ${Forge.categoryBadge(tool.category)}
          ${Forge.trustTierBadge(tier)}
          ${Forge.outputTypeBadge(tool.output_type)}
          ${tags.map((t) => `<span class="mono-tag">#${Forge.escapeHtml(t)}</span>`).join('')}
        </div>
        <div class="trust-card ${tier}">
          <div class="trust-card-title"><span aria-hidden="true">${trust.icon}</span> ${Forge.escapeHtml(trust.label)}</div>
          <div>${Forge.escapeHtml(trust.desc)}</div>
        </div>
      </div>
    `;

    info.appendChild(buildScoresAccordion());
    info.appendChild(buildDescriptionBlock());
    info.appendChild(buildVersionHistoryAccordion());
    info.appendChild(buildStatsRow());
    info.appendChild(buildToolActions());
    info.appendChild(buildAuthorRow());
  }

  function buildScoresAccordion() {
    const rows = [
      { label: 'Reliability', score: tool.reliability_score, note: reliabilityLabel(tool.reliability_score) },
      { label: 'Safety', score: tool.safety_score, note: safetyLabel(tool.safety_score) },
      { label: 'Complexity', score: tool.complexity_score, note: complexityLabel(tool.complexity_score) },
      { label: 'Verified', score: tool.verified_score, note: verifiedLabel(tool.verified_score) },
    ];
    const el = Forge.h(`
      <div class="accordion" id="scores-accordion">
        <div class="accordion-header" role="button" tabindex="0" aria-expanded="false">
          <span>How was this scored?</span>
          <span class="accordion-icon" aria-hidden="true">▾</span>
        </div>
        <div class="accordion-body">
          <div class="text-secondary mb-3">Governance scores from the agent review pipeline.</div>
          ${rows.map((r) => {
            const pct = Math.max(0, Math.min(100, Number(r.score) || 0));
            const cls = pct >= 70 ? 'good' : pct >= 40 ? 'mid' : 'low';
            return `
              <div class="score-row">
                <div class="score-label">${r.label}</div>
                <div class="score-bar"><div class="score-bar-fill ${cls}" style="width:${pct}%"></div></div>
                <div class="score-value">${pct}</div>
                <div class="score-note">${Forge.escapeHtml(r.note || '')}</div>
              </div>
            `;
          }).join('')}
          <div class="score-row" style="margin-top: 12px; border-top: 1px solid var(--border); padding-top: 12px;">
            <div class="score-label">Data Sensitivity</div>
            <div style="grid-column: 2 / -1;"><span class="mono-tag">${Forge.escapeHtml(tool.data_sensitivity || 'internal')}</span></div>
          </div>
        </div>
      </div>
    `);
    const header = el.querySelector('.accordion-header');
    const toggle = () => {
      el.classList.toggle('open');
      header.setAttribute('aria-expanded', el.classList.contains('open'));
    };
    header.addEventListener('click', toggle);
    header.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    return el;
  }

  function reliabilityLabel(s) {
    s = Number(s) || 0;
    if (s >= 90) return 'Deterministic';
    if (s >= 70) return 'Highly Reliable';
    if (s >= 50) return 'Mostly Reliable';
    if (s >= 30) return 'Variable';
    if (s >= 10) return 'Highly Variable';
    return 'Unpredictable';
  }
  function safetyLabel(s) {
    s = Number(s) || 0;
    if (s >= 90) return 'Safe';
    if (s >= 70) return 'Low Risk';
    if (s >= 50) return 'Medium Risk';
    if (s >= 30) return 'High Risk';
    return 'Critical';
  }
  function complexityLabel(s) {
    s = Number(s) || 0;
    if (s >= 80) return 'Simple';
    if (s >= 60) return 'Moderate';
    if (s >= 40) return 'Complex';
    return 'Expert Only';
  }
  function verifiedLabel(s) {
    s = Number(s) || 0;
    if (s >= 90) return 'Validated on real data';
    if (s >= 75) return 'Human-validated';
    if (s >= 50) return 'Agent-verified';
    return 'Unvalidated';
  }

  function buildDescriptionBlock() {
    const raw = tool.description || '';
    const html = (window.marked && typeof window.marked.parse === 'function')
      ? window.marked.parse(raw)
      : `<p>${Forge.escapeHtml(raw).replace(/\n/g, '<br>')}</p>`;
    return Forge.h(`<div class="section">
      <div class="section-title">About this tool</div>
      <div class="output-markdown" style="font-size:14px; line-height:1.6;">${html}</div>
    </div>`);
  }

  function buildVersionHistoryAccordion() {
    const versions = tool.versions || [];
    const el = Forge.h(`
      <div class="accordion">
        <div class="accordion-header" role="button" tabindex="0" aria-expanded="false">
          <span>Version history ${versions.length ? `(${versions.length})` : ''}</span>
          <span class="accordion-icon" aria-hidden="true">▾</span>
        </div>
        <div class="accordion-body">
          ${versions.length === 0 ? `<div class="text-secondary">Version 1 — initial release</div>` : versions.map((v) => `
            <div class="version-row">
              <div><span class="version-number">v${Forge.escapeHtml(String(v.version))}</span> — ${Forge.escapeHtml(v.change_summary || 'No summary')}</div>
              <div class="text-secondary text-sm">${Forge.formatDate(v.created_at)}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `);
    const header = el.querySelector('.accordion-header');
    const toggle = () => { el.classList.toggle('open'); header.setAttribute('aria-expanded', el.classList.contains('open')); };
    header.addEventListener('click', toggle);
    header.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    return el;
  }

  function buildStatsRow() {
    const uniqueUsers = Number(tool.unique_users || 0);
    return Forge.h(`
      <div class="stats-row">
        <span>↻ ${Forge.formatNumber(tool.run_count || 0)} runs</span>
        ${tool.avg_rating ? `<span>★ ${Number(tool.avg_rating).toFixed(1)} rating</span>` : ''}
        ${uniqueUsers > 0 ? `<span>👤 ${Forge.formatNumber(uniqueUsers)} users</span>` : ''}
        ${tool.last_run_at ? `<span>Last run: ${Forge.formatRelative(tool.last_run_at)}</span>` : ''}
      </div>
    `);
  }

  function buildToolActions() {
    const el = Forge.h(`
      <div class="tool-actions mb-4">
        <button class="btn btn-secondary btn-sm" id="fork-btn">Fork This Tool</button>
        <button class="btn btn-secondary btn-sm" id="instructions-btn">Usage Instructions</button>
        <button class="btn btn-ghost btn-sm" id="share-btn">Copy Shareable Link</button>
      </div>
    `);
    el.querySelector('#fork-btn').addEventListener('click', () => {
      window.location.href = `/submit.html?fork=${encodeURIComponent(tool.id)}`;
    });
    el.querySelector('#instructions-btn').addEventListener('click', openInstructionsModal);
    el.querySelector('#share-btn').addEventListener('click', () => {
      const token = tool.access_token;
      const url = token
        ? `${window.location.origin}/t/${token}`
        : `${window.location.origin}/tool.html?slug=${encodeURIComponent(tool.slug || tool.id)}`;
      Forge.copyToClipboard(url, 'Shareable link copied');
    });
    return el;
  }

  function buildAuthorRow() {
    return Forge.h(`
      <div class="text-secondary text-sm">
        Built by <strong>${Forge.escapeHtml(tool.author_name || 'Unknown')}</strong>
        ${tool.created_at ? ` · ${Forge.formatDate(tool.created_at)}` : ''}
      </div>
    `);
  }

  async function openInstructionsModal() {
    const { body } = Forge.openModal({ title: 'Usage Instructions', width: 720 });
    body.innerHTML = '<div class="spinner lg" style="margin: 40px auto; display: block;"></div>';
    try {
      const res = await ForgeApi.getToolInstructions(tool.id);
      const md = (res && typeof res === 'object') ? (res.markdown || res.content || '') : String(res || '');
      const html = (window.marked && typeof window.marked.parse === 'function')
        ? window.marked.parse(md)
        : `<pre>${Forge.escapeHtml(md)}</pre>`;
      body.innerHTML = `<div class="output-markdown">${html}</div>
        <div class="mt-4 flex flex-gap-2">
          <a class="btn btn-secondary btn-sm" href="${ForgeApi.toolInstructionsPdfUrl(tool.id)}" target="_blank" rel="noopener">Download PDF</a>
          <button class="btn btn-ghost btn-sm" id="copy-md">Copy Markdown</button>
        </div>`;
      body.querySelector('#copy-md').addEventListener('click', () => Forge.copyToClipboard(md, 'Markdown copied'));
    } catch (err) {
      body.innerHTML = `<div class="empty-state"><h3>Could not load instructions</h3><p>${Forge.escapeHtml(err.message)}</p></div>`;
    }
  }

  // ------------------- Runner ---------------------

  function renderRunner() {
    const panel = Forge.qs('#runner-panel');
    const schema = parseInputSchema(tool.input_schema);
    panel.innerHTML = '';
    panel.appendChild(Forge.h(`
      <div class="runner-header">
        <h2 class="runner-title">Run Tool</h2>
        <span class="live-indicator">Active</span>
      </div>
    `));
    const form = buildForm(schema);
    panel.appendChild(form);
    panel.appendChild(buildIdentityRow());
    const runBtn = Forge.h(`<button class="btn btn-primary btn-lg btn-block" id="run-btn">Run Tool</button>`);
    panel.appendChild(runBtn);
    panel.appendChild(Forge.h(`<div class="text-secondary text-sm text-center mt-2" id="run-hint">Usually takes 2–5 seconds</div>`));
    panel.appendChild(Forge.h(`<div id="output-container"></div>`));
    panel.appendChild(buildPreviousRunsAccordion());
    runBtn.addEventListener('click', onRun);
    restoreFromStorage(schema, form);
    updateRunEnabled();
  }

  function parseInputSchema(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    if (typeof raw === 'object') {
      if (Array.isArray(raw.fields)) return raw.fields;
      return Object.entries(raw).map(([name, spec]) => ({ name, ...(typeof spec === 'object' ? spec : { type: 'text' }) }));
    }
    try {
      const parsed = JSON.parse(raw);
      return parseInputSchema(parsed);
    } catch (e) {
      return [];
    }
  }

  function buildForm(schema) {
    const form = document.createElement('form');
    form.id = 'runner-form';
    form.setAttribute('aria-label', 'Tool inputs');
    form.addEventListener('submit', (e) => e.preventDefault());
    form.addEventListener('input', () => { saveInputsToStorage(); updateRunEnabled(); });
    form.addEventListener('change', () => { saveInputsToStorage(); updateRunEnabled(); });

    if (schema.length === 0) {
      form.appendChild(Forge.h(`<div class="text-secondary text-sm mb-3">This tool takes no inputs.</div>`));
      return form;
    }
    schema.forEach((field) => form.appendChild(renderField(field)));
    return form;
  }

  function renderField(field) {
    const type = (field.type || 'text').toLowerCase();
    const name = field.name;
    const label = field.label || name;
    const required = !!field.required;
    const placeholder = field.placeholder || '';
    const help = field.help || field.help_text || '';
    const wrap = document.createElement('div');
    wrap.className = 'form-group';
    wrap.innerHTML = `
      <label class="form-label" for="f-${name}">${Forge.escapeHtml(label)}${required ? '<span class="required" aria-hidden="true">*</span>' : ''}</label>
    `;
    let input;
    if (type === 'textarea') {
      input = Forge.h(`<textarea id="f-${name}" name="${name}" placeholder="${Forge.escapeHtml(placeholder)}" ${required ? 'required aria-required="true"' : ''}></textarea>`);
    } else if (type === 'select') {
      const options = Array.isArray(field.options) ? field.options : [];
      const optsHtml = options.map((opt) => {
        const v = typeof opt === 'object' ? opt.value : opt;
        const l = typeof opt === 'object' ? (opt.label || opt.value) : opt;
        return `<option value="${Forge.escapeHtml(v)}">${Forge.escapeHtml(l)}</option>`;
      }).join('');
      input = Forge.h(`<select id="f-${name}" name="${name}" ${required ? 'required aria-required="true"' : ''}>
        <option value="">Select…</option>${optsHtml}
      </select>`);
    } else if (type === 'checkbox' || type === 'boolean' || type === 'toggle') {
      const row = Forge.h(`<div class="toggle-row">
        <label class="toggle"><input type="checkbox" id="f-${name}" name="${name}"><span class="toggle-slider"></span></label>
        <span class="text-secondary text-sm">${Forge.escapeHtml(placeholder || 'Enable')}</span>
      </div>`);
      wrap.appendChild(row);
      if (help) wrap.appendChild(Forge.h(`<div class="form-help">${Forge.escapeHtml(help)}</div>`));
      return wrap;
    } else if (type === 'number') {
      input = Forge.h(`<input id="f-${name}" name="${name}" type="number" placeholder="${Forge.escapeHtml(placeholder)}" ${field.min != null ? `min="${field.min}"` : ''} ${field.max != null ? `max="${field.max}"` : ''} ${required ? 'required aria-required="true"' : ''}>`);
    } else if (type === 'email') {
      input = Forge.h(`<input id="f-${name}" name="${name}" type="email" placeholder="${Forge.escapeHtml(placeholder)}" ${required ? 'required aria-required="true"' : ''}>`);
    } else {
      input = Forge.h(`<input id="f-${name}" name="${name}" type="text" placeholder="${Forge.escapeHtml(placeholder)}" ${required ? 'required aria-required="true"' : ''}>`);
    }
    wrap.appendChild(input);
    if (help) wrap.appendChild(Forge.h(`<div class="form-help">${Forge.escapeHtml(help)}</div>`));
    return wrap;
  }

  function buildIdentityRow() {
    const { name, email } = Forge.getUser();
    const row = Forge.h(`
      <div class="identity-row">
        <div>
          <label class="form-label" for="user-name">Your name</label>
          <input type="text" id="user-name" value="${Forge.escapeHtml(name)}" placeholder="Full name">
        </div>
        <div>
          <label class="form-label" for="user-email">Your email</label>
          <input type="email" id="user-email" value="${Forge.escapeHtml(email)}" placeholder="you@navan.com">
        </div>
        <div class="save-row">
          <input type="checkbox" id="save-identity" checked>
          <label for="save-identity">Save for next time</label>
        </div>
      </div>
    `);
    return row;
  }

  function getInputValues() {
    const form = Forge.qs('#runner-form');
    const values = {};
    const schema = parseInputSchema(tool.input_schema);
    schema.forEach((field) => {
      const el = form.querySelector(`[name="${CSS.escape(field.name)}"]`);
      if (!el) return;
      const type = (field.type || 'text').toLowerCase();
      if (type === 'checkbox' || type === 'boolean' || type === 'toggle') values[field.name] = el.checked;
      else if (type === 'number') values[field.name] = el.value === '' ? null : Number(el.value);
      else values[field.name] = el.value;
    });
    return values;
  }

  function validateForm() {
    const form = Forge.qs('#runner-form');
    const schema = parseInputSchema(tool.input_schema);
    let ok = true;
    schema.forEach((field) => {
      const el = form.querySelector(`[name="${CSS.escape(field.name)}"]`);
      if (!el) return;
      if (field.required && !el.value && el.type !== 'checkbox') { el.classList.add('invalid'); ok = false; }
      else el.classList.remove('invalid');
    });
    return ok;
  }

  function updateRunEnabled() {
    const btn = Forge.qs('#run-btn');
    if (!btn) return;
    const form = Forge.qs('#runner-form');
    const schema = parseInputSchema(tool.input_schema);
    const ok = schema.every((field) => {
      if (!field.required) return true;
      const el = form.querySelector(`[name="${CSS.escape(field.name)}"]`);
      if (!el) return false;
      if (el.type === 'checkbox') return true;
      return !!el.value;
    });
    btn.disabled = !ok;
  }

  function saveInputsToStorage() {
    const key = `forge_inputs_${tool.slug || tool.id}`;
    try { localStorage.setItem(key, JSON.stringify(getInputValues())); } catch (e) { /* ignore */ }
  }

  function restoreFromStorage(schema, form) {
    const key = `forge_inputs_${tool.slug || tool.id}`;
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return;
      const values = JSON.parse(raw);
      schema.forEach((field) => {
        const el = form.querySelector(`[name="${CSS.escape(field.name)}"]`);
        if (!el || !(field.name in values)) return;
        const type = (field.type || 'text').toLowerCase();
        if (type === 'checkbox' || type === 'boolean' || type === 'toggle') el.checked = !!values[field.name];
        else el.value = values[field.name] ?? '';
      });
    } catch (e) { /* ignore */ }
  }

  async function onRun() {
    if (!validateForm()) {
      Forge.showToast('Please fill in required fields', 'error');
      return;
    }
    const user = {
      name: Forge.qs('#user-name').value.trim(),
      email: Forge.qs('#user-email').value.trim(),
    };
    if (Forge.qs('#save-identity').checked) Forge.setUser(user.name, user.email);
    const btn = Forge.qs('#run-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Running…';
    Forge.qs('#run-hint').textContent = 'Calling Claude — usually 2–5 seconds';
    const inputs = getInputValues();
    try {
      const result = await ForgeApi.runTool(tool.id, inputs, user);
      lastRun = result;
      renderOutput(result);
      Forge.showToast('Run complete', 'success');
      loadRecentRuns();
    } catch (err) {
      renderRunError(err);
      Forge.showToast(err.message || 'Run failed', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = 'Run Tool';
      Forge.qs('#run-hint').textContent = 'Usually takes 2–5 seconds';
    }
  }

  function renderOutput(run) {
    const container = Forge.qs('#output-container');
    container.innerHTML = '';
    const tier = Forge.computeTrustTier(tool);
    if (tier === 'caution') {
      container.appendChild(Forge.h(`<div class="trust-banner caution">⚡ AI-generated. Review before acting on this output.</div>`));
    } else if (tier === 'verified') {
      container.appendChild(Forge.h(`<div class="trust-banner verified">✓ Reviewed output</div>`));
    }
    container.appendChild(formatOutput(run));
    container.appendChild(buildOutputMeta(run));
    container.appendChild(buildOutputActions(run));
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function renderRunError(err) {
    const container = Forge.qs('#output-container');
    container.innerHTML = '';
    container.appendChild(Forge.h(`
      <div class="trust-banner caution">⚠ Run failed: ${Forge.escapeHtml(err.message || 'Unknown error')}</div>
    `));
  }

  function formatOutput(run) {
    const format = (tool.output_format || 'text').toLowerCase();
    const output = run.output_data ?? run.output ?? '';
    const parsed = run.output_parsed;
    if (format === 'email_draft' || format === 'email') return renderEmailOutput(parsed || tryParseJson(output) || { body: output });
    if (format === 'table') return renderTableOutput(parsed || tryParseJson(output));
    if (format === 'json') return renderJsonOutput(parsed || tryParseJson(output) || output);
    if (format === 'markdown') return renderMarkdownOutput(output);
    return Forge.h(`<div class="output-box">${Forge.escapeHtml(String(output))}</div>`);
  }

  function tryParseJson(s) {
    if (s == null) return null;
    if (typeof s === 'object') return s;
    try { return JSON.parse(s); } catch (e) { return null; }
  }

  function renderEmailOutput(data) {
    data = data || {};
    const el = Forge.h(`
      <div class="output-email">
        <div class="email-row"><span class="email-label">To</span><span>${Forge.escapeHtml(data.to || data.recipient || '—')}</span></div>
        <div class="email-row"><span class="email-label">Subject</span><span>${Forge.escapeHtml(data.subject || '—')}</span></div>
        <div class="email-body">${Forge.escapeHtml(data.body || data.content || '')}</div>
      </div>
      <div class="flex flex-gap-2"><button class="btn btn-secondary btn-sm" id="copy-email">Copy as email</button></div>
    `);
    const wrap = document.createElement('div');
    wrap.appendChild(el);
    Array.from(wrap.querySelectorAll('#copy-email')).forEach((b) => {
      b.addEventListener('click', () => {
        const text = `To: ${data.to || ''}\nSubject: ${data.subject || ''}\n\n${data.body || ''}`;
        Forge.copyToClipboard(text, 'Email copied');
      });
    });
    return wrap;
  }

  function renderTableOutput(data) {
    if (!data || !Array.isArray(data) || data.length === 0) {
      return Forge.h(`<div class="output-box">No table rows returned.</div>`);
    }
    const keys = Array.from(new Set(data.flatMap((row) => Object.keys(row || {}))));
    return Forge.h(`<table class="output-table">
      <thead><tr>${keys.map((k) => `<th>${Forge.escapeHtml(k)}</th>`).join('')}</tr></thead>
      <tbody>${data.map((row) => `<tr>${keys.map((k) => `<td>${Forge.escapeHtml(String(row[k] ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody>
    </table>`);
  }

  function renderJsonOutput(data) {
    const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    const el = Forge.h(`<div>
      <div class="output-box mono">${Forge.escapeHtml(text)}</div>
      <button class="btn btn-secondary btn-sm" id="copy-json">Copy JSON</button>
    </div>`);
    el.querySelector('#copy-json').addEventListener('click', () => Forge.copyToClipboard(text, 'JSON copied'));
    return el;
  }

  function renderMarkdownOutput(text) {
    const html = (window.marked && typeof window.marked.parse === 'function')
      ? window.marked.parse(String(text))
      : Forge.escapeHtml(String(text)).replace(/\n/g, '<br>');
    const el = Forge.h(`<div>
      <div class="output-box output-markdown">${html}</div>
      <button class="btn btn-secondary btn-sm" id="copy-md">Copy Markdown</button>
    </div>`);
    el.querySelector('#copy-md').addEventListener('click', () => Forge.copyToClipboard(String(text), 'Markdown copied'));
    return el;
  }

  function buildOutputMeta(run) {
    return Forge.h(`<div class="output-meta">
      <span>Ran in ${Forge.formatDuration(run.run_duration_ms)}</span>
      <span>Cost: ${Forge.formatCost(run.cost_usd)}</span>
      ${run.model_used ? `<span class="mono-tag">${Forge.escapeHtml(run.model_used)}</span>` : ''}
      ${run.tokens_used ? `<span>${Forge.formatNumber(run.tokens_used)} tokens</span>` : ''}
    </div>`);
  }

  function buildOutputActions(run) {
    const wrap = Forge.h(`<div class="output-actions"></div>`);
    const rating = Forge.ratingStars(0, {
      interactive: true,
      onRate: async (r) => {
        try {
          await ForgeApi.rateRun(run.id, r, '');
          Forge.showToast('Thanks for rating', 'success');
          const stars = wrap.querySelectorAll('.rating .star');
          stars.forEach((s, i) => s.classList.toggle('filled', i < r));
        } catch (err) { Forge.showToast(err.message || 'Rate failed', 'error'); }
      },
    });
    wrap.appendChild(rating);
    const flagBtn = Forge.h(`<button class="btn btn-ghost btn-sm">🚩 Flag this output</button>`);
    flagBtn.addEventListener('click', () => openFlagModal(run));
    wrap.appendChild(flagBtn);
    return wrap;
  }

  function openFlagModal(run) {
    const form = Forge.h(`
      <div>
        <div class="form-group">
          <label class="form-label">Reason</label>
          <select id="flag-reason">
            <option value="inaccurate">Inaccurate</option>
            <option value="offensive">Offensive or inappropriate</option>
            <option value="privacy">Exposes private info</option>
            <option value="off_topic">Off-topic or unrelated</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Notes (optional)</label>
          <textarea id="flag-notes" placeholder="Describe what went wrong…"></textarea>
        </div>
      </div>
    `);
    const footer = Forge.h(`<div>
      <button class="btn btn-ghost" id="flag-cancel">Cancel</button>
      <button class="btn btn-danger" id="flag-submit">Submit flag</button>
    </div>`);
    const { close } = Forge.openModal({ title: 'Flag this output', body: form, footer });
    footer.querySelector('#flag-cancel').addEventListener('click', close);
    footer.querySelector('#flag-submit').addEventListener('click', async () => {
      const reason = form.querySelector('#flag-reason').value;
      const notes = form.querySelector('#flag-notes').value;
      try {
        await ForgeApi.flagRun(run.id, `${reason}${notes ? ': ' + notes : ''}`);
        Forge.showToast('Flag submitted', 'success');
        close();
      } catch (err) { Forge.showToast(err.message || 'Flag failed', 'error'); }
    });
  }

  function buildPreviousRunsAccordion() {
    const el = Forge.h(`
      <div class="accordion mt-4">
        <div class="accordion-header" role="button" tabindex="0" aria-expanded="false">
          <span>Previous runs</span>
          <span class="accordion-icon" aria-hidden="true">▾</span>
        </div>
        <div class="accordion-body" id="prev-runs-body">
          <div class="text-secondary">Run this tool to see your history.</div>
        </div>
      </div>
    `);
    const header = el.querySelector('.accordion-header');
    const toggle = () => { el.classList.toggle('open'); header.setAttribute('aria-expanded', el.classList.contains('open')); };
    header.addEventListener('click', toggle);
    header.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    return el;
  }

  async function loadRecentRuns() {
    const user = Forge.getUser();
    if (!user.email) return;
    try {
      const res = await ForgeApi.getRuns(tool.id, { user_email: user.email, limit: 5 });
      recentRuns = Array.isArray(res) ? res : (res.runs || []);
      renderRecentRuns();
    } catch (e) { /* non-fatal */ }
  }

  function renderRecentRuns() {
    const body = Forge.qs('#prev-runs-body');
    if (!body) return;
    if (recentRuns.length === 0) {
      body.innerHTML = '<div class="text-secondary">Run this tool to see your history.</div>';
      return;
    }
    body.innerHTML = '';
    recentRuns.forEach((run) => {
      const row = Forge.h(`
        <div class="version-row">
          <div class="flex flex-gap-2 items-center">
            <span class="text-secondary text-sm">${Forge.formatRelative(run.created_at)}</span>
            ${run.rating ? `<span>★ ${run.rating}</span>` : ''}
          </div>
          <button class="btn btn-ghost btn-sm">Load inputs</button>
        </div>
      `);
      row.querySelector('button').addEventListener('click', () => loadRunInputs(run));
      body.appendChild(row);
    });
  }

  function loadRunInputs(run) {
    const data = tryParseJson(run.input_data) || run.input_data || {};
    const form = Forge.qs('#runner-form');
    Object.entries(data).forEach(([k, v]) => {
      const el = form.querySelector(`[name="${CSS.escape(k)}"]`);
      if (!el) return;
      if (el.type === 'checkbox') el.checked = !!v;
      else el.value = v == null ? '' : String(v);
    });
    saveInputsToStorage();
    updateRunEnabled();
    Forge.showToast('Inputs loaded', 'info');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
