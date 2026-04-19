// Forge catalog — persistent split view.
// Left: compact cards with Install/Open + Star. Right: live preview or detail.
// Click card → right pane loads. Star ☆ = wishlist. Install = commitment.

(function () {
  'use strict';

  const STORAGE_USER_ID = 'forge_user_id';
  const STORAGE_CAT_WIDTH = 'forge_cat_width';

  function uuidv4() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return 'anon-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }
  function getUserId() {
    let id = ''; try { id = localStorage.getItem(STORAGE_USER_ID) || ''; } catch (e) {}
    if (!id) { id = uuidv4(); try { localStorage.setItem(STORAGE_USER_ID, id); } catch (e) {} }
    return id;
  }
  function authHeaders() { return { 'X-Forge-User-Id': getUserId() }; }
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  const state = {
    items: [],
    installedSet: new Set(),
    starredSet: new Set(),
    activeCategory: null,
    search: '',
    selectedId: null,
  };

  let _runningPollTimer = null;
  let _runningApps = {}; // slug -> {running, pid, uptime_sec}

  function startRunningPoll(slug) {
    stopRunningPoll();
    pollRunning(slug);
    _runningPollTimer = setInterval(() => pollRunning(slug), 15000);
  }

  function stopRunningPoll() {
    if (_runningPollTimer) { clearInterval(_runningPollTimer); _runningPollTimer = null; }
  }

  async function pollRunning(slug) {
    try {
      const r = await fetch('/api/forge-agent/running', { signal: AbortSignal.timeout(8000) });
      if (r.ok) {
        const data = await r.json();
        _runningApps = {};
        (data.apps || []).forEach(a => { _runningApps[a.slug] = a; });
        updateControlPanelStatus(slug);
      }
    } catch (e) {}
  }

  function updateControlPanelStatus(slug) {
    const dot = document.getElementById('cp-status-dot');
    const label = document.getElementById('cp-status-label');
    const btn = document.getElementById('cp-primary-btn');
    if (!dot || !label) return;
    const rs = _runningApps[slug];
    const running = rs && rs.running;
    dot.className = 'cp-dot ' + (running ? 'running' : 'stopped');
    if (running) {
      const uptime = rs.uptime_sec ? formatUptime(rs.uptime_sec) : '';
      label.innerHTML = `<span style="color:#22c55e;">Running${uptime ? ' · ' + uptime : ''}</span>`;
      if (btn) { btn.textContent = 'Focus'; btn.dataset.action = 'focus'; }
    } else {
      label.innerHTML = '<span style="color:#555;">Not running</span>';
      if (btn) { btn.textContent = 'Launch'; btn.dataset.action = 'launch'; }
    }
  }

  function formatUptime(sec) {
    if (!sec || sec < 60) return 'just now';
    if (sec < 3600) return Math.floor(sec / 60) + 'm';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return h + 'h ' + m + 'm';
  }

  const listEl = document.getElementById('list');
  const filtersEl = document.getElementById('filters');
  const searchEl = document.getElementById('search');
  const appBar = document.getElementById('app-bar');
  const appPane = document.getElementById('app-pane');
  const emptyState = document.getElementById('empty-state');

  // ---- Data ----

  async function loadItems() {
    const p = new URLSearchParams();
    if (state.activeCategory) p.set('category', state.activeCategory);
    if (state.search) p.set('search', state.search);
    p.set('sort', 'most_used'); p.set('limit', '50');
    const res = await fetch('/api/tools?' + p.toString());
    const body = await res.json().catch(() => ({}));
    state.items = body.tools || [];
  }

  async function loadUserState() {
    const h = authHeaders();
    const [shelf, stars] = await Promise.all([
      fetch('/api/me/items', { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch('/api/me/stars', { headers: h }).then(r => r.json()).catch(() => ({})),
    ]);
    state.installedSet = new Set((shelf.items || []).map(i => i.id));
    state.starredSet = new Set((stars.items || []).map(i => i.id));
  }

  // ---- Filters ----

  function renderFilters() {
    const cats = [...new Set(state.items.map(t => t.category).filter(Boolean))].sort();
    filtersEl.innerHTML = '';
    filtersEl.appendChild(mkPill('All', null));
    cats.forEach(c => filtersEl.appendChild(mkPill(c, c)));
  }
  function mkPill(label, value) {
    const el = document.createElement('button');
    el.className = 'cat-pill' + (state.activeCategory === value ? ' active' : '');
    el.textContent = label;
    el.onclick = async () => { state.activeCategory = value; await loadItems(); renderAll(); };
    return el;
  }

  // ---- Card list ----

  function renderList() {
    listEl.innerHTML = '';
    if (!state.items.length) {
      listEl.innerHTML = '<div style="padding:32px 16px;text-align:center;color:#555;">No apps match.</div>';
      return;
    }
    // Role-aware sort: apps tagged for user's role float to the top
    let sorted = [...state.items];
    if (state.userRole) {
      sorted.sort((a, b) => {
        const aMatch = roleMatch(a);
        const bMatch = roleMatch(b);
        if (aMatch && !bMatch) return -1;
        if (!aMatch && bMatch) return 1;
        return (b.install_count || 0) - (a.install_count || 0);
      });
    }
    sorted.forEach(tool => listEl.appendChild(renderCard(tool)));
  }

  function roleMatch(tool) {
    if (!state.userRole) return false;
    try {
      const tags = typeof tool.role_tags === 'string' ? JSON.parse(tool.role_tags) : (tool.role_tags || []);
      return tags.includes(state.userRole);
    } catch (e) { return false; }
  }

  function renderCard(tool) {
    const isInstalled = state.installedSet.has(tool.id);
    const isStarred = state.starredSet.has(tool.id);
    const isSelected = state.selectedId === tool.id;
    const isExt = tool.delivery === 'external';

    // Action label: external installed = "Launch", external not installed = "Install", embedded = "Open"
    const actionLabel = isInstalled ? (isExt ? 'Launch' : '✓') : (isExt ? 'Install' : 'Open');
    const actionClass = isInstalled && !isExt ? 'c-action done' : 'c-action';

    const card = document.createElement('div');
    card.className = 'c-card' + (isSelected ? ' selected' : '');
    card.dataset.id = tool.id;
    card.tabIndex = 0;
    card.innerHTML = `
      <div class="c-icon">${esc(tool.icon || '⊞')}</div>
      <div class="c-info">
        <p class="c-name">${esc(tool.name)}</p>
        <p class="c-tag">${esc(tool.tagline || '')}</p>
        <span style="font-size:10px;color:#555;">${esc(tool.author_name || '')}${tool.install_count ? ` · ${tool.install_count} installs` : ''}</span>
      </div>
      <button class="c-star ${isStarred ? 'starred' : ''}" data-act="star" title="${isStarred ? 'Saved' : 'Save for later'}">
        ${isStarred ? '★' : '☆'}
      </button>
      <button class="${actionClass}" data-act="install" data-id="${tool.id}">
        ${actionLabel}
      </button>`;

    card.addEventListener('click', e => {
      if (e.target.closest('[data-act]')) return;
      selectApp(tool);
    });
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter') selectApp(tool);
    });

    card.querySelector('[data-act="star"]').addEventListener('click', e => {
      e.stopPropagation();
      handleStar(tool, e.currentTarget);
    });
    card.querySelector('[data-act="install"]').addEventListener('click', e => {
      e.stopPropagation();
      handleInstall(tool, e.currentTarget);
    });

    return card;
  }

  // ---- Actions ----

  async function handleStar(tool, btn) {
    const starred = state.starredSet.has(tool.id);
    if (starred) {
      await fetch(`/api/me/stars/${tool.id}`, { method: 'DELETE', headers: authHeaders() });
      state.starredSet.delete(tool.id);
      btn.textContent = '☆'; btn.classList.remove('starred');
      btn.title = 'Save for later';
    } else {
      await fetch(`/api/me/stars/${tool.id}`, { method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/json' }, body: '{}' });
      state.starredSet.add(tool.id);
      btn.textContent = '★'; btn.classList.add('starred');
      btn.title = 'Saved';
    }
  }

  async function handleInstall(tool, btn) {
    const isExt = tool.delivery === 'external';

    if (!isExt) {
      // Embedded apps: "Open" loads the iframe. Auto-adds to shelf.
      if (!state.installedSet.has(tool.id)) {
        fetch(`/api/me/items/${tool.id}`, {
          method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/json' }, body: '{}',
        }).then(() => {
          state.installedSet.add(tool.id);
          btn.textContent = '✓'; btn.classList.add('done');
          updateBarInstallState(tool);
        }).catch(() => {});
      }
      selectApp(tool);
      return;
    }

    // External apps: if already installed, launch via forge-agent
    if (state.installedSet.has(tool.id)) {
      btn.disabled = true;
      btn.textContent = 'Opening…';
      fetch('/api/forge-agent/launch', {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_slug: tool.slug, app_name: tool.name }),
        signal: AbortSignal.timeout(5000),
      }).then(() => {
        btn.textContent = '● Running';
      }).catch(() => {
        btn.textContent = 'Launch';
      }).finally(() => { btn.disabled = false; });
      return;
    }

    // Not installed: load the detail view, then auto-trigger the detail Install button.
    // All progress rendering happens in the detail view — one code path.
    selectApp(tool);

    // Auto-click the detail Install button after a brief render delay
    setTimeout(() => {
      const detailBtn = document.getElementById('detail-install-btn');
      if (detailBtn) detailBtn.click();
    }, 300);
  }

  function updateBarInstallState(tool) {
    const barBtn = appBar.querySelector('.bar-install');
    if (!barBtn || parseInt(barBtn.dataset.id) !== tool.id) return;
    const inst = state.installedSet.has(tool.id);
    const isExt = tool.delivery === 'external';
    barBtn.textContent = inst ? (isExt ? '✓ Installed' : '✓ Installed') : (isExt ? 'Install' : 'Open');
    barBtn.classList.toggle('done', inst);
  }

  // ---- Right pane ----

  function selectApp(tool) {
    stopRunningPoll();
    state.selectedId = tool.id;
    listEl.querySelectorAll('.c-card').forEach(c =>
      c.classList.toggle('selected', parseInt(c.dataset.id) === tool.id));

    const isInstalled = state.installedSet.has(tool.id);
    const isExt = tool.delivery === 'external';
    const appUrl = `/apps/${encodeURIComponent(tool.slug)}?user=${encodeURIComponent(getUserId())}`;

    // Bar
    appBar.style.display = 'flex';
    const installLabel = isInstalled ? '✓ Installed' : (isExt ? 'Install' : 'Open');
    appBar.innerHTML = `
      <span class="app-name">${esc(tool.icon || '⊞')} ${esc(tool.name)}
        <span class="app-tagline-inline">${esc(tool.tagline || '')}</span>
      </span>
      <button class="bar-install ${isInstalled ? 'done' : ''}" data-id="${tool.id}">
        ${installLabel}
      </button>
      ${!isExt ? `<a href="${esc(appUrl)}" target="_blank" rel="noopener">↗ Full screen</a>` : ''}
      ${tool.source_url ? `<a href="${esc(tool.source_url)}" target="_blank" rel="noopener">Source</a>` : ''}`;
    appBar.querySelector('.bar-install').addEventListener('click', e => handleInstall(tool, e.currentTarget));

    // Pane — clear ALL previous content (iframe wrapper, detail view, etc.)
    emptyState.style.display = 'none';
    while (appPane.lastChild && appPane.lastChild !== emptyState) {
      appPane.removeChild(appPane.lastChild);
    }

    if (isExt) {
      // External app: combined view — info card on top, preview iframe on bottom
      renderExternalCombined(tool);
    } else {
      // Embedded app: load in iframe with preview mode
      const hasDemoData = !!(tool.demo_data);
      const showPreviewBanner = hasDemoData && !isInstalled;
      const previewUrl = appUrl + (appUrl.includes('?') ? '&' : '?') + 'preview=true';

      const wrap = document.createElement('div');
      wrap.style.cssText = 'display:flex;flex-direction:column;position:absolute;inset:0;';

      // Slim preview banner (Phase 2)
      if (showPreviewBanner) {
        const banner = document.createElement('div');
        banner.id = 'preview-banner';
        banner.style.cssText = 'height:36px;background:rgba(0,102,255,0.08);border-bottom:1px solid rgba(0,102,255,0.2);display:flex;align-items:center;padding:0 16px;gap:10px;flex-shrink:0;font-size:13px;';
        banner.innerHTML = `
          <span style="color:rgba(255,255,255,0.4);">Sample data</span>
          <span style="color:rgba(255,255,255,0.7);flex:1;">— install to make this yours</span>
          <button id="banner-add" style="background:#0066FF;color:white;border:none;padding:5px 14px;border-radius:5px;font-size:12px;font-weight:600;cursor:pointer;">+ Add to my Forge</button>`;
        wrap.appendChild(banner);

        // Wire the banner Add button
        setTimeout(() => {
          const addBtn = document.getElementById('banner-add');
          if (addBtn) {
            addBtn.addEventListener('click', async () => {
              addBtn.disabled = true; addBtn.textContent = '…';
              await fetch(`/api/me/items/${tool.id}`, {
                method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/json' }, body: '{}',
              });
              state.installedSet.add(tool.id);
              // Update card button
              const cardBtn = listEl.querySelector(`[data-id="${tool.id}"][data-act="install"]`);
              if (cardBtn) { cardBtn.textContent = '✓'; cardBtn.classList.add('done'); }
              updateBarInstallState(tool);
              // Transition banner
              banner.style.background = 'rgba(26,127,75,0.12)';
              banner.style.borderColor = 'rgba(26,127,75,0.3)';
              banner.innerHTML = '<span style="color:#1a7f4b;font-weight:500;">✓ Added</span><span style="color:rgba(255,255,255,0.5);flex:1;">— open from My Forge for your own data</span>';
              // After 2s, reload iframe without preview
              setTimeout(() => {
                const iframe = wrap.querySelector('iframe');
                if (iframe) iframe.src = appUrl; // no ?preview=true
                banner.style.display = 'none';
              }, 2000);
            });
          }
        }, 100);
      }

      // Social info bar
      const social = document.createElement('div');
      social.style.cssText = 'padding:6px 16px;font-size:11px;color:#666;border-bottom:1px solid #1a1a1a;flex-shrink:0;display:flex;gap:12px;';
      social.innerHTML = `<span>by ${esc(tool.author_name || 'Unknown')}</span>`;
      fetch(`/api/tools/${tool.id}/social`, { headers: authHeaders() }).then(r => r.json()).then(s => {
        const parts = [];
        if (s.team_install_count > 0) parts.push(`<span style="color:#0066FF;font-weight:600;">+${s.team_install_count} from your team</span>`);
        parts.push(`${s.install_count || 0} installs`);
        if (s.avg_rating) parts.push(`★ ${Number(s.avg_rating).toFixed(1)}`);
        social.innerHTML += parts.join(' · ');
      }).catch(() => {});
      wrap.appendChild(social);

      // Co-installs section
      const coinstallWrap = document.createElement('div');
      coinstallWrap.style.cssText = 'padding:0 16px 8px;';
      fetch(`/api/tools/${tool.id}/coinstalls`, { headers: authHeaders() }).then(r => r.json()).then(data => {
        if (!data.coinstalls || !data.coinstalls.length) return;
        coinstallWrap.innerHTML = `
          <div style="font-size:10px;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px;">Also used by people who use ${esc(tool.name)}</div>
          <div style="display:flex;gap:8px;margin-bottom:4px;">
            ${data.coinstalls.map(ci => `
              <div class="ci-card" data-slug="${esc(ci.slug)}" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:6px;padding:6px 10px;cursor:pointer;opacity:0.8;transition:opacity 0.15s;display:flex;align-items:center;gap:6px;">
                <span style="font-size:14px;">${esc(ci.icon || '⊞')}</span>
                <span style="font-size:11px;color:#ccc;">${esc(ci.name)}</span>
              </div>
            `).join('')}
          </div>`;
        coinstallWrap.querySelectorAll('.ci-card').forEach(card => {
          card.addEventListener('mouseenter', () => { card.style.opacity = '1'; });
          card.addEventListener('mouseleave', () => { card.style.opacity = '0.8'; });
          card.addEventListener('click', () => {
            const ciSlug = card.dataset.slug;
            const ciTool = state.items.find(t => t.slug === ciSlug);
            if (ciTool) selectApp(ciTool);
          });
        });
      }).catch(() => {});
      wrap.appendChild(coinstallWrap);

      // Iframe: preview mode if not installed + demo data exists
      const iframe = document.createElement('iframe');
      iframe.src = (showPreviewBanner) ? previewUrl : appUrl;
      // Catalog preview: allow-same-origin so apps that embed external content
      // (Hebbia's VPS iframe, Chariot's local backend) actually load. This is
      // the "try before you install" context — the user is actively previewing.
      // My Forge's persistent iframe (my-tools.html) keeps the strict sandbox
      // without allow-same-origin.
      iframe.sandbox = 'allow-scripts allow-forms allow-modals allow-downloads allow-same-origin';
      iframe.style.cssText = 'flex:1;border:none;width:100%;';
      wrap.appendChild(iframe);
      appPane.appendChild(wrap);
    }
  }

  function renderUsageChart(sessions7d) {
    if (!sessions7d || !sessions7d.length) return '';
    const maxSec = Math.max(...sessions7d.map(d => d.duration_sec), 1);
    const barW = 24, gap = 4, h = 48;
    const totalW = sessions7d.length * (barW + gap) - gap;
    const bars = sessions7d.map((d, i) => {
      const barH = Math.max((d.duration_sec / maxSec) * h, d.duration_sec > 0 ? 3 : 0);
      const x = i * (barW + gap);
      const y = h - barH;
      const fill = d.duration_sec > 0 ? '#0066FF' : '#1a1a1a';
      const dayLabel = d.date.slice(5);
      return `<rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="3" fill="${fill}" opacity="0.8"/>
              <text x="${x + barW / 2}" y="${h + 14}" text-anchor="middle" fill="#555" font-size="9">${dayLabel}</text>`;
    }).join('');
    return `<svg width="${totalW}" height="${h + 18}" viewBox="0 0 ${totalW} ${h + 18}">${bars}</svg>`;
  }

  function formatDuration(sec) {
    if (!sec || sec < 60) return '0m';
    if (sec < 3600) return Math.floor(sec / 60) + 'm';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return h + 'h ' + (m ? m + 'm' : '');
  }

  function timeAgo(isoStr) {
    if (!isoStr) return '';
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
  }

  function renderExternalCombined(tool) {
    const isInstalled = state.installedSet.has(tool.id);
    const slug = tool.slug || '';

    stopRunningPoll();

    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:absolute;inset:0;overflow-y:auto;padding:24px;';

    let installType = 'external';
    try {
      const meta = typeof tool.install_meta === 'string' ? JSON.parse(tool.install_meta) : tool.install_meta;
      if (meta && meta.type) installType = meta.type;
    } catch (e) {}

    wrap.innerHTML = `
      <div style="display:flex;gap:14px;align-items:flex-start;margin-bottom:20px;">
        <div style="font-size:28px;width:48px;height:48px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:12px;flex-shrink:0;">${esc(tool.icon || '⊞')}</div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <h2 style="margin:0;font-size:18px;font-weight:700;">${esc(tool.name)}</h2>
            <span style="font-size:10px;padding:2px 8px;border-radius:4px;background:rgba(255,255,255,0.06);color:#888;text-transform:uppercase;letter-spacing:0.5px;">${esc(installType)}</span>
          </div>
          <p style="margin:3px 0 0;color:rgba(255,255,255,0.5);font-size:13px;">${esc(tool.tagline || '')}</p>
        </div>
        <div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">
          <div style="display:flex;align-items:center;gap:6px;">
            <span id="cp-status-dot" class="cp-dot stopped"></span>
            <span id="cp-status-label" style="font-size:12px;"><span style="color:#555;">Checking...</span></span>
          </div>
          <button id="cp-primary-btn" data-action="${isInstalled ? 'launch' : 'install'}"
            style="background:#0066FF;color:white;border:none;padding:7px 16px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">
            ${isInstalled ? 'Launch' : 'Install'}
          </button>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
        <div id="cp-usage-card" style="background:#141414;border:1px solid #2a2a2a;border-radius:10px;padding:16px;">
          <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:12px;">Your usage</div>
          <div id="cp-usage-content" style="color:#555;font-size:12px;">Loading...</div>
        </div>
        <div id="cp-team-card" style="background:#141414;border:1px solid #2a2a2a;border-radius:10px;padding:16px;">
          <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:12px;">Team</div>
          <div id="cp-team-content" style="color:#555;font-size:12px;">Loading...</div>
          <!-- Future: add heartbeat system for live presence. See VISION.md social features roadmap. -->
        </div>
      </div>

      <div id="cp-update-section"></div>
      <div id="cp-coinstalls" style="margin-bottom:16px;"></div>

      <div style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap;">
        <button id="cp-reveal" style="background:#1a1a1a;border:1px solid #2a2a2a;color:#ccc;padding:7px 14px;border-radius:6px;font-size:11px;cursor:pointer;">Show in Finder</button>
        ${tool.source_url ? `<a href="${esc(tool.source_url)}" target="_blank" rel="noopener" style="background:#1a1a1a;border:1px solid #2a2a2a;color:#ccc;padding:7px 14px;border-radius:6px;font-size:11px;cursor:pointer;text-decoration:none;">View source</a>` : ''}
        <button id="cp-uninstall" style="background:#1a1a1a;border:1px solid #2a2a2a;color:#888;padding:7px 14px;border-radius:6px;font-size:11px;cursor:pointer;">Uninstall</button>
      </div>

      <details style="margin-bottom:20px;">
        <summary style="font-size:11px;color:#888;cursor:pointer;text-transform:uppercase;letter-spacing:0.5px;">About</summary>
        <div style="margin-top:10px;font-size:13px;color:rgba(255,255,255,0.6);line-height:1.6;white-space:pre-wrap;">${esc(tool.description || 'No description available.')}</div>
        <div style="margin-top:8px;font-size:11px;color:#555;">by ${esc(tool.author_name || 'Unknown')}</div>
      </details>

      <div style="font-size:11px;color:rgba(255,255,255,0.4);border-top:1px solid #1a1a1a;padding-top:12px;">
        Forge monitors: process name only · Not tracked: window titles, URLs, keystrokes
        <a href="#" id="cp-privacy-link" style="color:rgba(255,255,255,0.3);margin-left:6px;">Privacy details</a>
      </div>
    `;

    if (!document.getElementById('cp-dot-style')) {
      const style = document.createElement('style');
      style.id = 'cp-dot-style';
      style.textContent = '.cp-dot{width:8px;height:8px;border-radius:50%;display:inline-block}.cp-dot.running{background:#22c55e;box-shadow:0 0 4px #22c55e;animation:cp-pulse 2s ease-in-out infinite}.cp-dot.stopped{background:#444}@keyframes cp-pulse{0%,100%{opacity:1}50%{opacity:.5}}';
      document.head.appendChild(style);
    }

    appPane.appendChild(wrap);

    // Wire primary button
    wrap.querySelector('#cp-primary-btn').addEventListener('click', async (e) => {
      const btn = e.target;
      const action = btn.dataset.action;
      if (action === 'install') {
        selectApp(tool);
        return;
      }
      btn.disabled = true;
      btn.textContent = 'Opening…';
      try {
        await fetch('/api/forge-agent/launch', {
          method: 'POST',
          headers: { ...authHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ app_slug: slug, app_name: tool.name }),
          signal: AbortSignal.timeout(5000),
        });
        btn.textContent = '● Focus';
        btn.style.background = 'rgba(34,197,94,0.15)';
        btn.style.color = '#22c55e';
        btn.style.border = '1px solid rgba(34,197,94,0.3)';
      } catch (err) {
        btn.textContent = 'Launch';
      }
      btn.disabled = false;
    });

    // Wire Show in Finder
    const revealBtn = wrap.querySelector('#cp-reveal');
    if (revealBtn) {
      revealBtn.addEventListener('click', async () => {
        try {
          const tokenR = await fetch('/api/agent/token');
          const tokenD = await tokenR.json();
          await fetch('http://localhost:4242/launch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Forge-Token': tokenD.token },
            body: JSON.stringify({ app_slug: slug, app_name: tool.name, action: 'reveal' }),
            signal: AbortSignal.timeout(5000),
          });
        } catch (e) {}
      });
    }

    // Wire Uninstall
    const uninstallBtn = wrap.querySelector('#cp-uninstall');
    if (uninstallBtn) {
      uninstallBtn.addEventListener('click', async () => {
        if (!confirm(`Uninstall ${tool.name}?`)) return;
        uninstallBtn.disabled = true;
        uninstallBtn.textContent = 'Removing…';
        try {
          await fetch('/api/forge-agent/uninstall', {
            method: 'POST',
            headers: { ...authHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ slug }),
            signal: AbortSignal.timeout(10000),
          });
          await fetch(`/api/me/items/${tool.id}`, { method: 'DELETE', headers: authHeaders() });
          state.installedSet.delete(tool.id);
          renderList();
          uninstallBtn.textContent = 'Uninstalled';
        } catch (e) {
          uninstallBtn.textContent = 'Uninstall';
          uninstallBtn.disabled = false;
        }
      });
    }

    // Wire Privacy link
    wrap.querySelector('#cp-privacy-link').addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        const r = await fetch('/api/forge-agent/privacy');
        const data = await r.json();
        const modal = document.createElement('div');
        modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:200;display:flex;align-items:center;justify-content:center;padding:24px;';
        modal.innerHTML = `<div style="background:#141414;border:1px solid #2a2a2a;border-radius:12px;max-width:500px;width:100%;padding:24px;max-height:80vh;overflow:auto;">
          <h3 style="margin:0 0 12px;font-size:16px;">Privacy Details</h3>
          <div style="font-size:12px;color:#ccc;line-height:1.6;">
            <p><strong>Scope:</strong> ${esc(data.scope || '')}</p>
            <p><strong>Method:</strong> ${esc(data.method || '')}</p>
            <p><strong>Data collected:</strong></p>
            <ul style="color:#888;margin:4px 0 12px;">${(data.data_collected || []).map(d => '<li>' + esc(d) + '</li>').join('')}</ul>
            <p><strong>Data NOT collected:</strong></p>
            <ul style="color:#888;margin:4px 0 12px;">${(data.data_not_collected || []).map(d => '<li>' + esc(d) + '</li>').join('')}</ul>
            <p style="color:#555;">Storage: ${esc(data.storage || '')}</p>
          </div>
          <button onclick="this.closest('div[style*=fixed]').remove()" style="margin-top:12px;background:#1a1a1a;border:1px solid #2a2a2a;color:#ccc;padding:7px 16px;border-radius:6px;font-size:12px;cursor:pointer;">Close</button>
        </div>`;
        modal.addEventListener('click', (ev) => { if (ev.target === modal) modal.remove(); });
        document.body.appendChild(modal);
      } catch (err) {}
    });

    // Async: Load usage
    fetch(`/api/forge-agent/usage?slug=${encodeURIComponent(slug)}`).then(r => r.json()).then(usage => {
      const el = wrap.querySelector('#cp-usage-content');
      if (!el) return;
      if (!usage.session_count_7d) {
        el.innerHTML = '<span style="color:#555;">Not used yet — click Launch above</span>';
        return;
      }
      const chart = renderUsageChart(usage.sessions_7d);
      const lastOpened = usage.last_opened ? timeAgo(usage.last_opened) : 'unknown';
      el.innerHTML = `${chart}<div style="margin-top:10px;font-size:12px;color:#aaa;">${formatDuration(usage.total_sec_7d)} this week · ${usage.session_count_7d} sessions · last opened ${lastOpened}</div>`;
    }).catch(() => {
      const el = wrap.querySelector('#cp-usage-content');
      if (el) el.innerHTML = '<span style="color:#555;">Usage data unavailable</span>';
    });

    // Async: Load team/social
    fetch(`/api/tools/${tool.id}/social`, { headers: authHeaders() }).then(r => r.json()).then(social => {
      const el = wrap.querySelector('#cp-team-content');
      if (!el) return;
      if (!social.team_install_count) {
        el.innerHTML = '<span style="color:#555;">Be the first on your team to use this</span>';
        return;
      }
      let html = `<div style="font-size:14px;color:#e0e0e0;font-weight:500;margin-bottom:6px;">${social.team_install_count} teammate${social.team_install_count > 1 ? 's' : ''} installed this</div>`;
      if (social.role_concentration) {
        const rc = social.role_concentration;
        html += `<div style="font-size:12px;color:#888;margin-bottom:4px;">Popular with ${esc(rc.role)}s — ${rc.count} of ${rc.total} installs from ${esc(rc.role)}s</div>`;
      }
      if (social.installs_this_week > 0) {
        html += `<div style="font-size:12px;color:#888;">${social.installs_this_week} new install${social.installs_this_week > 1 ? 's' : ''} this week</div>`;
      }
      el.innerHTML = html;
    }).catch(() => {
      const el = wrap.querySelector('#cp-team-content');
      if (el) el.innerHTML = '<span style="color:#555;">Team data unavailable</span>';
    });

    // Async: Load co-installs
    fetch(`/api/tools/${tool.id}/coinstalls`, { headers: authHeaders() }).then(r => r.json()).then(data => {
      const el = wrap.querySelector('#cp-coinstalls');
      if (!el || !data.coinstalls || !data.coinstalls.length) return;
      el.innerHTML = `
        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px;">People who use ${esc(tool.name)} also use</div>
        <div style="display:flex;gap:10px;">
          ${data.coinstalls.map(ci => `
            <div class="ci-card" data-slug="${esc(ci.slug)}" style="flex:1;background:#141414;border:1px solid #2a2a2a;border-radius:8px;padding:12px;cursor:pointer;opacity:0.8;transition:opacity 0.15s,border-color 0.15s;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                <span style="font-size:16px;">${esc(ci.icon || '⊞')}</span>
                <span style="font-size:13px;font-weight:600;color:#f0f0f0;">${esc(ci.name)}</span>
              </div>
              <div style="font-size:10px;color:#555;">used by ${ci.overlap} others</div>
            </div>
          `).join('')}
        </div>`;
      el.querySelectorAll('.ci-card').forEach(card => {
        card.addEventListener('mouseenter', () => { card.style.opacity = '1'; card.style.borderColor = '#0066FF'; });
        card.addEventListener('mouseleave', () => { card.style.opacity = '0.8'; card.style.borderColor = '#2a2a2a'; });
        card.addEventListener('click', () => {
          const ciSlug = card.dataset.slug;
          const ciTool = state.items.find(t => t.slug === ciSlug);
          if (ciTool) selectApp(ciTool);
        });
      });
    }).catch(() => {});

    // Async: Check updates
    fetch('/api/forge-agent/running', { signal: AbortSignal.timeout(3000) }).then(r => r.json()).then(() => {
      fetch(`/api/forge-agent/updates?slug=${encodeURIComponent(slug)}`, { signal: AbortSignal.timeout(5000) })
        .then(r => r.ok ? r.json() : null)
        .then(upd => {
          if (!upd || !upd.updates || !upd.updates.length) return;
          const update = upd.updates[0];
          const section = wrap.querySelector('#cp-update-section');
          if (!section) return;
          section.innerHTML = `
            <div style="background:#141414;border:1px solid #2a2a2a;border-left:3px solid #d97706;border-radius:10px;padding:16px;margin-bottom:16px;">
              <div style="font-size:10px;color:#d97706;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">Available update</div>
              <div style="font-size:13px;color:#e0e0e0;">${esc(update.detail || 'A newer version is available')}</div>
            </div>`;
        }).catch(() => {});
    }).catch(() => {});

    if (isInstalled) startRunningPoll(slug);
  }

  function renderExternalDetail(tool) {
    const screenshots = parseScreenshots(tool.screenshots);
    const detail = document.createElement('div');
    detail.className = 'app-detail';
    const isInstalled = state.installedSet.has(tool.id);

    let screenshotHtml = '';
    if (screenshots.length) {
      screenshotHtml = `<div style="display:flex;gap:10px;overflow-x:auto;padding:4px 0 14px;margin-bottom:14px;">
        ${screenshots.map(url => `<img src="${esc(url)}" style="max-height:280px;border-radius:8px;border:1px solid #2a2a2a;flex-shrink:0;" loading="lazy" onerror="this.style.display='none'">`).join('')}
      </div>`;
    }

    // Primary action: one-click install via forge-agent
    let installHtml = '';
    if (tool.install_command) {
      installHtml = `
        <div style="background:#0d1a2e;border:1px solid #1e3a5c;border-radius:10px;padding:18px;margin:16px 0;">
          ${isInstalled ? `
            <div style="display:flex;align-items:center;gap:10px;">
              <span style="font-size:22px;">✓</span>
              <div>
                <div style="font-size:15px;font-weight:600;color:#1a7f4b;">Installed</div>
                <div style="font-size:12px;color:#888;">Open from your Applications folder or My Forge.</div>
              </div>
            </div>
          ` : `
            <button id="detail-install-btn" style="background:#0066FF;color:white;border:none;padding:14px 0;border-radius:8px;cursor:pointer;font-size:15px;font-weight:600;width:100%;margin-bottom:12px;">
              Install ${esc(tool.name)}
            </button>
            <div id="install-status" style="display:none;margin-bottom:10px;">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                <div id="install-spinner" style="width:18px;height:18px;border:2px solid #2a2a2a;border-top-color:#0066FF;border-radius:50%;animation:spin 0.8s linear infinite;flex-shrink:0;"></div>
                <div id="install-label" style="font-size:14px;color:#e0e0e0;font-weight:500;">Downloading...</div>
              </div>
              <div id="install-bar-wrap" style="background:#1a1a1a;border-radius:4px;height:6px;overflow:hidden;margin-bottom:6px;">
                <div id="install-bar" style="background:#0066FF;height:100%;width:0%;transition:width 0.3s;border-radius:4px;"></div>
              </div>
              <div id="install-progress" style="font-size:11px;color:#666;font-family:ui-monospace,Menlo,monospace;max-height:100px;overflow-y:auto;line-height:1.5;"></div>
            </div>
            <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
            <div id="agent-fallback" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid #1e3a5c;">
              <div style="font-size:12px;color:#888;margin-bottom:8px;">Forge Agent not running. Install it once to enable one-click installs:</div>
              <pre style="margin:0 0 10px;color:#c3e88d;font-family:ui-monospace,Menlo,monospace;font-size:12px;background:#0d0d0d;border:1px solid #2a2a2a;border-radius:6px;padding:10px;cursor:pointer;user-select:all;"
                   onclick="navigator.clipboard.writeText(this.innerText)" title="Click to copy">bash forge_agent/install.sh</pre>
              <div style="font-size:11px;color:#666;">Or run the app's install command manually:</div>
              <pre style="margin:4px 0 0;color:#c3e88d;font-family:ui-monospace,Menlo,monospace;font-size:11px;background:#0d0d0d;border:1px solid #2a2a2a;border-radius:6px;padding:8px;cursor:pointer;user-select:all;white-space:pre-wrap;"
                   onclick="navigator.clipboard.writeText(this.innerText)">${esc(tool.install_command)}</pre>
            </div>
          `}
        </div>`;
    }

    let socialHtml = '<div id="detail-social" style="display:flex;gap:14px;font-size:12px;color:#888;margin-bottom:14px;"></div>';

    // ── Parse features from **bold** lines in description ──
    const desc = tool.description || '';
    const featureLines = desc.split('\n').filter(l => l.trim().startsWith('**'));
    let featuresHtml = '';
    if (featureLines.length >= 2) {
      featuresHtml = `<div style="margin:16px 0 20px;">
        ${featureLines.map(line => {
          const m = line.match(/\*\*(.+?)\*\*\s*[—–\-]\s*(.*)/);
          if (m) return `<div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">
            <span style="color:#0066FF;font-size:14px;flex-shrink:0;margin-top:2px;">◆</span>
            <div><div style="font-size:14px;color:#f0f0f0;font-weight:600;">${esc(m[1])}</div>
            <div style="font-size:13px;color:rgba(255,255,255,0.5);margin-top:2px;">${esc(m[2])}</div></div></div>`;
          return '';
        }).join('')}</div>`;
    } else {
      featuresHtml = `<div class="ad-desc" style="margin:12px 0 16px;white-space:pre-wrap;">${esc(desc)}</div>`;
    }

    // ── Stars + license ──
    const stars = tool.github_stars;
    const license = tool.github_license;
    let metaLine = '';
    if (stars || license) {
      metaLine = `<div style="display:flex;gap:12px;font-size:12px;color:#888;margin-bottom:12px;flex-wrap:wrap;">
        ${stars ? `<span>⭐ ${Number(stars).toLocaleString()} stars</span>` : ''}
        ${license ? `<span style="background:rgba(255,255,255,0.06);padding:2px 8px;border-radius:3px;">${esc(license)}</span>` : ''}
      </div>`;
    }

    detail.innerHTML = `
      <div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:16px;">
        <div style="font-size:36px;width:64px;height:64px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:14px;flex-shrink:0;">${esc(tool.icon || '⊞')}</div>
        <div style="flex:1;min-width:0;">
          <h2 style="margin:0 0 4px;font-size:22px;font-weight:700;">${esc(tool.name)}</h2>
          <p style="margin:0 0 6px;color:rgba(255,255,255,0.6);font-size:14px;">${esc(tool.tagline || '')}</p>
          <div style="font-size:12px;color:#888;">by ${esc(tool.author_name || 'Unknown')}</div>
        </div>
      </div>
      ${metaLine}
      ${screenshotHtml}
      ${featuresHtml}
      ${installHtml}
      ${tool.source_url ? `<a href="${esc(tool.source_url)}" target="_blank" rel="noopener" style="color:rgba(255,255,255,0.4);font-size:12px;text-decoration:none;">View source ↗</a>` : ''}
      <div id="detail-social" style="display:flex;gap:14px;font-size:12px;color:#888;margin:14px 0;"></div>
      <div id="detail-badges"></div>`;

    appPane.appendChild(detail);

    // Check agent status on render and show/hide fallback immediately
    (async function checkAgent() {
      const fallbackEl = detail.querySelector('#agent-fallback');
      try {
        await fetch('http://localhost:4242/health', {signal: AbortSignal.timeout(2000)});
        // Agent is up — hide fallback
        if (fallbackEl) fallbackEl.style.display = 'none';
      } catch (e) {
        // Agent down — show fallback panel
        if (fallbackEl) fallbackEl.style.display = 'block';
      }
    })();

    // Wire the detail Install button
    const detailBtn = detail.querySelector('#detail-install-btn');
    if (detailBtn) {
      detailBtn.addEventListener('click', async () => {
        const fallback = detail.querySelector('#agent-fallback');
        detailBtn.disabled = true;
        detailBtn.textContent = '⏳ Installing...';

        const statusWrap = detail.querySelector('#install-status');
        const progress = detail.querySelector('#install-progress');
        const label = detail.querySelector('#install-label');
        const bar = detail.querySelector('#install-bar');
        const spinner = detail.querySelector('#install-spinner');

        try {
          // Check forge-agent
          const healthR = await fetch('http://localhost:4242/health', {signal: AbortSignal.timeout(2000)});
          if (!healthR.ok) throw new Error('agent_down');
          const tokenR = await fetch('/api/agent/token');
          const tokenD = await tokenR.json();
          if (!tokenD.token) throw new Error('no_token');

          // Show progress UI
          if (statusWrap) statusWrap.style.display = 'block';
          if (label) label.textContent = 'Starting install...';

          // Build structured install body from install_meta
          let installBody2;
          try {
            const meta = typeof tool.install_meta === 'string' ? JSON.parse(tool.install_meta) : tool.install_meta;
            installBody2 = (meta && meta.type) ? { ...meta, name: tool.slug } : { type: 'command', command: tool.install_command, name: tool.slug };
          } catch (x) {
            installBody2 = { type: 'command', command: tool.install_command, name: tool.slug };
          }

          const r = await fetch('http://localhost:4242/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Forge-Token': tokenD.token },
            body: JSON.stringify(installBody2),
          });
          const reader = r.body.getReader();
          const decoder = new TextDecoder();
          let buf = '';
          let lineCount = 0;

          while (true) {
            const chunk = await reader.read();
            if (chunk.done) break;
            buf += decoder.decode(chunk.value, { stream: true });
            // Split on real newlines (not escaped)
            const parts = buf.split('\n');
            buf = parts.pop();
            for (const part of parts) {
              if (!part.startsWith('data: ')) continue;
              try {
                const evt = JSON.parse(part.slice(6));
                lineCount++;

                // Update visual progress
                if (label) {
                  if (evt.type === 'installing') label.textContent = 'Downloading...';
                  else if (evt.type === 'progress') label.textContent = evt.message || 'Installing...';
                  else if (evt.type === 'installed') label.textContent = 'Installed!';
                  else if (evt.type === 'error') label.textContent = 'Failed';
                }
                // Animate progress bar (indeterminate since we don't know total)
                if (bar) bar.style.width = Math.min(5 + lineCount * 4, 95) + '%';
                // Append to log
                if (progress && evt.message) {
                  progress.textContent += evt.message + '\n';
                  progress.scrollTop = progress.scrollHeight;
                }

                if (evt.type === 'installed') {
                  if (bar) bar.style.width = '100%';
                  if (bar) bar.style.background = '#1a7f4b';
                  if (spinner) { spinner.style.animation = 'none'; spinner.style.borderColor = '#1a7f4b'; spinner.style.borderTopColor = '#1a7f4b'; }
                  detailBtn.textContent = '✓ Installed';
                  detailBtn.style.background = '#1a7f4b';
                  // Add to shelf with installed flag
                  await fetch('/api/me/items/' + tool.id, {
                    method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({installed: true}),
                  });
                  state.installedSet.add(tool.id);
                  const cardBtn = listEl.querySelector('[data-id="' + tool.id + '"][data-act="install"]');
                  if (cardBtn) { cardBtn.textContent = '✓'; cardBtn.classList.add('done'); }
                  updateBarInstallState(tool);
                } else if (evt.type === 'error') {
                  if (bar) bar.style.background = '#c62828';
                  detailBtn.textContent = 'Install ' + esc(tool.name);
                  detailBtn.disabled = false;
                }
              } catch (x) {}
            }
          }
        } catch (e) {
          // Forge-agent not available
          detailBtn.textContent = 'Install ' + esc(tool.name);
          detailBtn.disabled = false;
          if (fallback) fallback.style.display = 'block';
          if (statusWrap) statusWrap.style.display = 'none';
        }
      });
    }

    // Async load social
    fetch(`/api/tools/${tool.id}/social`, { headers: authHeaders() }).then(r => r.json()).then(s => {
      const el = detail.querySelector('#detail-social');
      if (!el) return;
      const parts = [];
      if (s.team_install_count > 0) parts.push(`<span style="color:#0066FF;font-weight:600;">+${s.team_install_count} from your team</span>`);
      parts.push(`${s.install_count || 0} installs`);
      if (s.avg_rating) parts.push(`★ ${Number(s.avg_rating).toFixed(1)}`);
      if (s.review_count) parts.push(`${s.review_count} reviews`);
      el.innerHTML = parts.join(' · ');
    }).catch(() => {});

    // Async load inspection
    fetch(`/api/tools/${tool.id}/inspection`).then(r => r.json()).then(j => {
      const wrap = detail.querySelector('#detail-badges');
      if (!wrap || !j.badges || !j.badges.length) return;
      wrap.innerHTML = '<h3 style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 10px;">Behind the scenes</h3>'
        + j.badges.map(b => {
          const color = b.tone === 'warn' ? '#FF9800' : b.tone === 'ok' ? '#4CAF50' : b.tone === 'info' ? '#0066FF' : '#888';
          return `<div class="badge-row">
            <span class="bi" style="color:${color}">${esc(b.icon)}</span>
            <div><div class="bl">${esc(b.label)}</div>
            ${b.detail ? `<div class="bd">${esc(b.detail)}</div>` : ''}</div>
          </div>`;
        }).join('');
    }).catch(() => {});
  }

  function parseScreenshots(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    try { return JSON.parse(raw); } catch (e) { return []; }
  }

  // ---- Trending / Discovery ----

  let trendingData = { role_trending: [], team_popular: [] };

  async function loadTrending() {
    try {
      const r = await fetch('/api/team/trending', { headers: authHeaders() });
      trendingData = await r.json();
    } catch (e) {
      trendingData = { role_trending: [], team_popular: [] };
    }
  }

  function renderRecs() {
    const wrap = document.getElementById('recs');
    const list = document.getElementById('recs-list');
    if (!wrap || !list) return;

    const hasRole = trendingData.role_trending.length > 0;
    const hasTeam = trendingData.team_popular.length > 0;

    if (!hasRole && !hasTeam) {
      wrap.style.display = 'none';
      return;
    }
    wrap.style.display = '';

    let html = '';
    if (hasRole) {
      html += `<div style="grid-column:1/-1;font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:1.2px;font-weight:500;">Trending with ${esc(trendingData.role || 'your role')}s this week</div>`;
      html += trendingData.role_trending.map(r => `
        <div class="rec-chip" data-slug="${esc(r.slug)}">
          <span class="rec-icon">${esc(r.icon || '⊞')}</span>
          <span class="rec-name">${esc(r.name)}</span>
          <span class="rec-why">${esc(r.reason || '')}</span>
        </div>
      `).join('');
    }
    if (hasTeam) {
      html += `<div style="grid-column:1/-1;font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:1.2px;font-weight:500;${hasRole ? 'margin-top:8px;' : ''}">Popular on your team</div>`;
      html += trendingData.team_popular.map(r => `
        <div class="rec-chip" data-slug="${esc(r.slug)}">
          <span class="rec-icon">${esc(r.icon || '⊞')}</span>
          <span class="rec-name">${esc(r.name)}</span>
          <span class="rec-why">${esc(r.reason || '')}</span>
        </div>
      `).join('');
    }

    list.innerHTML = html;
    list.querySelectorAll('.rec-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const slug = chip.dataset.slug;
        const tool = state.items.find(t => t.slug === slug);
        if (tool) selectApp(tool);
      });
    });
  }

  // ---- Render all ----

  function renderAll() { renderFilters(); renderRecs(); renderList(); }

  // ---- Init ----

  // ---- Role-aware homepage ----

  async function checkOnboarding() {
    // Fast path: localStorage flag means we've already onboarded on this device
    try {
      const cached = localStorage.getItem('forge_onboarded');
      if (cached === '1') {
        state.userRole = localStorage.getItem('forge_user_role') || null;
        return;
      }
    } catch (e) {}
    // Slow path: check the server
    try {
      const r = await fetch('/api/me/context', { headers: authHeaders() });
      const ctx = await r.json();
      if (ctx.user && ctx.user.onboarded) {
        state.userRole = ctx.user.role;
        try {
          localStorage.setItem('forge_onboarded', '1');
          localStorage.setItem('forge_user_role', ctx.user.role || '');
        } catch (e) {}
        return;
      }
    } catch (e) {}
    // Not onboarded — show role picker
    await showRolePicker();
  }

  function showRolePicker() {
    return new Promise((resolve) => {
      const roles = ['AE', 'SDR', 'RevOps', 'CS', 'Product', 'Eng', 'Recruiter', 'Other'];
      const overlay = document.createElement('div');
      overlay.id = 'role-picker-modal';
      overlay.className = 'role-picker-overlay';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.9);z-index:2000;display:flex;align-items:center;justify-content:center;padding:24px;';
      overlay.innerHTML = `
        <div style="background:#141414;border:1px solid #2a2a2a;border-radius:14px;padding:32px;max-width:480px;width:100%;text-align:center;">
          <div style="font-size:32px;margin-bottom:12px;">⚒</div>
          <h2 style="margin:0 0 6px;font-size:20px;color:#f0f0f0;">Welcome to Forge</h2>
          <p style="color:#888;margin:0 0 24px;font-size:14px;">What's your role? We'll show you the most relevant apps first.</p>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            ${roles.map(r => `<button class="role-btn" data-role="${r}" style="background:#1a1a1a;border:1px solid #2a2a2a;color:#e0e0e0;padding:12px;border-radius:8px;cursor:pointer;font-size:14px;font-weight:500;transition:border-color 0.15s;"
              onmouseover="this.style.borderColor='#0066FF'" onmouseout="this.style.borderColor='#2a2a2a'">${r}</button>`).join('')}
          </div>
        </div>`;
      document.body.appendChild(overlay);
      overlay.querySelectorAll('.role-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const role = btn.dataset.role;
          state.userRole = role;
          try {
            localStorage.setItem('forge_onboarded', '1');
            localStorage.setItem('forge_user_role', role);
          } catch (x) {}
          await fetch('/api/me/role', {
            method: 'POST',
            headers: { ...authHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ role }),
          });
          overlay.remove();
          resolve();
        });
      });
    });
  }

  async function init() {
    getUserId();
    await checkOnboarding();
    await Promise.all([loadItems(), loadUserState(), loadTrending()]);
    renderAll();

    // Search
    let t;
    searchEl.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(async () => { state.search = searchEl.value.trim(); await loadItems(); renderAll(); }, 200);
    });

    // Keyboard
    document.addEventListener('keydown', e => {
      // Don't intercept when typing in search
      const inSearch = document.activeElement === searchEl;

      if (e.key === 'Escape') {
        if (state.selectedId) {
          state.selectedId = null;
          listEl.querySelectorAll('.c-card').forEach(c => c.classList.remove('selected'));
          appBar.style.display = 'none';
          const prev = appPane.querySelector('iframe, .app-detail, div[style]');
          if (prev) prev.remove();
          emptyState.style.display = 'flex';
        }
        if (inSearch) searchEl.blur();
        return;
      }
      if (e.key === '/' && !inSearch) {
        e.preventDefault();
        searchEl.focus();
        return;
      }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (inSearch && e.key === 'ArrowDown') { searchEl.blur(); }
        const active = document.activeElement;
        if (!listEl.contains(active) && active !== listEl && active !== searchEl) return;
        e.preventDefault();
        const cards = Array.from(listEl.querySelectorAll('.c-card'));
        if (!cards.length) return;
        let idx = cards.findIndex(c => parseInt(c.dataset.id) === state.selectedId);
        idx = e.key === 'ArrowDown' ? Math.min(idx + 1, cards.length - 1) : Math.max(idx - 1, 0);
        if (idx < 0) idx = 0;
        const tool = state.items.find(t => t.id === parseInt(cards[idx].dataset.id));
        if (tool) selectApp(tool);
        cards[idx].scrollIntoView({ block: 'nearest' });
        cards[idx].focus();
        return;
      }
      // Enter: launch if installed, install if not
      if (e.key === 'Enter' && !inSearch && state.selectedId) {
        e.preventDefault();
        const tool = state.items.find(t => t.id === state.selectedId);
        if (!tool) return;
        const isInstalled = state.installedSet.has(tool.id);
        if (isInstalled && tool.delivery === 'external') {
          // Launch via forge-agent
          fetch('/api/forge-agent/launch', {
            method: 'POST',
            headers: { ...authHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ app_slug: tool.slug, app_name: tool.name }),
          }).catch(() => {});
        } else {
          const btn = listEl.querySelector(`[data-id="${tool.id}"][data-act="install"]`);
          if (btn) handleInstall(tool, btn);
        }
        return;
      }
      // I key: install (skip launch)
      if ((e.key === 'i' || e.key === 'I') && !inSearch && state.selectedId) {
        const tool = state.items.find(t => t.id === state.selectedId);
        if (!tool || state.installedSet.has(tool.id)) return;
        e.preventDefault();
        const btn = listEl.querySelector(`[data-id="${tool.id}"][data-act="install"]`);
        if (btn) handleInstall(tool, btn);
        return;
      }
    });

    // Keyboard hints bar
    const hintsBar = document.createElement('div');
    hintsBar.style.cssText = 'padding:6px 16px;font-size:10px;color:rgba(255,255,255,0.25);border-top:1px solid #1a1a1a;flex-shrink:0;letter-spacing:0.3px;';
    hintsBar.textContent = '↑↓ navigate · Enter launch · I install · / search · Esc clear';
    document.querySelector('.cat-col').appendChild(hintsBar);

    // Resize handle
    const catCol = document.querySelector('.cat-col');
    const handle = document.getElementById('resize-handle');
    const MIN_W = 280, MAX_W = 500;
    try { const w = parseInt(localStorage.getItem(STORAGE_CAT_WIDTH)); if (w >= MIN_W && w <= MAX_W) catCol.style.width = w + 'px'; } catch (e) {}

    let dragging = false;
    handle.addEventListener('mousedown', e => {
      e.preventDefault(); dragging = true;
      handle.classList.add('dragging');
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      const cover = document.createElement('div');
      cover.id = 'iframe-cover';
      cover.style.cssText = 'position:fixed;inset:0;z-index:9999;cursor:col-resize;';
      document.body.appendChild(cover);
    });
    document.addEventListener('mousemove', e => {
      if (!dragging) return;
      catCol.style.width = Math.max(MIN_W, Math.min(MAX_W, e.clientX)) + 'px';
    });
    document.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false; handle.classList.remove('dragging');
      document.body.style.cursor = ''; document.body.style.userSelect = '';
      const cover = document.getElementById('iframe-cover');
      if (cover) cover.remove();
      try { localStorage.setItem(STORAGE_CAT_WIDTH, parseInt(catCol.style.width)); } catch (e) {}
    });
  }

  init();
})();
