// My Tools — status tabs + live pipeline progress polling for in-review tools.

(function () {
  const STATUS_TABS = [
    { key: 'all', label: 'All', match: () => true },
    { key: 'draft', label: 'Drafts', match: (t) => t.status === 'draft' },
    { key: 'in_review', label: 'In Review', match: (t) => t.status === 'pending' || t.status === 'pending_review' || t.status === 'in_review' },
    { key: 'needs_changes', label: 'Changes Needed', match: (t) => t.status === 'needs_changes' },
    { key: 'approved', label: 'Live', match: (t) => t.status === 'approved' || t.status === 'live' },
    { key: 'rejected', label: 'Rejected', match: (t) => t.status === 'rejected' },
    { key: 'archived', label: 'Archived', match: (t) => t.status === 'archived' },
  ];

  const state = {
    activeTab: 'all',
    tools: [],
    counts: {},
    pollTimers: new Map(),
  };

  function init() {
    Forge.renderLayout('my-tools');
    Forge.renderFooter();
    const user = Forge.getUser();
    if (!user.email) renderIdentityGate();
    else loadAndRender();
  }

  function renderIdentityGate() {
    Forge.qs('#identity-gate').classList.remove('hidden');
    Forge.qs('#main-content').classList.add('hidden');
    const submit = Forge.qs('#gate-submit');
    submit.addEventListener('click', () => {
      const name = Forge.qs('#gate-name').value.trim();
      const email = Forge.qs('#gate-email').value.trim();
      if (!email || !email.includes('@')) { Forge.showToast('Valid email required', 'error'); return; }
      Forge.setUser(name, email);
      Forge.qs('#identity-gate').classList.add('hidden');
      Forge.qs('#main-content').classList.remove('hidden');
      loadAndRender();
    });
  }

  async function loadAndRender() {
    Forge.qs('#main-content').classList.remove('hidden');
    Forge.qs('#identity-gate').classList.add('hidden');
    await loadTools();
    renderTabs();
    renderList();
  }

  async function loadTools() {
    const user = Forge.getUser();
    const list = Forge.qs('#tools-list');
    list.innerHTML = '<div class="flex flex-gap-2 items-center mb-4"><span class="spinner"></span> Loading your tools…</div>';
    try {
      const res = await ForgeApi.getMyTools(user.email);
      state.tools = Array.isArray(res) ? res : (res.tools || res.data || []);
    } catch (err) {
      state.tools = [];
      list.innerHTML = `<div class="empty-state"><h3>Could not load your tools</h3><p>${Forge.escapeHtml(err.message)}</p></div>`;
      return;
    }
    state.counts = {};
    STATUS_TABS.forEach((tab) => {
      state.counts[tab.key] = state.tools.filter(tab.match).length;
    });
  }

  function renderTabs() {
    const el = Forge.qs('#status-tabs');
    el.innerHTML = '';
    STATUS_TABS.forEach((tab) => {
      const btn = Forge.h(`<button class="tab ${state.activeTab === tab.key ? 'active' : ''}" role="tab" aria-selected="${state.activeTab === tab.key}">${Forge.escapeHtml(tab.label)}<span class="count">${state.counts[tab.key] || 0}</span></button>`);
      btn.addEventListener('click', () => { state.activeTab = tab.key; renderTabs(); renderList(); });
      el.appendChild(btn);
    });
  }

  function renderList() {
    const list = Forge.qs('#tools-list');
    list.innerHTML = '';
    state.pollTimers.forEach((t) => clearTimeout(t));
    state.pollTimers.clear();

    const tab = STATUS_TABS.find((t) => t.key === state.activeTab);
    const filtered = state.tools.filter(tab.match);
    if (filtered.length === 0) {
      list.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">📭</div>
        <h3>No tools in this tab</h3>
        ${state.activeTab === 'all' ? '<p>Submit your first tool to get started.</p><a class="btn btn-primary mt-3" href="/submit.html">Submit a Tool</a>' : ''}
      </div>`;
      return;
    }
    filtered.forEach((tool) => list.appendChild(renderRow(tool)));
  }

  function renderRow(tool) {
    const tier = tool.status === 'approved' ? Forge.computeTrustTier(tool) : null;
    const row = Forge.h(`
      <div class="tool-row">
        <div>
          <h3 class="tool-row-title">${Forge.escapeHtml(tool.name)}</h3>
          <p class="tool-row-tagline">${Forge.escapeHtml(tool.tagline || '')}</p>
        </div>
        <div class="tool-row-meta">
          ${Forge.statusBadge(tool.status)}
          ${tier ? Forge.trustTierBadge(tier) : ''}
          ${tool.status === 'approved' ? `<span>▶ ${Forge.formatNumber(tool.run_count || 0)}</span>` : ''}
          <span>${Forge.formatRelative(tool.submitted_at || tool.created_at)}</span>
        </div>
        <div class="tool-row-actions">
          ${tool.status === 'approved' ? `<a class="btn btn-secondary btn-sm" href="/tool.html?slug=${encodeURIComponent(tool.slug || tool.id)}">View</a>` : ''}
          ${tool.status === 'draft' || tool.status === 'needs_changes' ? `<a class="btn btn-secondary btn-sm" href="/submit.html?edit=${tool.id}">Edit</a>` : ''}
          <button class="btn btn-ghost btn-sm" data-action="archive">Archive</button>
        </div>
      </div>
    `);
    row.querySelector('[data-action="archive"]').addEventListener('click', async () => {
      if (!confirm('Archive this tool?')) return;
      try {
        await ForgeApi.updateTool(tool.id, { status: 'archived' });
        Forge.showToast('Archived', 'success');
        await loadTools();
        renderTabs(); renderList();
      } catch (err) { Forge.showToast(err.message || 'Archive failed', 'error'); }
    });

    if (tool.status === 'pending' || tool.status === 'pending_review' || tool.status === 'in_review') {
      const expanded = Forge.h(`<div class="tool-row-expanded">
        <div class="text-secondary text-sm mb-2">Live agent pipeline progress:</div>
        <div class="pipeline" data-tool-id="${tool.id}"></div>
        <div class="text-muted text-sm mt-2">Usually takes 2-3 minutes. We'll email you when it's done.</div>
      </div>`);
      row.appendChild(expanded);
      pollPipelineFor(tool.id, expanded.querySelector('.pipeline'));
    }
    return row;
  }

  const PIPELINE_STAGES = [
    { key: 'preflight', label: 'Pre-flight check' },
    { key: 'classifier', label: 'Classification agent' },
    { key: 'security_scanner', label: 'Security scanner' },
    { key: 'red_team', label: 'Red team agent' },
    { key: 'prompt_hardener', label: 'Prompt hardener' },
    { key: 'qa_tester', label: 'QA tester' },
    { key: 'synthesizer', label: 'Review synthesizer' },
  ];

  function renderPipeline(target, status) {
    if (!target) return;
    const apiStages = Array.isArray(status && status.stages) ? status.stages : [];
    const byKey = {};
    apiStages.forEach((s) => { if (s && s.key) byKey[s.key] = s; });
    const alias = { security_scanner: 'security', prompt_hardener: 'hardener', qa_tester: 'qa' };
    target.innerHTML = PIPELINE_STAGES.map((stage) => {
      const s = byKey[stage.key] || byKey[alias[stage.key]] || {};
      const st = (s.status || 'waiting').toLowerCase();
      const icon = st === 'done' ? '✓' : (st === 'running' || st === 'in_progress') ? '⟳' : (st === 'failed' || st === 'error') ? '✕' : '○';
      const iconCls = st === 'done' ? 'done' : (st === 'running' || st === 'in_progress') ? 'running' : (st === 'failed' || st === 'error') ? 'failed' : 'waiting';
      const label = st === 'done' ? 'Done' : (st === 'running' || st === 'in_progress') ? 'Running…' : (st === 'failed' || st === 'error') ? (s.detail || 'Failed') : 'Waiting';
      return `<div class="pipeline-row">
        <span class="icon ${iconCls}">${icon}</span>
        <span class="label">${Forge.escapeHtml(stage.label)}</span>
        <span class="status">${Forge.escapeHtml(label)}</span>
      </div>`;
    }).join('');
  }

  function pollPipelineFor(toolId, target) {
    renderPipeline(target, {});
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const status = await ForgeApi.getAgentStatus(toolId);
        renderPipeline(target, status);
        const s = (status && status.status) || '';
        const complete = s === 'approved' || s === 'rejected' || s === 'needs_changes' || (Number(status?.progress_pct) >= 100);
        if (complete) {
          await loadTools();
          renderTabs(); renderList();
          return;
        }
      } catch (e) { /* retry */ }
      const timer = setTimeout(poll, 5000);
      state.pollTimers.set(toolId, timer);
    };
    poll();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
