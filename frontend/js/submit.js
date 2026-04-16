// Single-page prompt-first submit flow.
// Prompt → auto-detected {{variables}} → inline test run → optional auto-fill metadata → submit.

(function () {
  'use strict';

  var advanced = new URL(location.href).searchParams.get('advanced') === '1';
  if (advanced) {
    console.info('[submit] advanced mode requested — using single-page anyway (advanced editor TBD).');
  }

  var DEFAULT_DRAFT_KEY = 'forge_submit_prompt_draft_v2';
  var PREFILL_KEY = 'forge_submit_prefill';

  var editor = document.getElementById('prompt-editor');
  var varChips = document.getElementById('var-chips');
  var charCount = document.getElementById('char-count');
  var inputsList = document.getElementById('inputs-list');
  var testInputsWrap = document.getElementById('test-inputs');
  var testRunBtn = document.getElementById('test-run-btn');
  var testOutput = document.getElementById('test-output');
  var testMeta = document.getElementById('test-meta');
  var autofillBtn = document.getElementById('autofill-btn');
  var autofillStatus = document.getElementById('autofill-status');
  var fName = document.getElementById('f-name');
  var fTagline = document.getElementById('f-tagline');
  var fDescription = document.getElementById('f-description');
  var fCategory = document.getElementById('f-category');
  var fOutputType = document.getElementById('f-output-type');
  var fAuthorName = document.getElementById('f-author-name');
  var fAuthorEmail = document.getElementById('f-author-email');
  var submitBtn = document.getElementById('submit-btn');
  var saveDraftBtn = document.getElementById('save-draft-btn');
  var submitStatus = document.getElementById('submit-status');
  var detailsDrawer = document.getElementById('details-drawer');
  var detailsStatus = document.getElementById('details-status');
  var postSubmit = document.getElementById('post-submit');
  var builder = document.getElementById('builder');

  if (!editor) {
    console.error('[submit] prompt editor missing — bailing.');
    return;
  }

  var varMeta = {};

  var debounce = (window.Forge && window.Forge.debounce) || function (fn, ms) {
    var t; return function () {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms || 300);
    };
  };

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function prettyLabel(varName) {
    return String(varName || '').replace(/_/g, ' ')
      .replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function detectVariables(prompt) {
    var seen = {};
    var out = [];
    var re = /\{\{\s*(\w+)\s*\}\}/g;
    var m;
    while ((m = re.exec(prompt)) !== null) {
      var name = m[1];
      if (!seen[name]) {
        seen[name] = true;
        out.push(name);
      }
    }
    return out;
  }

  function renderChips(vars) {
    if (!vars.length) {
      varChips.innerHTML = '<span style="font-size:11px; color:#555;">none</span>';
      return;
    }
    varChips.innerHTML = vars.map(function (v) {
      return '<span class="var-chip">{{' + escapeHtml(v) + '}}</span>';
    }).join('');
  }

  function renderInputs(vars) {
    if (!vars.length) {
      inputsList.innerHTML = '<div class="empty-inputs">No variables yet. Add <code>{{name}}</code> anywhere in your prompt.</div>';
      return;
    }
    inputsList.innerHTML = vars.map(function (v, i) {
      var meta = varMeta[v] || {};
      var label = meta.label || prettyLabel(v);
      var placeholder = meta.placeholder || '';
      var required = meta.required !== false;
      return (
        '<div class="input-card" data-var="' + escapeHtml(v) + '">' +
          '<div class="var-name">{{' + escapeHtml(v) + '}}</div>' +
          '<input type="text" class="var-label" data-field="label" value="' + escapeHtml(label) + '" placeholder="Field label">' +
          '<input type="text" class="var-placeholder" data-field="placeholder" value="' + escapeHtml(placeholder) + '" placeholder="Placeholder (optional)">' +
          '<div class="input-card-row">' +
            '<input type="checkbox" data-field="required" id="req-' + i + '" ' + (required ? 'checked' : '') + '>' +
            '<label for="req-' + i + '">required</label>' +
          '</div>' +
        '</div>'
      );
    }).join('');

    inputsList.querySelectorAll('.input-card').forEach(function (card) {
      var v = card.getAttribute('data-var');
      varMeta[v] = varMeta[v] || {};
      card.querySelectorAll('[data-field]').forEach(function (el) {
        el.addEventListener('input', function () {
          var field = el.getAttribute('data-field');
          if (field === 'required') {
            varMeta[v].required = el.checked;
          } else {
            varMeta[v][field] = el.value;
          }
          saveDraft();
        });
      });
    });
  }

  function renderTestInputs(vars) {
    if (!vars.length) {
      testInputsWrap.innerHTML = '<div class="empty-inputs">Add <code>{{variables}}</code> to your prompt to enable testing.</div>';
      testRunBtn.disabled = true;
      return;
    }
    testInputsWrap.innerHTML = vars.map(function (v) {
      var meta = varMeta[v] || {};
      var existing = meta.sampleValue || '';
      var label = meta.label || prettyLabel(v);
      var isLong = /description|prompt|message|body|text|notes|context/i.test(v);
      var control = isLong
        ? '<textarea data-testvar="' + escapeHtml(v) + '" placeholder="Sample value…">' + escapeHtml(existing) + '</textarea>'
        : '<input type="text" data-testvar="' + escapeHtml(v) + '" value="' + escapeHtml(existing) + '" placeholder="Sample value…">';
      return '<div><label>' + escapeHtml(label) + ' <span style="color:#555;">(' + escapeHtml(v) + ')</span></label>' + control + '</div>';
    }).join('');
    testRunBtn.disabled = false;

    testInputsWrap.querySelectorAll('[data-testvar]').forEach(function (el) {
      el.addEventListener('input', function () {
        var v = el.getAttribute('data-testvar');
        varMeta[v] = varMeta[v] || {};
        varMeta[v].sampleValue = el.value;
        saveDraft();
      });
    });
  }

  function getTestInputs() {
    var out = {};
    testInputsWrap.querySelectorAll('[data-testvar]').forEach(function (el) {
      out[el.getAttribute('data-testvar')] = el.value;
    });
    return out;
  }

  function recompute() {
    var prompt = editor.value;
    charCount.textContent = prompt.length + ' chars';
    var vars = detectVariables(prompt);
    renderChips(vars);
    renderInputs(vars);
    renderTestInputs(vars);
    updateSubmitEnabled();
  }

  function submitReady() {
    var prompt = editor.value.trim();
    var name = fName.value.trim();
    var tagline = fTagline.value.trim();
    var email = fAuthorEmail.value.trim();
    return prompt.length > 0 && name.length > 0 && tagline.length > 0 && email.indexOf('@') !== -1;
  }

  function updateSubmitEnabled() {
    var ready = submitReady();
    submitBtn.disabled = !ready;
    if (ready) {
      detailsStatus.textContent = ' — ready to submit';
      detailsStatus.style.color = '#1a7f4b';
    } else {
      var missing = [];
      if (!editor.value.trim()) missing.push('prompt');
      if (!fName.value.trim()) missing.push('name');
      if (!fTagline.value.trim()) missing.push('tagline');
      if (!fAuthorEmail.value.trim() || fAuthorEmail.value.indexOf('@') === -1) missing.push('email');
      detailsStatus.textContent = ' — need: ' + missing.join(', ');
      detailsStatus.style.color = '#888';
    }
  }

  function buildInputSchema() {
    var prompt = editor.value;
    var vars = detectVariables(prompt);
    return vars.map(function (v) {
      var meta = varMeta[v] || {};
      return {
        name: v,
        label: meta.label || prettyLabel(v),
        type: 'text',
        required: meta.required !== false,
        placeholder: meta.placeholder || '',
      };
    });
  }

  function saveDraft() {
    try {
      var payload = {
        prompt: editor.value,
        name: fName.value,
        tagline: fTagline.value,
        description: fDescription.value,
        category: fCategory.value,
        output_type: fOutputType.value,
        author_name: fAuthorName.value,
        author_email: fAuthorEmail.value,
        var_meta: varMeta,
        saved_at: new Date().toISOString(),
      };
      localStorage.setItem(DEFAULT_DRAFT_KEY, JSON.stringify(payload));
    } catch (e) { /* ignore */ }
  }

  function restoreDraft() {
    var prefill = null;
    try {
      var raw = localStorage.getItem(PREFILL_KEY);
      if (raw) {
        prefill = JSON.parse(raw);
        localStorage.removeItem(PREFILL_KEY);
      }
    } catch (e) { /* ignore */ }

    if (prefill) {
      editor.value = prefill.system_prompt || '';
      fName.value = prefill.name || '';
      if (prefill.category) fCategory.value = prefill.category;
      detailsDrawer.open = true;
      return;
    }

    try {
      var rawDraft = localStorage.getItem(DEFAULT_DRAFT_KEY);
      if (!rawDraft) return;
      var d = JSON.parse(rawDraft);
      editor.value = d.prompt || '';
      fName.value = d.name || '';
      fTagline.value = d.tagline || '';
      fDescription.value = d.description || '';
      if (d.category) fCategory.value = d.category;
      if (d.output_type) fOutputType.value = d.output_type;
      fAuthorName.value = d.author_name || '';
      fAuthorEmail.value = d.author_email || '';
      varMeta = d.var_meta || {};
    } catch (e) { /* ignore */ }
  }

  async function runTest() {
    var prompt = editor.value.trim();
    if (!prompt) return;
    testRunBtn.disabled = true;
    testOutput.classList.add('running');
    testOutput.textContent = 'Running...';
    testMeta.innerHTML = '<span class="spinner"></span> waiting on model…';
    var start = Date.now();
    try {
      var res = await fetch('/api/tools/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_prompt: prompt,
          inputs: getTestInputs(),
        }),
      });
      var body = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        testOutput.classList.remove('running');
        testOutput.textContent = 'Error: ' + (body.message || body.error || 'unknown');
        testMeta.textContent = '';
        return;
      }
      testOutput.classList.remove('running');
      testOutput.textContent = body.output || '(empty output)';
      var elapsed = body.duration_ms || (Date.now() - start);
      testMeta.textContent = 'Ran in ' + (elapsed / 1000).toFixed(1) + 's via ' + (body.model || 'Claude');
    } catch (err) {
      testOutput.classList.remove('running');
      testOutput.textContent = 'Network error: ' + err;
      testMeta.textContent = '';
    } finally {
      testRunBtn.disabled = false;
    }
  }

  async function autofillMetadata() {
    var prompt = editor.value.trim();
    if (!prompt) {
      autofillStatus.textContent = 'Write a prompt first.';
      return;
    }
    autofillBtn.disabled = true;
    autofillStatus.innerHTML = '<span class="spinner"></span> asking Claude…';
    try {
      var res = await fetch('/api/tools/suggest-metadata', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_prompt: prompt,
          variables: detectVariables(prompt),
        }),
      });
      var body = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        autofillStatus.textContent = 'Auto-fill failed: ' + (body.message || body.error || 'unknown');
        return;
      }
      if (body.name && !fName.value) fName.value = body.name;
      if (body.tagline && !fTagline.value) fTagline.value = body.tagline;
      if (body.description && !fDescription.value) fDescription.value = body.description;
      if (body.category) {
        var opts = Array.prototype.map.call(fCategory.options, function (o) { return o.value; });
        if (opts.indexOf(body.category) !== -1) fCategory.value = body.category;
      }
      if (body.output_type) {
        var typeOpts = ['deterministic', 'probabilistic', 'mixed'];
        if (typeOpts.indexOf(body.output_type) !== -1) fOutputType.value = body.output_type;
      }
      autofillStatus.textContent = 'Filled. Review and edit below.';
      updateSubmitEnabled();
      saveDraft();
    } catch (err) {
      autofillStatus.textContent = 'Network error: ' + err;
    } finally {
      autofillBtn.disabled = false;
    }
  }

  async function submitForReview() {
    if (!submitReady()) {
      detailsDrawer.open = true;
      return;
    }
    submitBtn.disabled = true;
    submitStatus.classList.remove('error');
    submitStatus.innerHTML = '<span class="spinner"></span> submitting…';
    var payload = {
      name: fName.value.trim(),
      tagline: fTagline.value.trim(),
      description: fDescription.value.trim(),
      category: fCategory.value,
      output_type: fOutputType.value,
      system_prompt: editor.value,
      input_schema: buildInputSchema(),
      author_name: fAuthorName.value.trim(),
      author_email: fAuthorEmail.value.trim(),
    };
    try {
      var res = await fetch('/api/tools/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      var body = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        submitBtn.disabled = false;
        submitStatus.classList.add('error');
        submitStatus.textContent = 'Error: ' + (body.message || body.error || 'unknown');
        return;
      }
      try {
        localStorage.removeItem(DEFAULT_DRAFT_KEY);
        localStorage.setItem('forge_has_submitted', '1');
      } catch (e) { /* ignore */ }
      if (window.Forge && window.Forge.trackMilestone) {
        window.Forge.trackMilestone('first_submission');
      }
      showSuccess(body);
    } catch (err) {
      submitBtn.disabled = false;
      submitStatus.classList.add('error');
      submitStatus.textContent = 'Network error: ' + err;
    }
  }

  function showSuccess(body) {
    builder.style.display = 'none';
    postSubmit.classList.remove('hidden');
    var toolUrl = '/tool.html?slug=' + encodeURIComponent(body.slug || '');
    postSubmit.innerHTML =
      '<section class="success-panel">' +
        '<h2>Submitted. The agent pipeline is reviewing now.</h2>' +
        '<p>Typical review takes 2–3 minutes. You\'ll see it in <a href="/my-tools.html">My Tools</a> with live progress.</p>' +
        '<div style="display:flex; justify-content:center; gap:10px;">' +
          '<a class="btn btn-primary" href="' + escapeHtml(toolUrl) + '">View your tool →</a>' +
          '<a class="btn btn-secondary" href="/submit.html">Submit another</a>' +
        '</div>' +
        '<p class="text-secondary" style="margin-top:16px; font-size:12px;">Tool ID: ' + (body.id || '—') + ' · slug: ' + escapeHtml(body.slug || '—') + '</p>' +
      '</section>';
  }

  restoreDraft();
  recompute();
  updateSubmitEnabled();

  editor.addEventListener('input', debounce(function () {
    recompute();
    saveDraft();
  }, 120));
  [fName, fTagline, fDescription, fAuthorName, fAuthorEmail].forEach(function (el) {
    el.addEventListener('input', function () {
      updateSubmitEnabled();
      saveDraft();
    });
  });
  [fCategory, fOutputType].forEach(function (el) {
    el.addEventListener('change', function () {
      saveDraft();
    });
  });

  testRunBtn.addEventListener('click', runTest);
  autofillBtn.addEventListener('click', autofillMetadata);
  submitBtn.addEventListener('click', submitForReview);
  saveDraftBtn.addEventListener('click', function () {
    saveDraft();
    submitStatus.textContent = 'Draft saved locally.';
    setTimeout(function () { submitStatus.textContent = ''; }, 2000);
  });

  try {
    var user = JSON.parse(localStorage.getItem('forge_user') || '{}');
    if (user.name && !fAuthorName.value) fAuthorName.value = user.name;
    if (user.email && !fAuthorEmail.value) fAuthorEmail.value = user.email;
  } catch (e) { /* ignore */ }
  updateSubmitEnabled();
})();
