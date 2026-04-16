// Conversational Tool Creator — describe a tool, get a full submission back.
// Pipeline: user text -> /api/creator/preview -> editable preview -> /api/creator/generate

(function () {
  'use strict';

  const BASE = '/api/creator';

  const EXAMPLES = [
    {
      title: 'Cold outreach email',
      body: 'A tool that takes a company name and drafts a personalized cold outreach email for an account executive.',
    },
    {
      title: 'Account research brief',
      body: 'A tool that takes a company name and generates a one-page research brief with funding history, key executives, and recent news.',
    },
    {
      title: 'Deal risk flagger',
      body: 'A tool that takes a deal stage, amount, and last activity date and flags whether the deal is at risk of slipping.',
    },
    {
      title: 'Meeting prep summary',
      body: 'A tool that takes a prospect name and role and summarizes what to ask them in a discovery call based on their likely priorities.',
    },
  ];

  const el = (id) => document.getElementById(id);

  const descInput = el('desc');
  const examplesWrap = el('examples');
  const generateBtn = el('generate-btn');
  const loadingBox = el('loading');
  const errorBanner = el('error-banner');

  const inputStage = el('input-stage');
  const previewCard = el('preview');
  const successState = el('success');

  const pvName = el('pv-name');
  const pvTagline = el('pv-tagline');
  const pvBadges = el('pv-badges');
  const pvDescription = el('pv-description');
  const pvSchema = el('pv-schema');
  const pvReliability = el('pv-reliability');

  const editName = el('edit-name');
  const editTagline = el('edit-tagline');
  const editPrompt = el('edit-prompt');

  const authorNameInput = el('author-name');
  const authorEmailInput = el('author-email');

  const startOverBtn = el('start-over-btn');
  const regenerateBtn = el('regenerate-btn');
  const submitBtn = el('submit-btn');
  const viewToolLink = el('view-tool-link');

  let currentTool = null;

  // -------------------- helpers --------------------

  function setLoading(on, text) {
    loadingBox.classList.toggle('active', on);
    generateBtn.disabled = on;
    if (regenerateBtn) regenerateBtn.disabled = on;
    if (submitBtn) submitBtn.disabled = on;
    if (text) {
      const line1 = loadingBox.querySelector('.line-1');
      if (line1) line1.textContent = text;
    }
  }

  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.classList.add('active');
  }

  function clearError() {
    errorBanner.classList.remove('active');
    errorBanner.textContent = '';
  }

  function renderExamples() {
    examplesWrap.innerHTML = EXAMPLES.map((ex, i) => `
      <button type="button" class="example-chip" data-idx="${i}">
        <strong>${escapeHtml(ex.title)}</strong>
        ${escapeHtml(ex.body)}
      </button>
    `).join('');
    examplesWrap.querySelectorAll('.example-chip').forEach((btn) => {
      btn.addEventListener('click', () => {
        const idx = Number(btn.dataset.idx);
        descInput.value = EXAMPLES[idx].body;
        descInput.focus();
      });
    });
  }

  function categoryBadge(category) {
    const c = escapeHtml(category || 'Other');
    return `<span class="badge-category">${c}</span>`;
  }

  function outputBadge(outputType) {
    const t = (outputType || 'probabilistic').toLowerCase();
    const label = {
      deterministic: '= Consistent',
      probabilistic: '⚡ Variable',
      mixed: '~ Mixed',
    }[t] || t;
    return `<span class="badge-output ${t}"><span class="dot"></span>${escapeHtml(label)}</span>`;
  }

  function tierBadge(tier) {
    const t = Number(tier) || 1;
    const labels = { 1: 'Tier 1 · Safe', 2: 'Tier 2 · Review', 3: 'Tier 3 · Restricted' };
    const cls = { 1: 'badge-trusted', 2: 'badge-verified', 3: 'badge-restricted' }[t] || 'badge-unverified';
    return `<span class="badge ${cls}">${escapeHtml(labels[t] || 'Tier ?')}</span>`;
  }

  function renderSchema(schema) {
    if (!Array.isArray(schema) || schema.length === 0) {
      pvSchema.innerHTML = '<div class="text-muted">No inputs defined.</div>';
      return;
    }
    pvSchema.innerHTML = schema.map((f) => {
      const name = escapeHtml(f.name || '');
      const label = escapeHtml(f.label || f.name || '');
      const type = escapeHtml(f.type || 'text');
      const required = f.required ? 'required' : 'optional';
      const requiredCls = f.required ? '' : 'optional';
      const reqLabel = f.required ? 'required' : 'optional';
      return `
        <div class="schema-field">
          <code>{{${name}}}</code>
          <div>${label}</div>
          <div class="field-type">${type}</div>
          <div class="field-required ${requiredCls}">${reqLabel}</div>
        </div>
      `;
    }).join('');
  }

  function renderPreview(tool) {
    currentTool = tool;
    pvName.textContent = tool.name || '';
    pvTagline.textContent = tool.tagline || '';
    pvDescription.textContent = tool.description || '';
    pvReliability.textContent = tool.reliability_note || '';
    pvBadges.innerHTML = [
      categoryBadge(tool.category),
      outputBadge(tool.output_type),
      tierBadge(tool.security_tier),
    ].join(' ');

    editName.value = tool.name || '';
    editTagline.value = tool.tagline || '';
    editPrompt.value = tool.system_prompt || '';

    renderSchema(tool.input_schema);

    inputStage.style.display = 'none';
    previewCard.classList.add('active');
    successState.classList.remove('active');

    // Pre-fill identity from localStorage if available
    if (window.getUser) {
      const u = window.getUser();
      if (u && u.name && !authorNameInput.value) authorNameInput.value = u.name;
      if (u && u.email && !authorEmailInput.value) authorEmailInput.value = u.email;
    }

    previewCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function collectEditedTool() {
    if (!currentTool) return null;
    return {
      ...currentTool,
      name: (editName.value || '').trim() || currentTool.name,
      tagline: (editTagline.value || '').trim() || currentTool.tagline,
      system_prompt: (editPrompt.value || '').trim() || currentTool.system_prompt,
    };
  }

  // -------------------- API calls --------------------

  async function callPreview(description) {
    const res = await fetch(`${BASE}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ description }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.message || body.error || `Preview failed (${res.status})`);
    return body.generated_tool;
  }

  async function callGenerate(tool, authorName, authorEmail) {
    const res = await fetch(`${BASE}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        tool,
        author_name: authorName,
        author_email: authorEmail,
      }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.message || body.error || `Submit failed (${res.status})`);
    return body;
  }

  // -------------------- Handlers --------------------

  async function onGenerate() {
    clearError();
    const desc = (descInput.value || '').trim();
    if (desc.length < 10) {
      showError('Describe what the tool should do — at least a sentence.');
      descInput.focus();
      return;
    }
    setLoading(true, 'AI is designing your tool…');
    try {
      const tool = await callPreview(desc);
      renderPreview(tool);
    } catch (e) {
      showError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function onRegenerate() {
    clearError();
    const desc = (descInput.value || '').trim();
    if (!desc) {
      showError('Original description missing — start over.');
      return;
    }
    setLoading(true, 'Regenerating…');
    try {
      const tool = await callPreview(desc);
      renderPreview(tool);
    } catch (e) {
      showError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit() {
    clearError();
    const authorName = (authorNameInput.value || '').trim();
    const authorEmail = (authorEmailInput.value || '').trim();
    if (!authorEmail) {
      showError('Your email is required to submit.');
      authorEmailInput.focus();
      return;
    }
    const edited = collectEditedTool();
    if (!edited) {
      showError('No generated tool to submit.');
      return;
    }

    if (window.setUser) {
      window.setUser({ name: authorName, email: authorEmail });
    }

    setLoading(true, 'Submitting to the pipeline…');
    try {
      const result = await callGenerate(edited, authorName, authorEmail);
      previewCard.classList.remove('active');
      successState.classList.add('active');
      if (result.slug) {
        viewToolLink.href = `/tool.html?slug=${encodeURIComponent(result.slug)}`;
      } else if (result.tool_id) {
        viewToolLink.href = `/tool.html?id=${encodeURIComponent(result.tool_id)}`;
      }
      successState.scrollIntoView({ behavior: 'smooth' });
    } catch (e) {
      showError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  function onStartOver() {
    currentTool = null;
    previewCard.classList.remove('active');
    successState.classList.remove('active');
    inputStage.style.display = '';
    clearError();
    descInput.focus();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // -------------------- Init --------------------

  function init() {
    if (window.Forge && window.Forge.renderLayout) {
      window.Forge.renderLayout('catalog');
      window.Forge.renderFooter();
    }
    renderExamples();
    generateBtn.addEventListener('click', onGenerate);
    startOverBtn.addEventListener('click', onStartOver);
    regenerateBtn.addEventListener('click', onRegenerate);
    submitBtn.addEventListener('click', onSubmit);

    descInput.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        onGenerate();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
