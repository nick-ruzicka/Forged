// Skills library — list, search, upvote, copy, submit.

(function () {
  const CATEGORIES = ['All', 'Development', 'Testing', 'Debugging', 'Planning', 'Code Review', 'Documents', 'Other'];
  const state = {
    search: '',
    category: 'All',
    sort: 'upvotes',
    skills: [],
    upvoted: new Set(JSON.parse(localStorage.getItem('forge_skill_upvotes') || '[]')),
  };

  function init() {
    Forge.renderLayout('skills');
    Forge.renderFooter();
    renderCategoryPills();
    hookEvents();
    reload();
  }

  function renderCategoryPills() {
    const el = Forge.qs('#skill-categories');
    el.innerHTML = '';
    CATEGORIES.forEach((cat) => {
      const pill = Forge.h(`<button class="pill ${cat === state.category ? 'active' : ''}">${Forge.escapeHtml(cat)}</button>`);
      pill.addEventListener('click', () => { state.category = cat; renderCategoryPills(); reload(); });
      el.appendChild(pill);
    });
  }

  function hookEvents() {
    Forge.qs('#skills-search').addEventListener('input', Forge.debounce((e) => {
      state.search = e.target.value.trim();
      reload();
    }, 300));
    Forge.qs('#skills-sort').addEventListener('change', (e) => { state.sort = e.target.value; reload(); });
    Forge.qs('#submit-skill-btn').addEventListener('click', openSubmitModal);
  }

  async function reload() {
    const grid = Forge.qs('#skills-grid');
    grid.innerHTML = '';
    for (let i = 0; i < 6; i++) grid.appendChild(Forge.h('<div class="skeleton skeleton-card"></div>'));
    try {
      const res = await ForgeApi.getSkills({
        search: state.search || undefined,
        category: state.category !== 'All' ? state.category : undefined,
        sort: state.sort,
      });
      state.skills = Array.isArray(res) ? res : (res.skills || res.data || []);
      renderGrid();
    } catch (err) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><h3>Could not load skills</h3><p>${Forge.escapeHtml(err.message)}</p></div>`;
    }
  }

  function renderGrid() {
    const grid = Forge.qs('#skills-grid');
    grid.innerHTML = '';
    if (state.skills.length === 0) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;">
        <div class="empty-state-icon">✨</div>
        <h3>No skills yet</h3><p>Be the first to share a prompt template.</p>
        <button class="btn btn-primary mt-3" id="empty-submit">+ Submit a Skill</button>
      </div>`;
      grid.querySelector('#empty-submit').addEventListener('click', openSubmitModal);
      return;
    }
    state.skills.forEach((s) => grid.appendChild(renderCard(s)));
  }

  function skillSlug(title) {
    return (title || 'skill').toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '') || 'skill';
  }

  function installCommand(skill) {
    const slug = skillSlug(skill.title);
    const downloadUrl = `${window.location.origin}${ForgeApi.skillDownloadUrl(skill.id)}`;
    return `mkdir -p ~/.claude/skills/${slug} && curl -L -o ~/.claude/skills/${slug}/SKILL.md ${downloadUrl}`;
  }

  function renderCard(skill) {
    const isUpvoted = state.upvoted.has(skill.id);
    const authorHandle = (skill.author_name || '').trim();
    const authorLink = skill.source_url
      ? `<a href="${Forge.escapeHtml(skill.source_url)}" target="_blank" rel="noopener" class="skill-author">@${Forge.escapeHtml(authorHandle || 'source')}</a>`
      : `<span class="text-muted text-sm">by ${Forge.escapeHtml(authorHandle || 'Anonymous')}</span>`;
    const cmd = installCommand(skill);
    const el = Forge.h(`
      <article class="card skill-card">
        <div class="flex flex-between items-center">
          ${Forge.categoryBadge(skill.category || 'Other')}
          <span class="text-muted text-sm">${skill.copy_count ? `${Forge.formatNumber(skill.copy_count)} downloads` : ''}</span>
        </div>
        <h3 class="tool-card-title">${Forge.escapeHtml(skill.title)}</h3>
        <p class="tool-card-tagline">${Forge.escapeHtml(skill.use_case || skill.description || '')}</p>
        <div class="skill-prompt-preview">${Forge.escapeHtml(Forge.truncate(skill.prompt_text || '', 300))}</div>
        <details class="skill-install-disclosure">
          <summary>
            <span class="skill-install-summary-label">Install with curl</span>
            <button class="btn btn-ghost btn-sm" data-action="copy-cmd" title="Copy install command" type="button">Copy</button>
          </summary>
          <code class="skill-install-cmd mono">${Forge.escapeHtml(cmd)}</code>
        </details>
        <div class="skill-actions">
          <div class="flex flex-gap-2 items-center">
            <button class="upvote-btn ${isUpvoted ? 'upvoted' : ''}" data-action="upvote">⬆ ${Forge.formatNumber(skill.upvotes || 0)}</button>
            ${authorLink}
          </div>
          <a class="btn btn-primary btn-sm" data-action="download" href="${Forge.escapeHtml(ForgeApi.skillDownloadUrl(skill.id))}" download>Download .md</a>
        </div>
      </article>
    `);
    el.querySelector('[data-action="upvote"]').addEventListener('click', () => onUpvote(skill, el));
    el.querySelector('[data-action="download"]').addEventListener('click', () => onDownload(skill, el));
    const copyBtn = el.querySelector('[data-action="copy-cmd"]');
    copyBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); onCopyCmd(cmd, copyBtn); });
    return el;
  }

  async function onUpvote(skill, card) {
    if (state.upvoted.has(skill.id)) { Forge.showToast('Already upvoted', 'info'); return; }
    const btn = card.querySelector('[data-action="upvote"]');
    btn.classList.add('upvoted');
    skill.upvotes = (skill.upvotes || 0) + 1;
    btn.textContent = `⬆ ${Forge.formatNumber(skill.upvotes)}`;
    state.upvoted.add(skill.id);
    localStorage.setItem('forge_skill_upvotes', JSON.stringify(Array.from(state.upvoted)));
    try { await ForgeApi.upvoteSkill(skill.id); }
    catch (err) {
      btn.classList.remove('upvoted');
      skill.upvotes--;
      btn.textContent = `⬆ ${Forge.formatNumber(skill.upvotes)}`;
      state.upvoted.delete(skill.id);
      localStorage.setItem('forge_skill_upvotes', JSON.stringify(Array.from(state.upvoted)));
      Forge.showToast(err.message || 'Upvote failed', 'error');
    }
  }

  function onDownload(skill) {
    // Browser handles the actual download via the href; we just bump local count.
    // The server increments copy_count as part of serving the file.
    skill.copy_count = (skill.copy_count || 0) + 1;
    Forge.showToast('Saving SKILL.md — drop it in ~/.claude/skills/<name>/', 'success');
  }

  async function onCopyCmd(cmd, btn) {
    await Forge.copyToClipboard(cmd, 'Install command copied');
    const original = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = original; }, 1500);
  }

  function openSubmitModal() {
    const user = Forge.getUser();
    const body = Forge.h(`
      <div>
        <div class="form-group">
          <label class="form-label" for="s-title">Title <span class="required">*</span></label>
          <input type="text" id="s-title" maxlength="100" placeholder="e.g. Discovery call follow-up template">
        </div>
        <div class="form-group">
          <label class="form-label" for="s-use-case">Use this when you want to… <span class="required">*</span></label>
          <input type="text" id="s-use-case" maxlength="160" placeholder="send a recap after a discovery call">
        </div>
        <div class="form-group">
          <label class="form-label" for="s-category">Category</label>
          <select id="s-category">${CATEGORIES.filter((c) => c !== 'All').map((c) => `<option>${Forge.escapeHtml(c)}</option>`).join('')}</select>
        </div>
        <div class="form-group">
          <label class="form-label" for="s-prompt">SKILL.md contents <span class="required">*</span></label>
          <textarea id="s-prompt" class="mono" rows="10" placeholder="---\nname: my-skill\ndescription: Use when ...\n---\n\nBody of the skill..."></textarea>
        </div>
        <div class="form-group">
          <label class="form-label" for="s-source">GitHub URL</label>
          <input type="url" id="s-source" placeholder="https://github.com/you/your-skills/tree/main/my-skill">
        </div>
        <div class="form-group">
          <label class="form-label" for="s-author">GitHub handle</label>
          <input type="text" id="s-author" value="${Forge.escapeHtml(user.name)}" placeholder="e.g. obra">
        </div>
      </div>
    `);
    const footer = Forge.h(`<div>
      <button class="btn btn-ghost" id="cancel">Cancel</button>
      <button class="btn btn-primary" id="submit">Submit Skill</button>
    </div>`);
    const { close } = Forge.openModal({ title: 'Submit a Skill', body, footer, width: 640 });
    footer.querySelector('#cancel').addEventListener('click', close);
    footer.querySelector('#submit').addEventListener('click', async () => {
      const payload = {
        title: body.querySelector('#s-title').value.trim(),
        use_case: body.querySelector('#s-use-case').value.trim(),
        category: body.querySelector('#s-category').value,
        prompt_text: body.querySelector('#s-prompt').value.trim(),
        source_url: body.querySelector('#s-source').value.trim(),
        author_name: body.querySelector('#s-author').value.trim() || 'Anonymous',
      };
      if (!payload.title || !payload.use_case || !payload.prompt_text) {
        Forge.showToast('Please fill in required fields', 'error');
        return;
      }
      try {
        await ForgeApi.submitSkill(payload);
        Forge.showToast('Skill submitted', 'success');
        close();
        reload();
      } catch (err) { Forge.showToast(err.message || 'Submit failed', 'error'); }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
