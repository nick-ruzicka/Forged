// Shared utilities: formatters, storage, toasts, keyboard shortcuts, badge HTML.

const USER_STORAGE_KEY = 'forge_user';

function pad2(n) { return String(n).padStart(2, '0'); }

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}

function formatDateTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return `${formatDate(iso)} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function formatRelative(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 0) return 'just now';
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 2592000) return `${Math.floor(diff / 86400)}d ago`;
  return formatDate(iso);
}

function formatDuration(ms) {
  if (ms == null || isNaN(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

function formatCost(usd) {
  if (usd == null || isNaN(usd)) return '—';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

function formatNumber(n) {
  if (n == null || isNaN(n)) return '0';
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function debounce(fn, delay = 300) {
  let t;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), delay);
  };
}

function truncate(str, n) {
  if (!str) return '';
  if (str.length <= n) return str;
  return str.slice(0, n).trimEnd() + '…';
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function slugify(s) {
  return String(s || '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 60);
}

async function copyToClipboard(text, msg = 'Copied to clipboard') {
  try {
    await navigator.clipboard.writeText(text);
    showToast(msg, 'success');
    return true;
  } catch (e) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      showToast(msg, 'success');
      return true;
    } catch (err) {
      showToast('Copy failed', 'error');
      return false;
    }
  }
}

// ---------- Toasts ----------

function ensureToastContainer() {
  let c = document.querySelector('.toast-container');
  if (!c) {
    c = document.createElement('div');
    c.className = 'toast-container';
    c.setAttribute('role', 'status');
    c.setAttribute('aria-live', 'polite');
    document.body.appendChild(c);
  }
  return c;
}

function showToast(msg, type = 'info', duration = 3000) {
  const c = ensureToastContainer();
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => {
    t.classList.add('closing');
    setTimeout(() => t.remove(), 200);
  }, duration);
}

// ---------- User (localStorage) ----------

function getUser() {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY);
    if (!raw) return { name: '', email: '' };
    const parsed = JSON.parse(raw);
    return { name: parsed.name || '', email: parsed.email || '' };
  } catch (e) {
    return { name: '', email: '' };
  }
}

function setUser(name, email) {
  try {
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify({ name, email }));
  } catch (e) { /* ignore */ }
}

function clearUser() {
  try { localStorage.removeItem(USER_STORAGE_KEY); } catch (e) { /* ignore */ }
}

function userInitials() {
  const { name, email } = getUser();
  const source = name || email || '';
  if (!source) return '?';
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

// ---------- Badges ----------

const TRUST_INFO = {
  trusted:    { label: 'Trusted',    icon: '✓', desc: 'Outputs are consistent and validated. Safe to act on directly.' },
  verified:   { label: 'Verified',   icon: '✓', desc: 'Reviewed and tested. Exercise standard professional judgment.' },
  caution:    { label: 'Caution',    icon: '⚠', desc: 'Outputs may vary. Treat as a starting point — verify before acting.' },
  restricted: { label: 'Restricted', icon: '🔒', desc: 'Access restricted. Contact your manager or platform admin.' },
  unverified: { label: 'Unverified', icon: '◷', desc: 'New tool. Run count is low. Treat as experimental.' },
};

function trustTierBadge(tier) {
  const key = String(tier || 'unverified').toLowerCase();
  const info = TRUST_INFO[key] || TRUST_INFO.unverified;
  return `<span class="badge badge-${key}" title="${escapeHtml(info.desc)}">
    <span aria-hidden="true">${info.icon}</span>${escapeHtml(info.label)}
  </span>`;
}

function outputTypeBadge(type) {
  const key = String(type || 'probabilistic').toLowerCase();
  const labels = {
    deterministic: { label: 'Consistent', icon: '✓' },
    probabilistic: { label: 'Variable',   icon: '⚡' },
    mixed:         { label: 'Mixed',      icon: '◐' },
  };
  const l = labels[key] || labels.probabilistic;
  return `<span class="badge badge-output ${key}"><span class="dot" aria-hidden="true"></span>${l.icon} ${escapeHtml(l.label)}</span>`;
}

function categoryBadge(cat) {
  if (!cat) return '';
  return `<span class="badge badge-category">${escapeHtml(cat)}</span>`;
}

function statusBadge(status) {
  if (!status) return '';
  const key = String(status).toLowerCase();
  const label = key.replace(/_/g, ' ');
  return `<span class="badge badge-status ${key}">${escapeHtml(label)}</span>`;
}

function ratingStars(rating, { interactive = false, onRate = null } = {}) {
  const r = Math.round(Number(rating) || 0);
  const wrap = document.createElement('span');
  wrap.className = 'rating';
  wrap.setAttribute('role', interactive ? 'radiogroup' : 'img');
  wrap.setAttribute('aria-label', `${r} out of 5 stars`);
  for (let i = 1; i <= 5; i++) {
    const s = document.createElement('span');
    s.className = 'star' + (i <= r ? ' filled' : '');
    s.textContent = '★';
    if (interactive) {
      s.setAttribute('role', 'radio');
      s.setAttribute('aria-checked', i === r ? 'true' : 'false');
      s.tabIndex = 0;
      s.addEventListener('click', () => { if (onRate) onRate(i); });
      s.addEventListener('mouseenter', () => {
        wrap.querySelectorAll('.star').forEach((el, idx) => {
          el.classList.toggle('filled', idx < i);
        });
      });
      s.addEventListener('mouseleave', () => {
        wrap.querySelectorAll('.star').forEach((el, idx) => {
          el.classList.toggle('filled', idx < r);
        });
      });
    }
    wrap.appendChild(s);
  }
  return wrap;
}

// ---------- DOM helpers ----------

function h(html) {
  const tmp = document.createElement('template');
  tmp.innerHTML = html.trim();
  return tmp.content.firstElementChild;
}

function qs(sel, root = document) { return root.querySelector(sel); }
function qsa(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

function on(el, evt, fn) { if (el) el.addEventListener(evt, fn); }

// ---------- Modal ----------

function openModal({ title = '', body = '', footer = '', width = 560, onClose = null } = {}) {
  closeModal();
  const overlay = h(`<div class="modal-overlay" role="dialog" aria-modal="true">
    <div class="modal" style="max-width:${width}px">
      <div class="modal-header">
        <h3 style="margin:0">${escapeHtml(title)}</h3>
        <button class="modal-close" aria-label="Close">✕</button>
      </div>
      <div class="modal-body"></div>
      ${footer ? `<div class="modal-footer"></div>` : ''}
    </div>
  </div>`);
  const modal = overlay.querySelector('.modal');
  const bodyEl = overlay.querySelector('.modal-body');
  const footerEl = overlay.querySelector('.modal-footer');
  if (body instanceof HTMLElement) bodyEl.appendChild(body); else bodyEl.innerHTML = body;
  if (footer && footerEl) {
    if (footer instanceof HTMLElement) footerEl.appendChild(footer); else footerEl.innerHTML = footer;
  }
  document.body.appendChild(overlay);
  // trap focus basic: focus first focusable
  const focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (focusable.length) focusable[0].focus();
  const closeBtn = overlay.querySelector('.modal-close');
  const close = () => { closeModal(); if (onClose) onClose(); };
  closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  return { overlay, modal, body: bodyEl, footer: footerEl, close };
}

function closeModal() {
  const existing = document.querySelector('.modal-overlay');
  if (existing) existing.remove();
}

// ---------- Keyboard shortcuts ----------

function initKeyboardShortcuts() {
  let gPending = false;
  let gTimer = null;
  document.addEventListener('keydown', (e) => {
    // Cmd/Ctrl+K focuses search
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      const s = document.querySelector('[data-search]');
      if (s) { e.preventDefault(); s.focus(); s.select(); }
      return;
    }
    // Escape closes modals
    if (e.key === 'Escape') {
      if (document.querySelector('.modal-overlay')) closeModal();
    }
    // ignore shortcuts while typing
    const tag = (e.target && e.target.tagName) || '';
    const isTyping = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target && e.target.isContentEditable);
    if (isTyping) return;
    // g-prefixed navigation
    if (e.key === 'g' && !gPending) {
      gPending = true;
      clearTimeout(gTimer);
      gTimer = setTimeout(() => { gPending = false; }, 900);
      return;
    }
    if (gPending) {
      gPending = false;
      clearTimeout(gTimer);
      if (e.key === 'c') window.location.href = '/index.html';
      else if (e.key === 's') window.location.href = '/submit.html';
      else if (e.key === 'm') window.location.href = '/my-tools.html';
      else if (e.key === 'k') window.location.href = '/skills.html';
    }
  });
}

// ---------- Header rendering ----------

function renderHeader(activeKey = '') {
  const { name, email } = getUser();
  const hasUser = !!(name || email);
  const avatarHtml = hasUser
    ? `<span class="avatar" title="${escapeHtml(name || email)}">${escapeHtml(userInitials())}</span>`
    : '';
  const headerHtml = `
    <header class="header" role="banner">
      <div class="header-left">
        <a href="/index.html" class="logo" aria-label="Forge home">
          <span class="logo-mark" aria-hidden="true">⚒</span>
          <span>FORGE</span>
        </a>
        <button type="button" class="nav-toggle" aria-label="Toggle navigation" aria-expanded="false" aria-controls="forge-nav">
          <span class="nav-toggle-bar" aria-hidden="true"></span>
          <span class="nav-toggle-bar" aria-hidden="true"></span>
          <span class="nav-toggle-bar" aria-hidden="true"></span>
        </button>
      </div>
      <nav id="forge-nav" class="header-center nav-links" role="navigation" aria-label="Main">
        <a href="/index.html" ${activeKey === 'catalog' ? 'class="active"' : ''}>Catalog</a>
        <a href="/skills.html" ${activeKey === 'skills' ? 'class="active"' : ''}>Skills</a>
        <a href="/my-tools.html" ${activeKey === 'my-tools' ? 'class="active"' : ''}>My Tools</a>
        <a href="/submit.html" ${activeKey === 'submit' ? 'class="active"' : ''}>Submit</a>
      </nav>
      <div class="header-right">
        <a href="https://slack.com" target="_blank" rel="noopener" class="btn-ghost btn-sm help-btn" aria-label="Help" title="Help">?</a>
        ${avatarHtml}
      </div>
    </header>`;
  const el = h(headerHtml);
  document.body.insertBefore(el, document.body.firstChild);
  const toggle = el.querySelector('.nav-toggle');
  const nav = el.querySelector('#forge-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = el.classList.toggle('nav-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.addEventListener('click', (e) => {
      if (e.target.tagName === 'A') {
        el.classList.remove('nav-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }
}

function renderFooter() {
  const html = `<footer class="footer">
    <span>Forge v0.1 — internal AI tool platform</span>
    <span>
      <a href="https://slack.com" target="_blank" rel="noopener">#forge-help</a>
      &nbsp;·&nbsp;
      <a href="/index.html">status</a>
    </span>
  </footer>`;
  document.body.appendChild(h(html));
}

function renderLayout(activeKey) {
  renderHeader(activeKey);
  initKeyboardShortcuts();
}

// ---------- Param helpers ----------

function getQueryParam(name) {
  const u = new URL(window.location.href);
  return u.searchParams.get(name);
}

function setQueryParam(name, value) {
  const u = new URL(window.location.href);
  if (value == null || value === '') u.searchParams.delete(name);
  else u.searchParams.set(name, value);
  window.history.replaceState({}, '', u.toString());
}

// ---------- Trust tier computation ----------

function computeTrustTier(tool) {
  if (tool.trust_tier) return tool.trust_tier.toLowerCase();
  const r = tool.reliability_score || 0;
  const s = tool.safety_score || 0;
  const v = tool.verified_score || 0;
  const sens = (tool.data_sensitivity || '').toLowerCase();
  if ((tool.security_tier || 1) >= 3 || sens === 'pii' || sens === 'confidential') return 'restricted';
  if (r >= 80 && s >= 80 && v >= 75) return 'trusted';
  if (r >= 60 && s >= 60 && v >= 50) return 'verified';
  if (v === 0 && (tool.unique_users || 0) <= 3) return 'unverified';
  return 'caution';
}

// ---------- Milestone tracking ----------

const MILESTONE_MESSAGES = {
  first_run: "You ran your first tool! Try remixing it to make it yours.",
  first_remix: "Your first remix — publish it to share with the team.",
  first_submission: "Tool submitted! You're now a builder.",
  first_approval: "Your tool was approved and is live.",
};

function trackMilestone(name) {
  if (!name) return false;
  let list = [];
  try {
    list = JSON.parse(localStorage.getItem("forge_milestones") || "[]");
    if (!Array.isArray(list)) list = [];
  } catch (e) {
    list = [];
  }
  if (list.indexOf(name) !== -1) return false;
  list.push(name);
  try { localStorage.setItem("forge_milestones", JSON.stringify(list)); } catch (e) {}
  const msg = MILESTONE_MESSAGES[name];
  if (msg && typeof showToast === "function") {
    showToast(msg, "success", 4500);
  }
  return true;
}

// ---------- Expose globals ----------

window.Forge = {
  formatDate, formatDateTime, formatRelative, formatDuration, formatCost, formatNumber,
  debounce, truncate, escapeHtml, slugify,
  copyToClipboard, showToast,
  getUser, setUser, clearUser, userInitials,
  trustTierBadge, outputTypeBadge, categoryBadge, statusBadge, ratingStars,
  TRUST_INFO,
  h, qs, qsa, on,
  openModal, closeModal,
  initKeyboardShortcuts, renderLayout, renderHeader, renderFooter,
  getQueryParam, setQueryParam,
  computeTrustTier,
  trackMilestone,
};
