// My Forge — anonymous-by-default shelf. Identity card prompts only when needed.

(function () {
  'use strict';

  const STORAGE_USER_ID = 'forge_user_id';
  const STORAGE_USER_EMAIL = 'forge_user_email';
  const STORAGE_USER_NAME = 'forge_user_name';

  function uuidv4() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return 'anon-xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function getUserId() {
    let id = '';
    try { id = localStorage.getItem(STORAGE_USER_ID) || ''; } catch (e) {}
    if (!id) {
      id = uuidv4();
      try { localStorage.setItem(STORAGE_USER_ID, id); } catch (e) {}
    }
    return id;
  }

  function getEmail() { try { return localStorage.getItem(STORAGE_USER_EMAIL) || ''; } catch (e) { return ''; } }
  function getName() { try { return localStorage.getItem(STORAGE_USER_NAME) || ''; } catch (e) { return ''; } }

  function authHeaders() {
    const h = { 'X-Forge-User-Id': getUserId() };
    const e = getEmail();
    if (e) h['X-Forge-User-Email'] = e;
    return h;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // ---------- DOM refs ----------
  const shelfContent = document.getElementById('shelf-content');
  const shelfCount = document.getElementById('shelf-count');
  const identityBanner = document.getElementById('identity-banner');
  const updatesBanner = document.getElementById('updates-banner');
  const skillsList = document.getElementById('skills-list');

  const extModal = document.getElementById('external-modal');
  const extName = document.getElementById('ext-name');
  const extTagline = document.getElementById('ext-tagline');
  const extInstallBlock = document.getElementById('ext-install-block');
  const extLaunchBlock = document.getElementById('ext-launch-block');
  const extInstallCmd = document.getElementById('ext-install-cmd');
  const extInstallLabel = document.getElementById('ext-install-label');
  const extSource = document.getElementById('ext-source');
  const extMarkInstalled = document.getElementById('ext-mark-installed');
  const extClose = document.getElementById('ext-close');

  const paneOverlay = document.getElementById('pane-overlay');
  const paneTitle = document.getElementById('pane-title');
  const paneIframe = document.getElementById('pane-iframe');
  const paneNewtab = document.getElementById('pane-newtab');
  const paneClose = document.getElementById('pane-close');

  let activeItem = null;

  // ---------- Identity card (lazy ask) ----------

  function renderIdentityCard() {
    const email = getEmail();
    if (email) {
      identityBanner.innerHTML = `<div class="identity-card signed-in">
        <span style="font-size:18px;">👤</span>
        <div class="who">Signed in as <strong>${escapeHtml(getName() || email)}</strong></div>
        <button id="signout-btn">Sign out</button>
      </div>`;
      identityBanner.querySelector('#signout-btn').onclick = () => {
        if (!confirm('Sign out? Your shelf stays anonymous on this device.')) return;
        try {
          localStorage.removeItem(STORAGE_USER_EMAIL);
          localStorage.removeItem(STORAGE_USER_NAME);
        } catch (e) {}
        renderIdentityCard();
      };
    } else {
      identityBanner.innerHTML = `<div class="identity-card">
        <span style="font-size:18px;">👋</span>
        <div class="who">Anonymous. Add your email to sync your Forge across devices and publish apps.</div>
        <button id="claim-btn">Set up identity</button>
      </div>`;
      identityBanner.querySelector('#claim-btn').onclick = openIdentityForm;
    }
  }

  function openIdentityForm() {
    // Inline modal — no native prompts.
    let modal = document.getElementById('identity-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'identity-modal';
      modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:1200;display:flex;align-items:center;justify-content:center;padding:24px;';
      document.body.appendChild(modal);
    }
    modal.innerHTML = `
      <div style="background:#141414;border:1px solid #2a2a2a;border-radius:12px;max-width:440px;width:100%;padding:24px;">
        <h2 style="margin:0 0 6px;">Set up your identity</h2>
        <p style="color:#888;font-size:13px;margin:0 0 18px;">Your name and email so teammates can see who built what, and you can sync your Forge across devices.</p>
        <div style="display:flex;flex-direction:column;gap:12px;">
          <div>
            <label style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;display:block;margin-bottom:4px;">Name</label>
            <input id="id-name" type="text" value="${escapeHtml(getName())}"
              style="width:100%;background:#0d0d0d;border:1px solid #2a2a2a;color:#e0e0e0;padding:10px;border-radius:6px;box-sizing:border-box;font-size:14px;">
          </div>
          <div>
            <label style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;display:block;margin-bottom:4px;">Work email</label>
            <input id="id-email" type="email" value="${escapeHtml(getEmail())}" placeholder="you@navan.com"
              style="width:100%;background:#0d0d0d;border:1px solid #2a2a2a;color:#e0e0e0;padding:10px;border-radius:6px;box-sizing:border-box;font-size:14px;">
          </div>
          <div id="id-err" style="color:#ff8a80;font-size:12px;min-height:14px;"></div>
          <div style="display:flex;gap:8px;justify-content:flex-end;">
            <button id="id-cancel" style="background:none;border:1px solid #2a2a2a;color:#ccc;padding:9px 16px;border-radius:6px;cursor:pointer;">Cancel</button>
            <button id="id-save" style="background:#0066FF;color:white;border:none;padding:9px 16px;border-radius:6px;cursor:pointer;font-weight:600;">Save</button>
          </div>
        </div>
      </div>`;
    function close() { modal.remove(); }
    modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
    modal.querySelector('#id-cancel').onclick = close;
    modal.querySelector('#id-save').onclick = async () => {
      const name = modal.querySelector('#id-name').value.trim();
      const email = modal.querySelector('#id-email').value.trim();
      if (email && email.indexOf('@') === -1) {
        modal.querySelector('#id-err').textContent = 'Email looks invalid.';
        return;
      }
      try {
        if (name) localStorage.setItem(STORAGE_USER_NAME, name);
        if (email) localStorage.setItem(STORAGE_USER_EMAIL, email);
      } catch (e) {}
      await fetch('/api/me', {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email }),
      });
      close();
      renderIdentityCard();
      loadShelf();
    };
    modal.querySelector('#id-name').focus();
  }

  // ---------- Shelf ----------

  async function loadShelf() {
    shelfContent.innerHTML = '<div style="color:#666;padding:40px;text-align:center;">Loading…</div>';
    let res;
    try {
      res = await fetch('/api/me/items', { headers: authHeaders() });
    } catch (err) {
      shelfContent.innerHTML = `<div class="empty"><h2>Couldn't load your Forge</h2><p>${escapeHtml(err.message || err)}</p></div>`;
      return;
    }
    const body = await res.json().catch(() => ({}));
    const items = body.items || [];
    shelfCount.textContent = items.length === 0 ? 'empty' : `(${items.length})`;
    if (items.length === 0) {
      shelfContent.innerHTML = `
        <div class="empty">
          <h2>Your Forge is empty</h2>
          <p style="margin:0 0 16px;">Add apps from the catalog. They'll show up here, ready to open.</p>
          <a class="btn btn-primary" href="/" style="display:inline-block;background:#0066FF;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">Browse the catalog →</a>
        </div>`;
      return;
    }
    const grid = document.createElement('div');
    grid.className = 'shelf-grid';
    items.forEach((item) => grid.appendChild(renderTile(item)));
    shelfContent.innerHTML = '';
    shelfContent.appendChild(grid);
  }

  function renderTile(item) {
    const tile = document.createElement('div');
    tile.className = 'shelf-tile';
    const installNeeded = item.delivery === 'external' && !item.installed_locally;
    const launchLabel = item.delivery === 'external'
      ? (item.installed_locally ? 'Launch' : 'Install')
      : 'Open';
    tile.innerHTML = `
      <div style="display:flex;gap:12px;align-items:flex-start;">
        <div class="shelf-tile-icon">${escapeHtml(item.icon || '⊞')}</div>
        <div style="flex:1;min-width:0;">
          <h3 class="shelf-tile-name">${escapeHtml(item.name)}</h3>
        </div>
      </div>
      <p class="shelf-tile-tagline">${escapeHtml(item.tagline || '')}</p>
      <div class="shelf-tile-meta">
        <span>${item.open_count || 0} opens</span>
        ${item.delivery === 'external' ? `<span>· ${item.installed_locally ? 'installed' : 'not installed'}</span>` : ''}
      </div>
      <div class="shelf-tile-action">
        <button class="btn-launch ${installNeeded ? 'install-needed' : ''}" data-act="launch">${launchLabel}</button>
        <button class="btn-remove" data-act="remove" title="Remove from Forge">×</button>
      </div>`;

    tile.querySelector('[data-act="launch"]').addEventListener('click', (e) => {
      e.stopPropagation(); openItem(item);
    });
    tile.querySelector('[data-act="remove"]').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm(`Remove ${item.name} from your Forge?`)) return;
      await fetch(`/api/me/items/${item.id}`, { method: 'DELETE', headers: authHeaders() });
      loadShelf();
    });
    tile.addEventListener('click', () => openItem(item));
    return tile;
  }

  function openItem(item) {
    activeItem = item;
    bumpOpen(item.id).catch(() => {});
    if (item.delivery === 'external') openExternalModal(item);
    else openEmbeddedPane(item);
  }

  async function bumpOpen(toolId) {
    await fetch(`/api/me/items/${toolId}/launch`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
  }

  function openExternalModal(item) {
    extName.textContent = item.name;
    extTagline.textContent = item.tagline || '';
    extInstallCmd.textContent = item.install_command || '(no install command provided)';
    const isMultistep = (item.setup_complexity === 'multi-step' || item.setup_complexity === 'manual-setup');
    extInstallLabel.textContent = isMultistep
      ? "This app needs setup. Run these in a terminal — takes about 10 minutes:"
      : "Run this in a terminal:";
    if (item.installed_locally) {
      extInstallBlock.classList.add('hidden');
      extLaunchBlock.classList.remove('hidden');
      extMarkInstalled.style.display = 'none';
    } else {
      extInstallBlock.classList.remove('hidden');
      extLaunchBlock.classList.add('hidden');
      extMarkInstalled.style.display = '';
    }
    if (item.source_url) { extSource.href = item.source_url; extSource.style.display = ''; }
    else extSource.style.display = 'none';
    extModal.classList.add('open');
  }

  extMarkInstalled.addEventListener('click', async () => {
    if (!activeItem) return;
    await fetch(`/api/me/items/${activeItem.id}/install`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ version: 'manual' }),
    });
    extInstallBlock.classList.add('hidden');
    extLaunchBlock.classList.remove('hidden');
    extMarkInstalled.style.display = 'none';
    loadShelf();
  });

  extClose.addEventListener('click', () => { extModal.classList.remove('open'); activeItem = null; });
  extModal.addEventListener('click', (e) => { if (e.target === extModal) extClose.click(); });

  function openEmbeddedPane(item) {
    paneTitle.textContent = item.name;
    const src = `/apps/${encodeURIComponent(item.slug)}?user=${encodeURIComponent(getUserId())}`;
    paneIframe.src = src;
    paneNewtab.href = src;
    paneOverlay.classList.add('open');
  }

  paneClose.addEventListener('click', () => {
    paneOverlay.classList.remove('open');
    paneIframe.src = 'about:blank';
    activeItem = null;
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (paneOverlay.classList.contains('open')) paneClose.click();
    else if (extModal.classList.contains('open')) extClose.click();
  });

  // ---------- Updates banner ----------

  async function loadUpdates() {
    try {
      const res = await fetch('/api/me/updates', { headers: authHeaders() });
      const body = await res.json().catch(() => ({}));
      const updates = body.updates || [];
      if (!updates.length) { updatesBanner.innerHTML = ''; return; }
      const security = updates.some((u) => u.is_security);
      updatesBanner.innerHTML = `<div class="updates-banner ${security ? 'security' : ''}">
        <span class="badge">${security ? 'Security' : 'Updates'}</span>
        <span style="flex:1;color:#e0e0e0;font-size:13px;">${updates.length} app${updates.length === 1 ? '' : 's'} on your shelf ${security ? 'have security updates' : 'have new versions'}.</span>
        <button style="background:#1f1f1f;border:1px solid #444;color:#ccc;padding:5px 10px;border-radius:5px;cursor:pointer;font-size:12px;" onclick="alert('Use forge sync (CLI) or check each app from your shelf.')">View</button>
      </div>`;
    } catch (e) { /* silent */ }
  }

  // ---------- Skills sidebar ----------

  async function loadSkills() {
    try {
      const res = await fetch('/api/me/skills', { headers: authHeaders() });
      const body = await res.json().catch(() => ({}));
      const skills = body.skills || [];
      if (!skills.length) {
        skillsList.innerHTML = '<div class="skill-empty">No skills synced yet. Browse the Skills library and Subscribe.</div>';
        return;
      }
      skillsList.innerHTML = skills.map((s) => `
        <div class="skill-row">
          <div>${escapeHtml(s.title)}</div>
          <div class="skill-meta">${escapeHtml(s.category || 'general')} · by ${escapeHtml(s.author_name || 'unknown')}</div>
        </div>`).join('');
    } catch (e) {
      skillsList.innerHTML = '<div class="skill-empty">Couldn\'t load skills.</div>';
    }
  }

  // ---------- Init ----------

  async function init() {
    getUserId();  // ensure UUID exists
    renderIdentityCard();
    await Promise.all([loadShelf(), loadUpdates(), loadSkills()]);
  }

  init();
})();
