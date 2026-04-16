// Catalog page: search, filters, infinite scroll grid of tool cards.

(function () {
  const CATEGORIES = [
    'All', 'Apps', 'Account Research', 'Email Generation', 'Contact Scoring',
    'Data Lookup', 'Reporting', 'Onboarding', 'Forecasting', 'Other',
  ];
  const TRUST_OPTIONS = ['All', 'Trusted', 'Verified', 'Caution'];
  const PAGE_SIZE = 12;

  const state = {
    search: '',
    category: 'All',
    appOnly: false,
    trust_tiers: [],
    sort: 'most_used',
    offset: 0,
    loading: false,
    done: false,
    tools: [],
  };

  let observer = null;

  function init() {
    Forge.renderLayout('catalog');
    Forge.renderFooter();
    // Honor ?type=app query param on initial load.
    if (Forge.getQueryParam('type') === 'app') {
      state.appOnly = true;
      state.category = 'Apps';
    }
    renderHero();
    renderCategoryPills();
    renderTrustPills();
    reflectAppsNavActive();
    hookEvents();
    reload();
  }

  function reflectAppsNavActive() {
    const link = document.getElementById('nav-apps-link');
    if (!link) return;
    if (state.appOnly) {
      link.classList.add('active');
      link.style.color = 'var(--accent)';
    } else {
      link.classList.remove('active');
      link.style.color = '';
    }
  }

  function renderHero() {
    const container = Forge.qs('#hero-container');
    const dismissed = localStorage.getItem('forge_visited') === '1';
    if (dismissed) return;
    const hero = Forge.h(`
      <div class="hero">
        <button class="hero-dismiss" aria-label="Dismiss welcome message">✕</button>
        <h1>Welcome to Forge</h1>
        <p class="text-secondary" style="font-size:15px; max-width:640px;">
          Share the apps and skills you built with Claude Code with your team.
          Browse what others have shipped; publish yours with <code>forge deploy</code>.
        </p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="#results-container">Browse Apps</a>
          <a class="btn btn-secondary" href="/skills.html">Browse Skills</a>
        </div>
      </div>
    `);
    hero.querySelector('.hero-dismiss').addEventListener('click', () => {
      localStorage.setItem('forge_visited', '1');
      hero.remove();
    });
    container.appendChild(hero);
  }

  function renderCategoryPills() {
    const el = Forge.qs('#category-pills');
    el.innerHTML = '';
    el.appendChild(Forge.h('<span class="pill-group-label">Category</span>'));
    CATEGORIES.forEach((cat) => {
      const active = cat === state.category;
      const pill = Forge.h(`<button class="pill ${active ? 'active' : ''}" role="tab" aria-selected="${active}">${Forge.escapeHtml(cat)}</button>`);
      pill.addEventListener('click', () => {
        state.category = cat;
        state.appOnly = cat === 'Apps';
        Forge.setQueryParam('type', state.appOnly ? 'app' : null);
        reflectAppsNavActive();
        renderCategoryPills();
        reload();
      });
      el.appendChild(pill);
    });
  }

  function renderTrustPills() {
    const el = Forge.qs('#trust-pills');
    el.innerHTML = '';
    el.appendChild(Forge.h('<span class="pill-group-label">Trust</span>'));
    TRUST_OPTIONS.forEach((tier) => {
      const isActive = tier === 'All'
        ? state.trust_tiers.length === 0
        : state.trust_tiers.includes(tier.toLowerCase());
      const pill = Forge.h(`<button class="pill ${isActive ? 'active' : ''}" role="tab" aria-selected="${isActive}">${Forge.escapeHtml(tier)}</button>`);
      pill.addEventListener('click', () => {
        if (tier === 'All') state.trust_tiers = [];
        else {
          const k = tier.toLowerCase();
          if (state.trust_tiers.includes(k)) state.trust_tiers = state.trust_tiers.filter((x) => x !== k);
          else state.trust_tiers.push(k);
        }
        renderTrustPills();
        reload();
      });
      el.appendChild(pill);
    });
  }

  function hookEvents() {
    const search = Forge.qs('#catalog-search');
    search.addEventListener('input', Forge.debounce((e) => {
      state.search = e.target.value.trim();
      reload();
    }, 300));
    Forge.qs('#sort-select').addEventListener('change', (e) => {
      state.sort = e.target.value;
      reload();
    });
    // Infinite scroll
    observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && !state.loading && !state.done) loadMore();
      });
    }, { rootMargin: '300px' });
    observer.observe(Forge.qs('#load-sentinel'));
  }

  function showSkeletons() {
    const grid = Forge.qs('#results-grid');
    grid.innerHTML = '';
    for (let i = 0; i < 6; i++) grid.appendChild(Forge.h('<div class="skeleton skeleton-card"></div>'));
  }

  function reload() {
    state.offset = 0;
    state.done = false;
    state.tools = [];
    showSkeletons();
    loadMore(true);
  }

  async function loadMore(isReload = false) {
    if (state.loading) return;
    state.loading = true;
    const filters = {
      search: state.search || undefined,
      // "Apps" is a virtual category; don't forward it to the API.
      category: state.category && state.category !== 'All' && state.category !== 'Apps' ? state.category : undefined,
      trust_tier: state.trust_tiers.length ? state.trust_tiers : undefined,
      sort: state.sort,
      limit: PAGE_SIZE,
      offset: state.offset,
      app_type: state.appOnly ? 'app' : undefined,
    };
    try {
      const res = await ForgeApi.getTools(filters);
      const raw = Array.isArray(res) ? res : (res.tools || res.data || []);
      // Defensive client-side filter in case the API doesn't support app_type yet.
      const items = state.appOnly ? raw.filter((t) => (t.app_type || '') === 'app') : raw;
      if (isReload) Forge.qs('#results-grid').innerHTML = '';
      state.tools = state.tools.concat(items);
      renderItems(items);
      state.offset += raw.length;
      if (raw.length < PAGE_SIZE) state.done = true;
      if (state.tools.length === 0) renderEmpty();
    } catch (err) {
      renderError(err);
    } finally {
      state.loading = false;
    }
  }

  function renderItems(items) {
    const grid = Forge.qs('#results-grid');
    items.forEach((tool) => grid.appendChild(renderToolCard(tool)));
  }

  function renderToolCard(tool) {
    // After the prompt-stack demolition, every card is an app.
    return appCard(tool);
  }

  function appCard(tool) {
    const tier = Forge.computeTrustTier(tool);
    const runCount = Forge.formatNumber(tool.run_count || 0);
    const el = Forge.h(`
      <article class="card card-hover tool-card" tabindex="0" aria-label="${Forge.escapeHtml(tool.name)}">
        <div class="tool-card-top">
          <span class="badge-app">⊞ APP</span>
          ${Forge.trustTierBadge(tier)}
        </div>
        <h3 class="tool-card-title">${Forge.escapeHtml(tool.name)}</h3>
        <p class="tool-card-tagline">${Forge.escapeHtml(tool.tagline || '')}</p>
        <div class="tool-card-divider"></div>
        <span class="text-muted text-sm">${Forge.escapeHtml(tool.category || 'Other')}</span>
        <div class="tool-card-meta">
          <span>${Forge.escapeHtml(tool.author_name || 'Unknown')}</span>
          <div class="tool-card-stats">
            <span title="Open count">↻ ${runCount} opens</span>
            ${tool.avg_rating ? `<span>★ ${Number(tool.avg_rating).toFixed(1)}</span>` : ''}
          </div>
        </div>
        <div class="tool-card-actions">
          <button class="btn btn-sm btn-open-app" type="button"><span class="app-icon" aria-hidden="true">⊞</span>Open App</button>
        </div>
      </article>
    `);
    const openBtn = el.querySelector('.btn-open-app');
    const open = () => openAppModal(tool);
    openBtn.addEventListener('click', (e) => { e.stopPropagation(); open(); });
    el.addEventListener('click', (e) => {
      if (e.target.closest('a,button')) return;
      open();
    });
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') open();
    });
    return el;
  }

  function openAppModal(tool) {
    closeAppModal();
    const slug = tool.slug || tool.id;
    const user = Forge.getUser();
    const userParam = encodeURIComponent(user.email || user.name || '');
    const src = `/apps/${encodeURIComponent(slug)}?user=${userParam}`;
    const tier = Forge.computeTrustTier(tool);
    const modal = Forge.h(`
      <div class="app-modal" role="dialog" aria-modal="true" aria-label="${Forge.escapeHtml(tool.name)}">
        <div class="app-modal-header">
          <h3 class="app-modal-title">${Forge.escapeHtml(tool.name)}</h3>
          <div class="app-modal-actions">
            ${Forge.trustTierBadge(tier)}
            <button class="app-modal-close" type="button" aria-label="Close app">✕</button>
          </div>
        </div>
        <div class="app-modal-body">
          <div class="app-modal-spinner" aria-hidden="true"><span class="spinner"></span> Loading app…</div>
          <iframe
            class="app-modal-iframe"
            src="${Forge.escapeHtml(src)}"
            title="${Forge.escapeHtml(tool.name)}"
            sandbox="allow-scripts allow-forms allow-modals"
            referrerpolicy="no-referrer"
            loading="eager"></iframe>
        </div>
      </div>
    `);
    document.body.appendChild(modal);
    document.body.style.overflow = 'hidden';
    const iframe = modal.querySelector('iframe');
    const spinner = modal.querySelector('.app-modal-spinner');
    iframe.addEventListener('load', () => { if (spinner) spinner.remove(); });
    const closeBtn = modal.querySelector('.app-modal-close');
    closeBtn.addEventListener('click', closeAppModal);
    modal._escHandler = (e) => {
      if (e.key === 'Escape') closeAppModal();
    };
    document.addEventListener('keydown', modal._escHandler);
    closeBtn.focus();
  }

  function closeAppModal() {
    const existing = document.querySelector('.app-modal');
    if (!existing) return;
    if (existing._escHandler) document.removeEventListener('keydown', existing._escHandler);
    // Drop iframe before removing so any in-flight JS in the sandbox stops.
    const iframe = existing.querySelector('iframe');
    if (iframe) iframe.remove();
    existing.remove();
    document.body.style.overflow = '';
  }

  function renderEmpty() {
    const grid = Forge.qs('#results-grid');
    grid.innerHTML = '';
    const msg = state.appOnly
      ? { title: 'No apps yet', body: 'Be the first to submit a full App.' }
      : { title: 'No apps match your search', body: 'Try different filters.' };
    grid.appendChild(Forge.h(`
      <div class="empty-state" style="grid-column: 1 / -1;">
        <div class="empty-state-icon">⚒</div>
        <h3>${Forge.escapeHtml(msg.title)}</h3>
        <p>${Forge.escapeHtml(msg.body)}</p>
      </div>
    `));
  }

  function renderError(err) {
    const grid = Forge.qs('#results-grid');
    grid.innerHTML = '';
    grid.appendChild(Forge.h(`
      <div class="empty-state" style="grid-column: 1 / -1;">
        <div class="empty-state-icon">⚠</div>
        <h3>Couldn't load tools</h3>
        <p class="text-secondary">${Forge.escapeHtml(err.message || 'Something went wrong')}</p>
        <div class="mt-3"><button class="btn btn-secondary" id="retry-btn">Retry</button></div>
      </div>
    `));
    Forge.qs('#retry-btn').addEventListener('click', reload);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
