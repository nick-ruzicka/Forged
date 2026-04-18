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

    // Action label: external = "Install", embedded = "Open"
    const actionLabel = isInstalled ? '✓' : (isExt ? 'Install' : 'Open');
    const actionClass = isInstalled ? 'c-action done' : 'c-action';

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

    // External apps: load the detail view, then auto-trigger the detail Install button.
    // All progress rendering happens in the detail view — one code path.
    selectApp(tool);

    if (state.installedSet.has(tool.id)) return;

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
    barBtn.textContent = inst ? '✓ Installed' : (tool.delivery === 'external' ? 'Install' : 'Open');
    barBtn.classList.toggle('done', inst);
  }

  // ---- Right pane ----

  function selectApp(tool) {
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

  function renderExternalCombined(tool) {
    const screenshots = parseScreenshots(tool.screenshots);
    const isInstalled = state.installedSet.has(tool.id);
    const hasPreview = !!(tool.app_html);
    const stars = tool.github_stars;
    const license = tool.github_license;

    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:absolute;inset:0;overflow-y:auto;';

    const info = document.createElement('div');
    info.style.cssText = 'padding:20px 24px;';

    // Parse features from **bold** description lines
    const desc = tool.description || '';
    const featureLines = desc.split('\n').filter(l => l.trim().startsWith('**'));
    let featuresHtml = '';
    if (featureLines.length >= 2) {
      featuresHtml = featureLines.map(line => {
        const m = line.match(/\*\*(.+?)\*\*\s*[—–\-]\s*(.*)/);
        if (m) return `<div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;">
          <span style="color:#0066FF;font-size:12px;flex-shrink:0;margin-top:3px;">◆</span>
          <div><span style="font-size:13px;color:#f0f0f0;font-weight:600;">${esc(m[1])}</span>
          <span style="font-size:13px;color:rgba(255,255,255,0.45);"> — ${esc(m[2])}</span></div></div>`;
        return '';
      }).join('');
    } else {
      featuresHtml = `<div style="font-size:13px;color:rgba(255,255,255,0.6);line-height:1.6;white-space:pre-wrap;">${esc(desc)}</div>`;
    }

    // Install CTA
    let installCta = '';
    if (tool.install_command && !isInstalled) {
      installCta = `<button id="detail-install-btn" style="background:#0066FF;color:white;border:none;padding:11px 0;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;width:100%;margin:14px 0 8px;">
        Install ${esc(tool.name)}
      </button>
      <div id="install-status" style="display:none;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
          <div id="install-spinner" style="width:14px;height:14px;border:2px solid #2a2a2a;border-top-color:#0066FF;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
          <div id="install-label" style="font-size:12px;color:#ccc;">Downloading...</div>
        </div>
        <div style="background:#1a1a1a;border-radius:3px;height:3px;overflow:hidden;">
          <div id="install-bar" style="background:#0066FF;height:100%;width:0%;transition:width 0.3s;"></div>
        </div>
        <div id="install-progress" style="font-size:10px;color:#555;font-family:ui-monospace,monospace;max-height:60px;overflow-y:auto;margin-top:4px;"></div>
      </div>
      <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
      <div id="agent-fallback" style="display:none;margin-top:10px;padding-top:10px;border-top:1px solid #222;">
        <pre style="margin:0;color:#c3e88d;font-family:ui-monospace,monospace;font-size:11px;background:#0d0d0d;border:1px solid #222;border-radius:5px;padding:8px;cursor:pointer;user-select:all;white-space:pre-wrap;"
             onclick="navigator.clipboard.writeText(this.innerText)">${esc(tool.install_command)}</pre>
      </div>`;
    } else if (isInstalled) {
      installCta = `<div style="display:flex;align-items:center;gap:8px;margin:12px 0;padding:10px 14px;background:rgba(26,127,75,0.08);border:1px solid rgba(26,127,75,0.2);border-radius:8px;">
        <span style="color:#1a7f4b;font-size:16px;">✓</span>
        <span style="color:#1a7f4b;font-size:13px;font-weight:500;">Installed</span>
      </div>`;
    }

    info.innerHTML = `
      <div style="display:flex;gap:14px;align-items:flex-start;margin-bottom:14px;">
        <div style="font-size:32px;width:56px;height:56px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:12px;flex-shrink:0;">${esc(tool.icon || '⊞')}</div>
        <div style="flex:1;min-width:0;">
          <h2 style="margin:0 0 3px;font-size:20px;font-weight:700;">${esc(tool.name)}</h2>
          <p style="margin:0 0 6px;color:rgba(255,255,255,0.55);font-size:13px;">${esc(tool.tagline || '')}</p>
          <div style="display:flex;gap:10px;align-items:center;font-size:11px;color:#888;flex-wrap:wrap;">
            <span>by ${esc(tool.author_name || 'Unknown')}</span>
            ${stars ? `<span>⭐ ${Number(stars).toLocaleString()}</span>` : ''}
            ${license ? `<span style="background:rgba(255,255,255,0.06);padding:1px 6px;border-radius:3px;font-size:10px;">${esc(license)}</span>` : ''}
            ${tool.source_url ? `<a href="${esc(tool.source_url)}" target="_blank" rel="noopener" style="color:rgba(255,255,255,0.35);text-decoration:none;">Source ↗</a>` : ''}
          </div>
        </div>
      </div>
      <div id="detail-social" style="display:flex;gap:12px;font-size:11px;color:#888;margin-bottom:12px;"></div>
      ${featuresHtml}
      ${installCta}`;

    wrap.appendChild(info);

    // ── Preview iframe below the info ──
    if (hasPreview) {
      const previewLabel = document.createElement('div');
      previewLabel.style.cssText = 'padding:8px 24px;font-size:10px;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:0.8px;border-top:1px solid #222;border-bottom:1px solid #1a1a1a;background:#111;';
      previewLabel.textContent = 'Interactive preview';
      wrap.appendChild(previewLabel);

      const iframe = document.createElement('iframe');
      iframe.src = `/apps/${encodeURIComponent(tool.slug)}?user=${encodeURIComponent(getUserId())}&preview=true`;
      iframe.sandbox = 'allow-scripts allow-forms allow-modals allow-downloads allow-same-origin';
      iframe.style.cssText = 'width:100%;height:500px;border:none;';
      wrap.appendChild(iframe);
    }

    appPane.appendChild(wrap);

    // ── Wire install button + agent check + social load ──
    (async function() {
      // Agent check
      const fallback = wrap.querySelector('#agent-fallback');
      try {
        await fetch('http://localhost:4242/health', {signal: AbortSignal.timeout(2000)});
        if (fallback) fallback.style.display = 'none';
      } catch (e) {
        if (fallback) fallback.style.display = 'block';
      }
    })();

    // Install button
    const detailBtn = wrap.querySelector('#detail-install-btn');
    if (detailBtn) {
      detailBtn.addEventListener('click', async () => {
        const fallback = wrap.querySelector('#agent-fallback');
        detailBtn.disabled = true;
        detailBtn.textContent = '⏳ Installing...';
        const statusWrap = wrap.querySelector('#install-status');
        const progress = wrap.querySelector('#install-progress');
        const label = wrap.querySelector('#install-label');
        const bar = wrap.querySelector('#install-bar');

        try {
          const healthR = await fetch('http://localhost:4242/health', {signal: AbortSignal.timeout(2000)});
          if (!healthR.ok) throw new Error('agent_down');
          const tokenR = await fetch('/api/agent/token');
          const tokenD = await tokenR.json();
          if (!tokenD.token) throw new Error('no_token');
          if (statusWrap) statusWrap.style.display = 'block';
          if (label) label.textContent = 'Starting...';

          let installBody;
          try {
            const meta = typeof tool.install_meta === 'string' ? JSON.parse(tool.install_meta) : tool.install_meta;
            installBody = (meta && meta.type) ? { ...meta, name: tool.slug } : { type: 'command', command: tool.install_command, name: tool.slug };
          } catch (x) {
            installBody = { type: 'command', command: tool.install_command, name: tool.slug };
          }

          const r = await fetch('http://localhost:4242/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Forge-Token': tokenD.token },
            body: JSON.stringify(installBody),
          });
          const reader = r.body.getReader();
          const decoder = new TextDecoder();
          let buf = '', lineCount = 0;
          while (true) {
            const chunk = await reader.read();
            if (chunk.done) break;
            buf += decoder.decode(chunk.value, { stream: true });
            const parts = buf.split('\n'); buf = parts.pop();
            for (const part of parts) {
              if (!part.startsWith('data: ')) continue;
              try {
                const evt = JSON.parse(part.slice(6)); lineCount++;
                if (label) label.textContent = evt.message || 'Installing...';
                if (bar) bar.style.width = Math.min(5 + lineCount * 4, 95) + '%';
                if (progress && evt.message) { progress.textContent += evt.message + '\n'; progress.scrollTop = progress.scrollHeight; }
                if (evt.type === 'installed') {
                  if (bar) { bar.style.width = '100%'; bar.style.background = '#1a7f4b'; }
                  detailBtn.textContent = '✓ Installed'; detailBtn.style.background = '#1a7f4b';
                  await fetch('/api/me/items/' + tool.id, { method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({installed: true}) });
                  state.installedSet.add(tool.id);
                  const cardBtn = listEl.querySelector('[data-id="' + tool.id + '"][data-act="install"]');
                  if (cardBtn) { cardBtn.textContent = '✓'; cardBtn.classList.add('done'); }
                  updateBarInstallState(tool);
                } else if (evt.type === 'error') {
                  if (bar) bar.style.background = '#c62828';
                  detailBtn.textContent = 'Install ' + esc(tool.name); detailBtn.disabled = false;
                }
              } catch (x) {}
            }
          }
        } catch (e) {
          detailBtn.textContent = 'Install ' + esc(tool.name); detailBtn.disabled = false;
          if (fallback) fallback.style.display = 'block';
          if (statusWrap) statusWrap.style.display = 'none';
        }
      });
    }

    // Social
    fetch(`/api/tools/${tool.id}/social`, { headers: authHeaders() }).then(r => r.json()).then(s => {
      const el = wrap.querySelector('#detail-social');
      if (!el) return;
      const parts = [];
      if (s.team_install_count > 0) parts.push(`<span style="color:#0066FF;font-weight:600;">+${s.team_install_count} from your team</span>`);
      parts.push(`${s.install_count || 0} installs`);
      if (s.avg_rating) parts.push(`★ ${Number(s.avg_rating).toFixed(1)}`);
      el.innerHTML = parts.join(' · ');
    }).catch(() => {});
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

  // ---- Recommendations ----

  let recommendations = [];

  async function loadRecommendations() {
    try {
      const r = await fetch('/api/me/recommended', { headers: authHeaders() });
      const d = await r.json();
      recommendations = d.items || [];
    } catch (e) { recommendations = []; }
  }

  function renderRecs() {
    const wrap = document.getElementById('recs');
    const list = document.getElementById('recs-list');
    if (!wrap || !list) return;
    if (!recommendations.length) { wrap.style.display = 'none'; return; }
    wrap.style.display = '';
    list.innerHTML = recommendations.map(r => `
      <div class="rec-chip" data-slug="${esc(r.slug)}">
        <span class="rec-icon">${esc(r.icon || '⊞')}</span>
        <span class="rec-name">${esc(r.name)}</span>
        <span class="rec-why">${esc(r.reason || '')}</span>
      </div>
    `).join('');
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
    await Promise.all([loadItems(), loadUserState(), loadRecommendations()]);
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
