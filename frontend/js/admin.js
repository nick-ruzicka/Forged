// Admin — minimal review queue.

(function () {
  'use strict';

  const STORAGE_ADMIN_KEY = 'forge_admin_key';
  const gateView = document.getElementById('gate-view');
  const adminView = document.getElementById('admin-view');
  const gateKey = document.getElementById('gate-key');
  const queueEl = document.getElementById('queue');
  const statsEl = document.getElementById('stats');

  let adminKey = '';

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function init() {
    try { adminKey = localStorage.getItem(STORAGE_ADMIN_KEY) || ''; } catch (e) {}
    if (adminKey) {
      verifyAndShow();
    } else {
      gateView.classList.remove('hidden');
      gateKey.focus();
    }
  }

  document.getElementById('gate-submit').addEventListener('click', () => {
    adminKey = gateKey.value.trim();
    if (!adminKey) return;
    try { localStorage.setItem(STORAGE_ADMIN_KEY, adminKey); } catch (e) {}
    verifyAndShow();
  });
  gateKey.addEventListener('keydown', (e) => { if (e.key === 'Enter') document.getElementById('gate-submit').click(); });

  async function verifyAndShow() {
    // Try a request; if 401, prompt re-entry
    const res = await fetch('/api/admin/queue', { headers: { 'X-Admin-Key': adminKey } });
    if (res.status === 401) {
      try { localStorage.removeItem(STORAGE_ADMIN_KEY); } catch (e) {}
      gateView.classList.remove('hidden');
      gateKey.value = '';
      gateKey.focus();
      gateKey.placeholder = 'Wrong key — try again';
      return;
    }
    gateView.classList.add('hidden');
    adminView.classList.remove('hidden');
    await Promise.all([loadStats(), loadQueue()]);
  }

  async function loadStats() {
    try {
      const res = await fetch('/api/admin/analytics', { headers: { 'X-Admin-Key': adminKey } });
      const body = await res.json();
      statsEl.innerHTML = `
        <div class="stat-card"><div class="v">${body.apps_live || 0}</div><div class="l">Apps live</div></div>
        <div class="stat-card"><div class="v">${body.apps_pending || 0}</div><div class="l">Pending review</div></div>
        <div class="stat-card"><div class="v">${body.skills_total || 0}</div><div class="l">Skills total</div></div>`;
    } catch (e) { statsEl.innerHTML = ''; }
  }

  async function loadQueue() {
    queueEl.innerHTML = '<div style="color:#666;padding:24px;text-align:center;">Loading…</div>';
    const res = await fetch('/api/admin/queue', { headers: { 'X-Admin-Key': adminKey } });
    const body = await res.json();
    const tools = body.tools || [];
    if (!tools.length) {
      queueEl.innerHTML = `<div style="background:#0d2a1a;border:1px solid #1a7f4b;border-radius:10px;padding:32px;text-align:center;color:#aaa;">
        <div style="font-size:32px;">🎉</div>
        <h3 style="color:#e0e0e0;margin:8px 0 4px;">Queue is empty</h3>
        <p style="margin:0;font-size:13px;">Nothing pending. Check back when authors publish new apps.</p>
      </div>`;
      return;
    }
    queueEl.innerHTML = '';
    for (const t of tools) {
      const tile = document.createElement('div');
      tile.className = 'queue-tile';
      tile.innerHTML = `
        <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;">
          <div style="font-size:22px;width:38px;height:38px;display:flex;align-items:center;justify-content:center;background:#0d0d0d;border:1px solid #2a2a2a;border-radius:6px;">${escapeHtml(t.icon || '⊞')}</div>
          <div style="flex:1;min-width:0;">
            <h3>${escapeHtml(t.name)}</h3>
            <p style="margin:0;color:#888;font-size:13px;">${escapeHtml(t.tagline || '')}</p>
          </div>
        </div>
        <div class="qmeta">
          <span>${escapeHtml(t.category || 'Other')}</span>
          <span>· ${escapeHtml(t.author_name || 'Unknown')} (${escapeHtml(t.author_email || '')})</span>
          <span>· ${(t.html_length || 0)} bytes of HTML</span>
        </div>
        <div class="qbadges" data-insp></div>
        <div class="qactions">
          <button class="approve" data-act="approve" data-id="${t.id}">Approve</button>
          <button class="reject" data-act="reject" data-id="${t.id}">Reject</button>
          <button class="preview" data-act="preview" data-id="${t.id}" data-slug="${escapeHtml(t.slug)}">Preview</button>
        </div>`;
      queueEl.appendChild(tile);
      // Lazy-load inspection
      fetch(`/api/tools/${t.id}/inspection`).then(r => r.json()).then((j) => {
        const wrap = tile.querySelector('[data-insp]');
        if (!wrap || !j.badges) return;
        wrap.innerHTML = (j.badges || []).map(b => {
          const cls = b.tone === 'warn' ? 'warn' : '';
          return `<span class="qbadge ${cls}" title="${escapeHtml(b.detail || '')}">${escapeHtml(b.icon)} ${escapeHtml(b.label)}</span>`;
        }).join('');
      }).catch(() => {});
      tile.querySelector('[data-act="approve"]').addEventListener('click', () => approve(t.id));
      tile.querySelector('[data-act="reject"]').addEventListener('click', () => reject(t.id));
      tile.querySelector('[data-act="preview"]').addEventListener('click', () => preview(t.slug));
    }
  }

  async function approve(toolId) {
    if (!confirm('Approve this app? It becomes live in the catalog immediately.')) return;
    const res = await fetch(`/api/admin/tools/${toolId}/approve`, {
      method: 'POST',
      headers: { 'X-Admin-Key': adminKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewer: 'admin' }),
    });
    if (res.ok) {
      Forge.showToast('Approved', 'success');
      await loadQueue(); loadStats();
    } else {
      Forge.showToast('Approve failed', 'error');
    }
  }

  async function reject(toolId) {
    const reason = prompt('Why are you rejecting this? (Author will see this.)');
    if (reason === null) return;
    const res = await fetch(`/api/admin/tools/${toolId}/reject`, {
      method: 'POST',
      headers: { 'X-Admin-Key': adminKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    if (res.ok) {
      Forge.showToast('Rejected', 'info');
      await loadQueue(); loadStats();
    } else {
      Forge.showToast('Reject failed', 'error');
    }
  }

  function preview(slug) {
    window.open(`/apps/${slug}`, '_blank', 'noopener');
  }

  init();
})();
