// Publish — three modes: paste HTML, upload zip, GitHub URL.
// Submits to POST /api/submit/app (existing endpoint, supports multipart + JSON).

(function () {
  'use strict';

  const STORAGE_USER_ID = 'forge_user_id';
  const STORAGE_USER_EMAIL = 'forge_user_email';
  const STORAGE_USER_NAME = 'forge_user_name';

  function getUserId() {
    let id = '';
    try { id = localStorage.getItem(STORAGE_USER_ID) || ''; } catch (e) {}
    return id;
  }

  function getEmail() { try { return localStorage.getItem(STORAGE_USER_EMAIL) || ''; } catch (e) { return ''; } }
  function getName() { try { return localStorage.getItem(STORAGE_USER_NAME) || ''; } catch (e) { return ''; } }

  let mode = 'paste';
  let zipFile = null;

  // Pre-fill author fields from localStorage
  document.getElementById('meta-name-author').value = getName();
  document.getElementById('meta-email-author').value = getEmail();

  // ---------- Mode pills ----------
  document.querySelectorAll('.mode-pill').forEach((btn) => {
    btn.addEventListener('click', () => {
      mode = btn.dataset.mode;
      document.querySelectorAll('.mode-pill').forEach((b) => b.classList.toggle('active', b === btn));
      document.getElementById('panel-paste').style.display = mode === 'paste' ? '' : 'none';
      document.getElementById('panel-upload').style.display = mode === 'upload' ? '' : 'none';
      document.getElementById('panel-github').style.display = mode === 'github' ? '' : 'none';
    });
  });

  // ---------- Drag-drop into HTML textarea ----------
  const htmlSource = document.getElementById('html-source');
  htmlSource.addEventListener('dragover', (e) => { e.preventDefault(); });
  htmlSource.addEventListener('drop', (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (!f) return;
    f.text().then((txt) => { htmlSource.value = txt; });
  });

  // ---------- File drop ----------
  const fileDrop = document.getElementById('file-drop');
  const fileInput = document.getElementById('file-input');
  const fileName = document.getElementById('file-name');
  fileDrop.addEventListener('dragover', (e) => { e.preventDefault(); fileDrop.classList.add('over'); });
  fileDrop.addEventListener('dragleave', () => fileDrop.classList.remove('over'));
  fileDrop.addEventListener('drop', (e) => {
    e.preventDefault();
    fileDrop.classList.remove('over');
    if (e.dataTransfer.files[0]) {
      zipFile = e.dataTransfer.files[0];
      fileName.textContent = zipFile.name + ' (' + (zipFile.size / 1024).toFixed(1) + ' KB)';
    }
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) {
      zipFile = fileInput.files[0];
      fileName.textContent = zipFile.name + ' (' + (zipFile.size / 1024).toFixed(1) + ' KB)';
    }
  });

  // ---------- Submit ----------
  const status = document.getElementById('publish-status');
  document.getElementById('publish-btn').addEventListener('click', async () => {
    const name = document.getElementById('meta-name').value.trim();
    const tagline = document.getElementById('meta-tagline').value.trim();
    const description = document.getElementById('meta-description').value.trim();
    const category = document.getElementById('meta-category').value;
    const icon = document.getElementById('meta-icon').value.trim() || '⊞';
    const author_name = document.getElementById('meta-name-author').value.trim();
    const author_email = document.getElementById('meta-email-author').value.trim();

    status.classList.remove('error');
    if (!name) return fail('Name is required');
    if (!tagline) return fail('Tagline is required');
    if (!author_email || author_email.indexOf('@') === -1) return fail('Valid email required');

    // Persist author identity for next time
    try {
      if (author_name) localStorage.setItem(STORAGE_USER_NAME, author_name);
      if (author_email) localStorage.setItem(STORAGE_USER_EMAIL, author_email);
    } catch (e) {}

    let res;
    status.textContent = 'Publishing…';

    if (mode === 'paste') {
      const html = htmlSource.value.trim();
      if (!html) return fail('Paste your HTML first');
      res = await fetch('/api/submit/app', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Forge-User-Id': getUserId() },
        body: JSON.stringify({ html, name, tagline, description, category, author_name, author_email, icon }),
      });
    } else if (mode === 'upload') {
      if (!zipFile) return fail('Choose a file first');
      const fd = new FormData();
      fd.append('file', zipFile);
      fd.append('name', name);
      fd.append('tagline', tagline);
      fd.append('description', description);
      fd.append('category', category);
      fd.append('author_name', author_name);
      fd.append('author_email', author_email);
      res = await fetch('/api/submit/app', {
        method: 'POST',
        headers: { 'X-Forge-User-Id': getUserId() },
        body: fd,
      });
    } else if (mode === 'github') {
      const url = document.getElementById('github-url').value.trim();
      if (!url || !url.includes('github.com')) return fail('Paste a GitHub URL');
      res = await fetch('/api/submit/from-github', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Forge-User-Id': getUserId() },
        body: JSON.stringify({ github_url: url, name, tagline, description, category, author_name, author_email, icon }),
      });
    }

    let body;
    try { body = await res.json(); } catch (e) { body = {}; }
    if (!res.ok) return fail((body && (body.message || body.error)) || `HTTP ${res.status}`);
    showSuccess(body, name);
  });

  function fail(msg) {
    status.textContent = msg;
    status.classList.add('error');
  }

  function showSuccess(body, name) {
    document.getElementById('form-view').style.display = 'none';
    const sv = document.getElementById('success-view');
    sv.style.display = '';
    const url = body.url || ('/apps/' + body.slug);
    sv.innerHTML = `<div class="success-card">
      <div style="font-size:42px;">🎉</div>
      <h2>${name} published</h2>
      <p>It's pending admin review. Once approved, anyone on your team can add it to their Forge.</p>
      <p style="font-family:ui-monospace,Menlo,monospace;color:#0066FF;font-size:13px;">${url}</p>
      <a href="${url}">Open it</a>
      <a href="/my-tools.html">Go to My Forge</a>
      <button onclick="location.reload()">Publish another</button>
    </div>`;
  }
})();
