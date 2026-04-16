// Forge — Chain Tools (Workflow Composability v1)
//
// Loads approved tools into two selectors, renders per-step input forms from
// each tool's input_schema, optionally maps step 1's output into a step 2
// input field, and executes the chain via POST /api/workflows/run.

(function () {
  'use strict';

  const STATE = {
    tools: [],
    byId: new Map(),
    selected: { 1: null, 2: null },
  };

  // ---------- helpers ----------

  function $(id) { return document.getElementById(id); }

  function setStatus(msg, isError) {
    const el = $('run-status');
    if (!el) return;
    el.textContent = msg || '';
    el.style.color = isError ? '#c04040' : '';
  }

  function parseSchema(schema) {
    if (!schema) return [];
    if (Array.isArray(schema)) return schema;
    if (typeof schema === 'string') {
      try {
        const parsed = JSON.parse(schema);
        return Array.isArray(parsed) ? parsed : [];
      } catch (e) { return []; }
    }
    return [];
  }

  function persistUser() {
    try {
      localStorage.setItem('forge.user.name', $('user-name').value || '');
      localStorage.setItem('forge.user.email', $('user-email').value || '');
    } catch (e) { /* ignore */ }
  }

  function loadUser() {
    try {
      $('user-name').value = localStorage.getItem('forge.user.name') || '';
      $('user-email').value = localStorage.getItem('forge.user.email') || '';
    } catch (e) { /* ignore */ }
  }

  // ---------- rendering ----------

  function renderToolOptions(selectEl) {
    selectEl.innerHTML = '';
    const blank = document.createElement('option');
    blank.value = '';
    blank.textContent = '— Select a tool —';
    selectEl.appendChild(blank);
    for (const t of STATE.tools) {
      const opt = document.createElement('option');
      opt.value = String(t.id);
      opt.textContent = t.name + (t.category ? ' · ' + t.category : '');
      selectEl.appendChild(opt);
    }
  }

  function renderStepInputs(stepNum, tool) {
    const container = $('step' + stepNum + '-inputs');
    if (!container) return;
    container.innerHTML = '';
    if (!tool) return;
    const fields = parseSchema(tool.input_schema);
    if (fields.length === 0) {
      const p = document.createElement('p');
      p.className = 'muted';
      p.textContent = 'This tool has no inputs.';
      container.appendChild(p);
      return;
    }
    for (const field of fields) {
      if (!field || typeof field !== 'object') continue;
      const name = field.name || field.field_name;
      if (!name) continue;
      const label = document.createElement('label');
      label.htmlFor = 'step' + stepNum + '-field-' + name;
      label.textContent = (field.label || name) + (field.required ? ' *' : '');

      let input;
      if (field.type === 'textarea') {
        input = document.createElement('textarea');
        input.rows = 3;
      } else if (field.type === 'select' && Array.isArray(field.options)) {
        input = document.createElement('select');
        for (const opt of field.options) {
          const o = document.createElement('option');
          o.value = typeof opt === 'object' ? (opt.value || opt.label || '') : String(opt);
          o.textContent = typeof opt === 'object' ? (opt.label || opt.value || '') : String(opt);
          input.appendChild(o);
        }
      } else {
        input = document.createElement('input');
        input.type = field.type === 'email' ? 'email'
          : field.type === 'number' ? 'number'
            : 'text';
      }
      input.id = 'step' + stepNum + '-field-' + name;
      input.dataset.step = String(stepNum);
      input.dataset.field = name;
      if (field.placeholder) input.placeholder = field.placeholder;

      container.appendChild(label);
      container.appendChild(input);
    }
  }

  function renderMappingOptions() {
    const select = $('mapping-target');
    if (!select) return;
    select.innerHTML = '';
    const none = document.createElement('option');
    none.value = '';
    none.textContent = "(none — don't auto-map)";
    select.appendChild(none);

    const tool = STATE.selected[2];
    if (!tool) return;
    for (const field of parseSchema(tool.input_schema)) {
      if (!field || !field.name) continue;
      const opt = document.createElement('option');
      opt.value = field.name;
      opt.textContent = field.label || field.name;
      select.appendChild(opt);
    }
  }

  function collectStepInputs(stepNum) {
    const out = {};
    const nodes = document.querySelectorAll(
      '#step' + stepNum + '-inputs [data-field]'
    );
    nodes.forEach(function (el) {
      out[el.dataset.field] = el.value != null ? el.value : '';
    });
    return out;
  }

  function renderResults(payload) {
    const container = $('results-container');
    if (!container) return;
    container.innerHTML = '';
    const results = (payload && payload.results) || [];
    if (!results.length) {
      container.textContent = 'No results returned.';
      return;
    }
    results.forEach(function (r) {
      const card = document.createElement('div');
      card.className = 'card result-card';
      card.style.marginTop = '0.75rem';

      const h = document.createElement('h3');
      h.textContent = 'Step ' + r.step + ' output';
      card.appendChild(h);

      const meta = document.createElement('p');
      meta.className = 'muted';
      meta.style.fontSize = '0.85em';
      const parts = [];
      if (r.model) parts.push(r.model);
      if (typeof r.duration_ms === 'number') parts.push(r.duration_ms + 'ms');
      if (typeof r.cost_usd === 'number') parts.push('$' + r.cost_usd.toFixed(6));
      meta.textContent = parts.join(' · ');
      card.appendChild(meta);

      const pre = document.createElement('pre');
      pre.style.whiteSpace = 'pre-wrap';
      pre.textContent = r.output || '';
      card.appendChild(pre);

      if (r.error) {
        const err = document.createElement('p');
        err.textContent = 'Error: ' + r.error;
        err.style.color = '#c04040';
        card.appendChild(err);
      }
      container.appendChild(card);
    });
  }

  // ---------- actions ----------

  async function loadTools() {
    try {
      const payload = await window.ForgeApi.apiFetch('/workflows/tools');
      STATE.tools = (payload && payload.tools) || [];
      STATE.byId = new Map(STATE.tools.map(function (t) { return [String(t.id), t]; }));
      renderToolOptions($('step1-tool'));
      renderToolOptions($('step2-tool'));
    } catch (e) {
      setStatus('Failed to load tools: ' + (e.message || e), true);
    }
  }

  function onToolChange(stepNum, value) {
    const tool = STATE.byId.get(String(value)) || null;
    STATE.selected[stepNum] = tool;
    renderStepInputs(stepNum, tool);
    if (stepNum === 2) renderMappingOptions();
  }

  async function runChain() {
    setStatus('Running…');
    persistUser();
    const step1 = STATE.selected[1];
    const step2 = STATE.selected[2];
    if (!step1 || !step2) {
      setStatus('Select a tool for both steps first.', true);
      return;
    }

    const inputs1 = collectStepInputs(1);
    const inputs2 = collectStepInputs(2);

    const mapTarget = ($('mapping-target') || {}).value || '';
    if (mapTarget) {
      inputs2[mapTarget] = '{{step1.output}}';
    }

    const body = {
      workflow_steps: [
        { tool_id: step1.id, inputs: inputs1 },
        { tool_id: step2.id, inputs: inputs2 },
      ],
      user_name: $('user-name').value || '',
      user_email: $('user-email').value || '',
    };

    try {
      const payload = await window.ForgeApi.apiFetch('/workflows/run', {
        method: 'POST',
        body: body,
      });
      setStatus('Done — ' + (payload.step_count || 0) + ' step(s) completed.');
      renderResults(payload);
    } catch (e) {
      const partial = e && e.body && e.body.results ? { results: e.body.results } : null;
      if (partial) renderResults(partial);
      setStatus('Chain failed: ' + (e.message || e), true);
    }
  }

  // ---------- bootstrap ----------

  document.addEventListener('DOMContentLoaded', function () {
    if (window.Forge && window.Forge.renderLayout) {
      window.Forge.renderLayout('catalog');
      window.Forge.renderFooter();
    }
    loadUser();
    loadTools();

    const s1 = $('step1-tool');
    const s2 = $('step2-tool');
    if (s1) s1.addEventListener('change', function (e) { onToolChange(1, e.target.value); });
    if (s2) s2.addEventListener('change', function (e) { onToolChange(2, e.target.value); });

    const btn = $('run-chain');
    if (btn) btn.addEventListener('click', runChain);
  });
})();
