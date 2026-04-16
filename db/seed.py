"""
Seed data for Forge. Loads 5 approved launch tools with full governance scores.
Run: python3 -m db.seed
"""
import json
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import db
from api.models import compute_trust_tier


# ---------- App HTML bodies (dark-themed, DM Sans) ----------

APP_HTML_JOB_SEARCH = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Search Pipeline</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0d0d0d; --surface:#1a1a1a; --surface-2:#222; --border:#2a2a2a;
    --accent:#0066FF; --text:#e8e8e8; --muted:#888;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:'DM Sans',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
  header.app{padding:20px 28px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
  header.app h1{margin:0;font-size:20px;letter-spacing:-0.01em}
  header.app .meta{color:var(--muted);font-size:13px;font-family:'DM Mono',monospace}
  .board{padding:20px;display:grid;gap:14px;grid-template-columns:repeat(6,minmax(220px,1fr));overflow-x:auto}
  .col{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px;min-height:65vh;display:flex;flex-direction:column}
  .col-head{padding:0 0 12px 0;display:flex;justify-content:space-between;align-items:center}
  .col-head h2{margin:0;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:var(--muted);font-weight:500}
  .col-head .count{color:var(--muted);font-family:'DM Mono',monospace;font-size:12px}
  .col[data-key=applied]{border-top:3px solid #3aa3ff}
  .col[data-key=phone]{border-top:3px solid #7c6bff}
  .col[data-key=interview]{border-top:3px solid #c970ff}
  .col[data-key=final]{border-top:3px solid #ff8a3d}
  .col[data-key=offer]{border-top:3px solid #16d17d}
  .col[data-key=rejected]{border-top:3px solid #ff5151}
  .cards{display:flex;flex-direction:column;gap:8px;flex:1}
  .card{background:var(--surface-2);border:1px solid var(--border);border-radius:8px;padding:10px 12px;cursor:grab;transition:border .15s,transform .15s}
  .card:hover{border-color:var(--accent)}
  .card.dragging{opacity:0.4}
  .card .company{font-weight:500;font-size:13px}
  .card .role{font-size:12px;color:var(--muted);margin-top:2px}
  .card .row{display:flex;justify-content:space-between;margin-top:8px;font-family:'DM Mono',monospace;font-size:11px;color:var(--muted)}
  .col.drop{background:rgba(0,102,255,0.08)}
  .add-bar{position:sticky;bottom:0;padding:12px 20px;background:rgba(13,13,13,0.96);border-top:1px solid var(--border);display:flex;gap:10px;align-items:center}
  button{background:var(--accent);color:#fff;border:0;padding:9px 16px;font-family:inherit;font-size:13px;font-weight:500;border-radius:6px;cursor:pointer}
  button:hover{filter:brightness(1.1)}
  button.ghost{background:transparent;border:1px solid var(--border);color:var(--text)}
  .dialog{position:fixed;inset:0;background:rgba(0,0,0,0.6);display:none;align-items:center;justify-content:center;z-index:20}
  .dialog.open{display:flex}
  .dialog-card{width:440px;max-width:calc(100vw - 40px);background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:22px}
  .dialog-card h3{margin:0 0 14px 0;font-size:16px}
  label{display:block;font-size:12px;color:var(--muted);margin:10px 0 4px}
  input,textarea,select{width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:13px;padding:9px 10px;border-radius:6px}
  input:focus,textarea:focus,select:focus{outline:0;border-color:var(--accent)}
  textarea{min-height:70px;resize:vertical}
  .dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:18px}
  .kbd{font-family:'DM Mono',monospace;font-size:11px;padding:2px 6px;background:var(--surface-2);border:1px solid var(--border);border-radius:4px}
</style>
</head>
<body>
<header class="app">
  <div>
    <h1>Job Search Pipeline</h1>
    <div class="meta" id="total">0 applications tracked</div>
  </div>
  <div><button id="add-btn">Add company</button></div>
</header>
<div class="board" id="board"></div>
<div class="add-bar">
  <span class="kbd">N</span>
  <span class="meta">press N to add &middot; drag cards between columns &middot; click a card to edit</span>
</div>
<div class="dialog" id="dialog">
  <div class="dialog-card">
    <h3 id="dlg-title">Add application</h3>
    <label>Company *</label><input id="f-company" placeholder="Acme Corp">
    <label>Role *</label><input id="f-role" placeholder="Senior RevOps Analyst">
    <label>Applied date</label><input id="f-date" type="date">
    <label>Salary / range</label><input id="f-salary" placeholder="$140k - $170k">
    <label>URL</label><input id="f-url" placeholder="https://...">
    <label>Notes</label><textarea id="f-notes" placeholder="Referral, recruiter name, open questions..."></textarea>
    <div class="dialog-actions">
      <button class="ghost" id="dlg-delete" style="display:none">Delete</button>
      <button class="ghost" id="dlg-cancel">Cancel</button>
      <button id="dlg-save">Save</button>
    </div>
  </div>
</div>
<script>
const COLUMNS = [
  {key:'applied',label:'Applied'},{key:'phone',label:'Phone Screen'},
  {key:'interview',label:'Interview'},{key:'final',label:'Final Round'},
  {key:'offer',label:'Offer'},{key:'rejected',label:'Rejected'},
];
let state = { cards: [] };
let editing = null;
const $ = (s) => document.querySelector(s);
const boardEl = $('#board');
const dlg = $('#dialog');
const esc = (s) => (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){
  boardEl.innerHTML = '';
  COLUMNS.forEach(col => {
    const items = state.cards.filter(c => c.column === col.key);
    const colEl = document.createElement('div');
    colEl.className = 'col'; colEl.dataset.key = col.key;
    colEl.innerHTML = '<div class="col-head"><h2>'+col.label+'</h2><span class="count">'+items.length+'</span></div><div class="cards"></div>';
    const cardsEl = colEl.querySelector('.cards');
    items.forEach(c => {
      const cEl = document.createElement('div');
      cEl.className = 'card'; cEl.draggable = true; cEl.dataset.id = c.id;
      cEl.innerHTML = '<div class="company">'+esc(c.company)+'</div><div class="role">'+esc(c.role||'')+'</div>'
        + '<div class="row"><span>'+esc(c.date||'')+'</span><span>'+esc(c.salary||'')+'</span></div>';
      cEl.addEventListener('click', () => openEdit(c));
      cEl.addEventListener('dragstart', e => { cEl.classList.add('dragging'); e.dataTransfer.setData('text/plain', c.id); });
      cEl.addEventListener('dragend', () => cEl.classList.remove('dragging'));
      cardsEl.appendChild(cEl);
    });
    colEl.addEventListener('dragover', e => { e.preventDefault(); colEl.classList.add('drop'); });
    colEl.addEventListener('dragleave', () => colEl.classList.remove('drop'));
    colEl.addEventListener('drop', e => {
      e.preventDefault(); colEl.classList.remove('drop');
      const id = e.dataTransfer.getData('text/plain');
      const card = state.cards.find(c => c.id === id);
      if (card && card.column !== col.key) { card.column = col.key; persist(); }
    });
    boardEl.appendChild(colEl);
  });
  $('#total').textContent = state.cards.length + ' applications tracked';
}
function openAdd(){
  editing = null;
  $('#dlg-title').textContent = 'Add application';
  $('#f-company').value = ''; $('#f-role').value = '';
  $('#f-date').value = new Date().toISOString().slice(0,10);
  $('#f-salary').value = ''; $('#f-url').value = ''; $('#f-notes').value = '';
  $('#dlg-delete').style.display = 'none';
  dlg.classList.add('open');
  setTimeout(() => $('#f-company').focus(), 30);
}
function openEdit(card){
  editing = card;
  $('#dlg-title').textContent = 'Edit application';
  $('#f-company').value = card.company; $('#f-role').value = card.role || '';
  $('#f-date').value = card.date || ''; $('#f-salary').value = card.salary || '';
  $('#f-url').value = card.url || ''; $('#f-notes').value = card.notes || '';
  $('#dlg-delete').style.display = 'inline-block';
  dlg.classList.add('open');
}
$('#add-btn').addEventListener('click', openAdd);
$('#dlg-cancel').addEventListener('click', () => dlg.classList.remove('open'));
$('#dlg-save').addEventListener('click', () => {
  const company = $('#f-company').value.trim();
  const role = $('#f-role').value.trim();
  if (!company || !role) { alert('Company and role are required'); return; }
  const fields = { company, role, date: $('#f-date').value, salary: $('#f-salary').value,
                   url: $('#f-url').value, notes: $('#f-notes').value };
  if (editing) Object.assign(editing, fields);
  else state.cards.push(Object.assign({ id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())+Math.random()), column: 'applied' }, fields));
  dlg.classList.remove('open'); persist();
});
$('#dlg-delete').addEventListener('click', () => {
  if (!editing) return;
  state.cards = state.cards.filter(c => c.id !== editing.id);
  dlg.classList.remove('open'); persist();
});
document.addEventListener('keydown', e => {
  if (e.target.matches('input, textarea, select')) return;
  if (e.key && e.key.toLowerCase() === 'n' && !e.metaKey && !e.ctrlKey) { e.preventDefault(); openAdd(); }
  if (e.key === 'Escape') dlg.classList.remove('open');
});
async function persist(){ render(); try { await window.ForgeAPI.setData('board', state); } catch(e){} }
async function load(){
  try { const saved = await window.ForgeAPI.getData('board'); if (saved && Array.isArray(saved.cards)) state = saved; } catch(e){}
  render();
}
load();
</script>
</body>
</html>
"""


APP_HTML_MEETING_PREP = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meeting Prep Generator</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{--bg:#0d0d0d;--surface:#1a1a1a;--surface-2:#222;--border:#2a2a2a;--accent:#0066FF;--text:#e8e8e8;--muted:#888}
  *{box-sizing:border-box}
  body{margin:0;font-family:'DM Sans',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
  header.app{padding:20px 28px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
  header.app h1{margin:0;font-size:20px;letter-spacing:-0.01em}
  header.app .meta{color:var(--muted);font-size:13px;font-family:'DM Mono',monospace}
  main{display:grid;grid-template-columns:280px 1fr;gap:0;min-height:calc(100vh - 62px)}
  aside{background:var(--surface);border-right:1px solid var(--border);padding:20px 18px}
  aside h2{margin:0 0 14px 0;font-size:12px;color:var(--muted);letter-spacing:0.08em;text-transform:uppercase;font-weight:500}
  .hist-item{padding:10px 12px;background:var(--surface-2);border:1px solid var(--border);border-radius:8px;margin-bottom:8px;cursor:pointer;transition:border .15s}
  .hist-item:hover{border-color:var(--accent)}
  .hist-item .h{font-weight:500;font-size:13px}
  .hist-item .s{color:var(--muted);font-size:11px;font-family:'DM Mono',monospace;margin-top:2px}
  .empty{color:var(--muted);font-size:13px}
  section.main{padding:28px 34px;max-width:880px}
  .form{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:22px;margin-bottom:22px}
  .form h2{margin:0 0 4px;font-size:16px}
  .form p.sub{color:var(--muted);font-size:13px;margin:0 0 16px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px}
  input,textarea,select{width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:13px;padding:9px 10px;border-radius:6px}
  input:focus,textarea:focus,select:focus{outline:0;border-color:var(--accent)}
  textarea{min-height:70px;resize:vertical}
  .actions{display:flex;justify-content:space-between;align-items:center;margin-top:16px;gap:10px}
  button{background:var(--accent);color:#fff;border:0;padding:10px 18px;font-family:inherit;font-size:13px;font-weight:500;border-radius:6px;cursor:pointer}
  button:hover{filter:brightness(1.1)}
  button.ghost{background:transparent;border:1px solid var(--border);color:var(--text)}
  button:disabled{opacity:0.5;cursor:wait}
  .brief{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px 28px}
  .brief .ctx{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-bottom:18px;font-family:'DM Mono',monospace}
  .brief h2{margin:22px 0 8px;font-size:15px;color:var(--accent);font-weight:500}
  .brief h2:first-child{margin-top:0}
  .brief-body{line-height:1.55;font-size:14px;white-space:pre-wrap}
  .loading{color:var(--muted);font-size:13px;padding:18px 0}
  .dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);margin-right:6px;animation:pulse 1s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
  @media print{
    body{background:#fff;color:#000}
    header.app, aside, .form, button{display:none!important}
    main{display:block}
    section.main{max-width:100%;padding:0}
    .brief{border:0;padding:0;background:#fff}
  }
</style>
</head>
<body>
<header class="app">
  <div>
    <h1>Meeting Prep Generator</h1>
    <div class="meta" id="sub">Pre-call briefs backed by Account Research Brief</div>
  </div>
</header>
<main>
  <aside>
    <h2>Recent preps</h2>
    <div id="history"></div>
  </aside>
  <section class="main">
    <div class="form">
      <h2>Generate a pre-call brief</h2>
      <p class="sub">We&apos;ll call the Account Research Brief tool and format the result for your meeting.</p>
      <div class="grid">
        <div><label>Company *</label><input id="f-company" placeholder="Acme Corp"></div>
        <div><label>Contact name *</label><input id="f-contact" placeholder="Dana Lee"></div>
      </div>
      <div style="margin-top:12px"><label>Meeting purpose *</label><textarea id="f-purpose" placeholder="Discovery call to understand their travel & expense pain points."></textarea></div>
      <div class="actions">
        <span class="meta" id="status"></span>
        <div>
          <button class="ghost" id="print-btn" onclick="window.print()">Print</button>
          <button id="gen-btn">Generate brief</button>
        </div>
      </div>
    </div>
    <div class="brief" id="brief" style="display:none">
      <div class="ctx" id="brief-ctx"></div>
      <div class="brief-body" id="brief-body"></div>
    </div>
  </section>
</main>
<script>
const $ = (s) => document.querySelector(s);
const esc = (s) => (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let history = [];

function renderHistory(){
  const el = $('#history');
  if (!history.length){ el.innerHTML = '<div class="empty">No preps yet. Generate your first brief on the right.</div>'; return; }
  el.innerHTML = history.slice(0,5).map(h =>
    '<div class="hist-item" data-id="'+h.id+'"><div class="h">'+esc(h.company)+'</div><div class="s">'+esc(h.contact)+' &middot; '+new Date(h.ts).toLocaleString()+'</div></div>'
  ).join('');
  el.querySelectorAll('.hist-item').forEach(n => n.addEventListener('click', () => {
    const item = history.find(h => h.id === n.dataset.id);
    if (item) showBrief(item);
  }));
}
function showBrief(item){
  $('#brief').style.display = 'block';
  $('#brief-ctx').innerHTML = '<span>Company: '+esc(item.company)+'</span><span>Contact: '+esc(item.contact)+'</span><span>Purpose: '+esc(item.purpose)+'</span>';
  $('#brief-body').textContent = item.output || '';
}
async function load(){
  try { const saved = await window.ForgeAPI.getData('history'); if (Array.isArray(saved)) history = saved; } catch(e){}
  renderHistory();
}
async function generate(){
  const company = $('#f-company').value.trim();
  const contact = $('#f-contact').value.trim();
  const purpose = $('#f-purpose').value.trim();
  if (!company || !contact || !purpose){ alert('Company, contact, and purpose are required.'); return; }
  const btn = $('#gen-btn');
  btn.disabled = true; btn.textContent = 'Generating...';
  $('#status').innerHTML = '<span class="dot"></span>Calling Account Research Brief...';
  $('#brief').style.display = 'block';
  $('#brief-ctx').innerHTML = '<span>Company: '+esc(company)+'</span><span>Contact: '+esc(contact)+'</span><span>Purpose: '+esc(purpose)+'</span>';
  $('#brief-body').innerHTML = '<div class="loading">Running the research agent. Usually 3-6 seconds.</div>';
  try {
    const result = await window.ForgeAPI.runTool('account-research-brief', { company_name: company, segment: 'Mid-Market' });
    const output = (result && result.output) || '(no output returned)';
    $('#brief-body').textContent = output;
    const item = { id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())), company, contact, purpose, output, ts: Date.now() };
    history.unshift(item);
    history = history.slice(0, 50);
    try { await window.ForgeAPI.setData('history', history); } catch(e){}
    renderHistory();
    $('#status').textContent = 'Ran in ' + (result && result.duration_ms ? (result.duration_ms + 'ms') : '');
  } catch(err){
    $('#brief-body').textContent = 'Error: ' + (err && err.message ? err.message : String(err));
    $('#status').textContent = '';
  } finally {
    btn.disabled = false; btn.textContent = 'Generate brief';
  }
}
$('#gen-btn').addEventListener('click', generate);
load();
</script>
</body>
</html>
"""


APP_HTML_PIPELINE_VELOCITY = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pipeline Velocity Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root{--bg:#0d0d0d;--surface:#1a1a1a;--surface-2:#222;--border:#2a2a2a;--accent:#0066FF;--text:#e8e8e8;--muted:#888;--warn:#ff8a3d;--ok:#16d17d}
  *{box-sizing:border-box}
  body{margin:0;font-family:'DM Sans',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
  header.app{padding:20px 28px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
  header.app h1{margin:0;font-size:20px;letter-spacing:-0.01em}
  header.app .meta{color:var(--muted);font-size:13px;font-family:'DM Mono',monospace}
  main{padding:24px 28px;display:flex;flex-direction:column;gap:22px;max-width:1200px;margin:0 auto}
  .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
  .metric{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 18px}
  .metric .l{font-size:11px;color:var(--muted);letter-spacing:0.08em;text-transform:uppercase}
  .metric .v{font-family:'DM Mono',monospace;font-size:26px;margin-top:6px;font-weight:500}
  .metric .s{font-size:12px;color:var(--muted);margin-top:2px}
  .metric .v.warn{color:var(--warn)}
  .metric .v.ok{color:var(--ok)}
  .panels{display:grid;grid-template-columns:1.2fr 1fr;gap:18px}
  .panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px}
  .panel h2{margin:0 0 14px;font-size:14px}
  .panel h2 .hint{color:var(--muted);font-weight:400;font-size:12px;margin-left:8px}
  .add-form{display:grid;grid-template-columns:repeat(5, 1fr);gap:10px;align-items:end}
  .add-form label{display:block;font-size:11px;color:var(--muted);margin-bottom:3px}
  input,select{width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:13px;padding:8px 9px;border-radius:6px}
  input:focus,select:focus{outline:0;border-color:var(--accent)}
  .row-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:12px}
  button{background:var(--accent);color:#fff;border:0;padding:9px 16px;font-family:inherit;font-size:13px;font-weight:500;border-radius:6px;cursor:pointer}
  button:hover{filter:brightness(1.1)}
  button.ghost{background:transparent;border:1px solid var(--border);color:var(--text)}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;font-weight:500;color:var(--muted);font-size:11px;letter-spacing:0.08em;text-transform:uppercase;padding:8px 10px;border-bottom:1px solid var(--border)}
  td{padding:10px;border-bottom:1px solid var(--border);font-family:'DM Mono',monospace}
  tr.at-risk td{color:var(--warn)}
  td.stage{font-family:inherit;color:var(--text)}
  .empty{color:var(--muted);font-size:13px;padding:16px 0;text-align:center}
  .del{background:transparent;color:var(--muted);border:0;font-size:12px;cursor:pointer;padding:4px 6px}
  .del:hover{color:var(--warn)}
  canvas{max-height:260px}
</style>
</head>
<body>
<header class="app">
  <div>
    <h1>Pipeline Velocity Dashboard</h1>
    <div class="meta" id="sub">Manual pipeline tracking &middot; computes velocity metrics from deals you enter</div>
  </div>
  <div><button class="ghost" id="csv-btn">Export CSV</button></div>
</header>
<main>
  <div class="metrics">
    <div class="metric"><div class="l">Total pipeline</div><div class="v" id="m-total">$0</div><div class="s" id="m-count">0 deals</div></div>
    <div class="metric"><div class="l">Avg days in stage</div><div class="v" id="m-days">0</div><div class="s">across open deals</div></div>
    <div class="metric"><div class="l">At risk</div><div class="v warn" id="m-risk">0</div><div class="s">days_in_stage &gt; 30</div></div>
    <div class="metric"><div class="l">Likely close (30d)</div><div class="v ok" id="m-close">$0</div><div class="s">close_date within 30 days</div></div>
  </div>
  <div class="panels">
    <div class="panel">
      <h2>Pipeline by stage <span class="hint">count and value</span></h2>
      <canvas id="chart"></canvas>
    </div>
    <div class="panel">
      <h2>Add a deal</h2>
      <div class="add-form">
        <div><label>Company</label><input id="f-company" placeholder="Acme"></div>
        <div><label>Stage</label>
          <select id="f-stage">
            <option>Qualified</option><option>Discovery</option><option>Proposal</option>
            <option>Negotiation</option><option>Closed Won</option><option>Closed Lost</option>
          </select>
        </div>
        <div><label>Days in stage</label><input id="f-days" type="number" min="0" value="0"></div>
        <div><label>Value (USD)</label><input id="f-value" type="number" min="0" placeholder="50000"></div>
        <div><label>Close date</label><input id="f-close" type="date"></div>
      </div>
      <div class="row-actions">
        <button id="add-btn">Add deal</button>
      </div>
    </div>
  </div>
  <div class="panel">
    <h2>Open deals</h2>
    <table id="tbl"><thead><tr>
      <th>Company</th><th>Stage</th><th>Days</th><th>Value</th><th>Close</th><th></th>
    </tr></thead><tbody></tbody></table>
    <div class="empty" id="empty" style="display:none">No deals yet. Add your first one above.</div>
  </div>
</main>
<script>
const $ = (s) => document.querySelector(s);
const esc = (s) => (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const STAGES = ['Qualified','Discovery','Proposal','Negotiation','Closed Won','Closed Lost'];
let deals = [];
let chart = null;

function fmt$(n){ return '$' + Math.round(Number(n)||0).toLocaleString(); }
function isOpen(d){ return !['Closed Won','Closed Lost'].includes(d.stage); }

function render(){
  const open = deals.filter(isOpen);
  $('#m-total').textContent = fmt$(open.reduce((a,d) => a + (Number(d.value)||0), 0));
  $('#m-count').textContent = open.length + ' open &middot; ' + deals.length + ' total';
  const avgDays = open.length ? Math.round(open.reduce((a,d) => a + (Number(d.days)||0), 0) / open.length) : 0;
  $('#m-days').textContent = avgDays;
  $('#m-risk').textContent = open.filter(d => (Number(d.days)||0) > 30).length;
  const now = Date.now(); const cutoff = now + 30*86400*1000;
  const likely = open.filter(d => d.close && new Date(d.close).getTime() <= cutoff)
                     .reduce((a,d) => a + (Number(d.value)||0), 0);
  $('#m-close').textContent = fmt$(likely);

  const tb = document.querySelector('#tbl tbody');
  tb.innerHTML = deals.map(d => {
    const risk = (Number(d.days)||0) > 30 && isOpen(d);
    return '<tr class="'+(risk?'at-risk':'')+'" data-id="'+d.id+'">'
      + '<td class="stage">'+esc(d.company)+'</td>'
      + '<td class="stage">'+esc(d.stage)+'</td>'
      + '<td>'+(Number(d.days)||0)+'</td>'
      + '<td>'+fmt$(d.value)+'</td>'
      + '<td>'+esc(d.close||'')+'</td>'
      + '<td style="text-align:right"><button class="del">remove</button></td></tr>';
  }).join('');
  $('#empty').style.display = deals.length ? 'none' : 'block';
  tb.querySelectorAll('.del').forEach(btn => btn.addEventListener('click', e => {
    const id = e.target.closest('tr').dataset.id;
    deals = deals.filter(d => d.id !== id); persist();
  }));
  drawChart();
}

function drawChart(){
  const counts = STAGES.map(s => deals.filter(d => d.stage === s).length);
  const values = STAGES.map(s => deals.filter(d => d.stage === s).reduce((a,d) => a + (Number(d.value)||0), 0));
  if (chart) chart.destroy();
  const ctx = document.getElementById('chart').getContext('2d');
  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: STAGES,
      datasets: [
        {label:'Count', data: counts, backgroundColor:'#0066FF', yAxisID:'y1', borderRadius:4},
        {label:'Value ($)', data: values, backgroundColor:'rgba(22,209,125,0.55)', yAxisID:'y2', borderRadius:4},
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#e8e8e8' } } },
      scales: {
        x: { ticks: { color: '#888' }, grid: { color: '#2a2a2a' } },
        y1:{ type:'linear', position:'left', ticks:{ color:'#888' }, grid:{ color:'#2a2a2a' } },
        y2:{ type:'linear', position:'right', ticks:{ color:'#888' }, grid:{ display:false } },
      }
    }
  });
}

$('#add-btn').addEventListener('click', () => {
  const d = {
    id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())+Math.random()),
    company: $('#f-company').value.trim(),
    stage: $('#f-stage').value,
    days: Number($('#f-days').value) || 0,
    value: Number($('#f-value').value) || 0,
    close: $('#f-close').value,
  };
  if (!d.company){ alert('Company required'); return; }
  deals.push(d);
  $('#f-company').value=''; $('#f-days').value='0'; $('#f-value').value=''; $('#f-close').value='';
  persist();
});

$('#csv-btn').addEventListener('click', () => {
  const rows = [['company','stage','days_in_stage','value','close_date']];
  deals.forEach(d => rows.push([d.company, d.stage, d.days, d.value, d.close||'']));
  const csv = rows.map(r => r.map(v => '"'+String(v).replace(/"/g,'""')+'"').join(',')).join('\n');
  const blob = new Blob([csv], {type:'text/csv'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'pipeline-velocity.csv'; a.click();
  URL.revokeObjectURL(url);
});

async function persist(){ render(); try { await window.ForgeAPI.setData('deals', deals); } catch(e){} }
async function load(){
  try { const saved = await window.ForgeAPI.getData('deals'); if (Array.isArray(saved)) deals = saved; } catch(e){}
  render();
}
load();
</script>
</body>
</html>
"""


APP_HTML_ACCOUNT_HEALTH = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Account Health Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root{--bg:#0d0d0d;--surface:#1a1a1a;--surface-2:#222;--border:#2a2a2a;--accent:#0066FF;--text:#e8e8e8;--muted:#888;--warn:#ff8a3d;--ok:#16d17d}
  *{box-sizing:border-box}
  body{margin:0;font-family:'DM Sans',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
  header.app{padding:20px 28px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
  header.app h1{margin:0;font-size:20px;letter-spacing:-0.01em}
  header.app .meta{color:var(--muted);font-size:13px;font-family:'DM Mono',monospace}
  .pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:11px;font-family:'DM Mono',monospace;letter-spacing:0.04em}
  .pill.ok{background:rgba(22,209,125,0.12);color:var(--ok);border:1px solid rgba(22,209,125,0.35)}
  .pill.warn{background:rgba(255,138,61,0.12);color:var(--warn);border:1px solid rgba(255,138,61,0.35)}
  .banner{margin:20px 28px;padding:18px 22px;border:1px solid rgba(255,138,61,0.35);background:rgba(255,138,61,0.08);border-radius:10px}
  .banner h2{margin:0 0 6px;font-size:15px;color:var(--warn)}
  .banner p{margin:0 0 10px;font-size:13px;color:var(--text);line-height:1.5}
  .banner ul{margin:10px 0 0;padding-left:20px;font-family:'DM Mono',monospace;font-size:12px;color:var(--muted)}
  .banner ul li{margin:4px 0}
  main{padding:20px 28px;display:grid;grid-template-columns:340px 1fr;gap:18px;max-width:1400px;margin:0 auto}
  .panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px}
  .panel h2{margin:0 0 12px;font-size:14px;font-weight:500}
  .panel h2 .hint{color:var(--muted);font-weight:400;font-size:12px;margin-left:8px}
  input[type=search],input[type=text]{width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:13px;padding:9px 10px;border-radius:6px}
  input:focus{outline:0;border-color:var(--accent)}
  .acct-list{display:flex;flex-direction:column;gap:8px;margin-top:12px;max-height:70vh;overflow-y:auto}
  .acct{padding:10px 12px;background:var(--surface-2);border:1px solid var(--border);border-radius:8px;cursor:pointer;transition:border .15s}
  .acct:hover{border-color:var(--accent)}
  .acct.selected{border-color:var(--accent);background:rgba(0,102,255,0.08)}
  .acct .n{font-weight:500;font-size:13px}
  .acct .m{color:var(--muted);font-size:11px;font-family:'DM Mono',monospace;margin-top:2px;display:flex;gap:10px;flex-wrap:wrap}
  .empty{color:var(--muted);font-size:13px;padding:16px 0;text-align:center}
  .detail{display:flex;flex-direction:column;gap:18px}
  .kv{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
  .kv .k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.08em}
  .kv .v{font-family:'DM Mono',monospace;font-size:14px;margin-top:4px}
  .subgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  table{width:100%;border-collapse:collapse;font-size:12px}
  th{text-align:left;font-weight:500;color:var(--muted);font-size:10px;letter-spacing:0.08em;text-transform:uppercase;padding:6px 8px;border-bottom:1px solid var(--border)}
  td{padding:8px;border-bottom:1px solid var(--border);font-family:'DM Mono',monospace}
  td.name{font-family:inherit}
  canvas{max-height:200px}
  .loading{color:var(--muted);font-size:13px;padding:14px 0}
  .dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);margin-right:6px;animation:pulse 1s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
</style>
</head>
<body>
<header class="app">
  <div>
    <h1>Account Health Dashboard</h1>
    <div class="meta">Live account data from Salesforce in one view</div>
  </div>
  <div id="sf-pill"><span class="pill warn">checking...</span></div>
</header>

<div id="banner" class="banner" style="display:none">
  <h2>Salesforce not connected yet</h2>
  <p>This dashboard lights up once your admin wires up the Salesforce credentials. Ask them to set <code>SALESFORCE_USERNAME</code>, <code>SALESFORCE_PASSWORD</code>, and <code>SALESFORCE_TOKEN</code> on the Forge server.</p>
  <p style="color:var(--muted);font-size:12px">Endpoints this app will use once connected:</p>
  <ul>
    <li>GET /api/forgedata/salesforce/accounts</li>
    <li>GET /api/forgedata/salesforce/opportunities</li>
    <li>GET /api/forgedata/salesforce/contacts</li>
    <li>GET /api/forgedata/salesforce/activities</li>
  </ul>
</div>

<main id="main" style="display:none">
  <div class="panel">
    <h2>Accounts <span class="hint" id="acct-count"></span></h2>
    <input type="search" id="f-search" placeholder="Search by name...">
    <div class="acct-list" id="acct-list"></div>
  </div>
  <div class="panel" id="detail-panel">
    <div class="empty" id="detail-empty">Select an account to see pipeline, contacts, and activity.</div>
    <div class="detail" id="detail" style="display:none">
      <div>
        <h2 id="d-name">&nbsp;</h2>
        <div class="kv">
          <div><div class="k">Industry</div><div class="v" id="d-industry">—</div></div>
          <div><div class="k">Employees</div><div class="v" id="d-emp">—</div></div>
          <div><div class="k">Annual revenue</div><div class="v" id="d-rev">—</div></div>
          <div><div class="k">Owner</div><div class="v" id="d-owner">—</div></div>
        </div>
      </div>
      <div class="subgrid">
        <div class="panel" style="padding:14px">
          <h2>Pipeline funnel <span class="hint" id="opp-count"></span></h2>
          <canvas id="funnel"></canvas>
        </div>
        <div class="panel" style="padding:14px">
          <h2>Contacts <span class="hint" id="contact-count"></span></h2>
          <table id="contacts-tbl"><thead><tr><th>Name</th><th>Title</th><th>Email</th></tr></thead><tbody></tbody></table>
          <div class="empty" id="contacts-empty" style="display:none">No contacts.</div>
        </div>
      </div>
      <div class="panel" style="padding:14px">
        <h2>Recent activity <span class="hint" id="act-count"></span></h2>
        <table id="act-tbl"><thead><tr><th>Date</th><th>Subject</th><th>Status</th><th>Owner</th></tr></thead><tbody></tbody></table>
        <div class="empty" id="act-empty" style="display:none">No activity.</div>
      </div>
    </div>
  </div>
</main>

<script>
const $ = (s) => document.querySelector(s);
const esc = (s) => (s==null?'':String(s)).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let accounts = [];
let selected = null;
let funnelChart = null;
let searchTimer = null;

function fmt$(n){ if(n==null||isNaN(Number(n))) return '—'; return '$' + Math.round(Number(n)).toLocaleString(); }

async function boot(){
  let status;
  try { status = await window.ForgeAPI.data.salesforce.status(); }
  catch(err){ status = {salesforce:{configured:false,connected:false}}; }
  const sf = (status && status.salesforce) || {};
  const pill = $('#sf-pill');
  if (!sf.configured){
    pill.innerHTML = '<span class="pill warn">Salesforce: not configured</span>';
    $('#banner').style.display = 'block';
    return;
  }
  if (!sf.connected){
    pill.innerHTML = '<span class="pill warn">Salesforce: configured, not connected</span>';
  } else {
    pill.innerHTML = '<span class="pill ok">Salesforce: live</span>';
  }
  $('#main').style.display = 'grid';
  loadAccounts();
}

async function loadAccounts(search){
  const listEl = $('#acct-list');
  listEl.innerHTML = '<div class="loading"><span class="dot"></span>Loading accounts...</div>';
  const params = {limit: 50};
  if (search) params.search = search;
  let resp;
  try { resp = await window.ForgeAPI.data.salesforce.accounts(params); }
  catch(err){ listEl.innerHTML = '<div class="empty">Error loading accounts.</div>'; return; }
  if (resp && resp.error){
    listEl.innerHTML = '<div class="empty">'+esc(resp.error)+'</div>';
    return;
  }
  accounts = (resp && resp.data) || [];
  $('#acct-count').textContent = accounts.length;
  renderAccounts();
}

function renderAccounts(){
  const listEl = $('#acct-list');
  if (!accounts.length){ listEl.innerHTML = '<div class="empty">No accounts match.</div>'; return; }
  listEl.innerHTML = accounts.map(a => {
    const rev = a.annual_revenue ? fmt$(a.annual_revenue) : '—';
    const emp = a.number_of_employees || '—';
    const industry = a.industry || '—';
    return '<div class="acct" data-id="'+esc(a.id)+'">'
      + '<div class="n">'+esc(a.name)+'</div>'
      + '<div class="m"><span>'+esc(industry)+'</span><span>'+esc(emp)+' emp</span><span>'+esc(rev)+'</span></div>'
      + '</div>';
  }).join('');
  listEl.querySelectorAll('.acct').forEach(n => n.addEventListener('click', () => {
    listEl.querySelectorAll('.acct').forEach(x => x.classList.remove('selected'));
    n.classList.add('selected');
    const acct = accounts.find(a => String(a.id) === n.dataset.id);
    if (acct) loadDetail(acct);
  }));
}

async function loadDetail(acct){
  selected = acct;
  $('#detail-empty').style.display = 'none';
  $('#detail').style.display = 'flex';
  $('#d-name').textContent = acct.name || '—';
  $('#d-industry').textContent = acct.industry || '—';
  $('#d-emp').textContent = acct.number_of_employees != null ? String(acct.number_of_employees) : '—';
  $('#d-rev').textContent = fmt$(acct.annual_revenue);
  $('#d-owner').textContent = acct.owner_name || '—';

  const [oppsResp, contactsResp, actsResp] = await Promise.all([
    window.ForgeAPI.data.salesforce.opportunities({account_id: acct.id, limit: 50}).catch(()=>({data:[]})),
    window.ForgeAPI.data.salesforce.contacts({account_id: acct.id, limit: 50}).catch(()=>({data:[]})),
    window.ForgeAPI.data.salesforce.activities(acct.id).catch(()=>({data:[]})),
  ]);

  renderFunnel((oppsResp && oppsResp.data) || []);
  renderContacts((contactsResp && contactsResp.data) || []);
  renderActivities((actsResp && actsResp.data) || []);
}

function renderFunnel(opps){
  $('#opp-count').textContent = opps.length + ' opps';
  const stages = {};
  opps.forEach(o => {
    const s = o.stage_name || 'Unknown';
    stages[s] = (stages[s] || 0) + (Number(o.amount) || 0);
  });
  const labels = Object.keys(stages);
  const data = labels.map(l => stages[l]);
  if (funnelChart) funnelChart.destroy();
  if (!labels.length){
    const ctx = document.getElementById('funnel').getContext('2d');
    ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);
    return;
  }
  funnelChart = new Chart(document.getElementById('funnel').getContext('2d'), {
    type: 'bar',
    data: { labels, datasets:[{label:'Value ($)', data, backgroundColor:'#0066FF', borderRadius:4}] },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x:{ ticks:{color:'#888', callback: v => '$' + Number(v).toLocaleString()}, grid:{color:'#2a2a2a'} },
        y:{ ticks:{color:'#e8e8e8'}, grid:{display:false} },
      }
    }
  });
}

function renderContacts(contacts){
  $('#contact-count').textContent = contacts.length;
  const tb = document.querySelector('#contacts-tbl tbody');
  if (!contacts.length){
    tb.innerHTML = '';
    $('#contacts-tbl').style.display = 'none';
    $('#contacts-empty').style.display = 'block';
    return;
  }
  $('#contacts-tbl').style.display = 'table';
  $('#contacts-empty').style.display = 'none';
  tb.innerHTML = contacts.map(c =>
    '<tr><td class="name">'+esc(c.name)+'</td><td class="name">'+esc(c.title||'—')+'</td><td>'+esc(c.email||'—')+'</td></tr>'
  ).join('');
}

function renderActivities(acts){
  $('#act-count').textContent = acts.length;
  const tb = document.querySelector('#act-tbl tbody');
  if (!acts.length){
    tb.innerHTML = '';
    $('#act-tbl').style.display = 'none';
    $('#act-empty').style.display = 'block';
    return;
  }
  $('#act-tbl').style.display = 'table';
  $('#act-empty').style.display = 'none';
  tb.innerHTML = acts.map(a =>
    '<tr><td>'+esc(a.activity_date||'—')+'</td><td class="name">'+esc(a.subject||'—')+'</td><td>'+esc(a.status||'—')+'</td><td class="name">'+esc(a.owner_name||'—')+'</td></tr>'
  ).join('');
}

$('#f-search').addEventListener('input', e => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  searchTimer = setTimeout(() => loadAccounts(q), 300);
});

boot();
</script>
</body>
</html>
"""


SEED_APPS = [
    {
        "slug": "job-search-pipeline",
        "name": "Job Search Pipeline",
        "tagline": "Drag-and-drop kanban for tracking your job search end to end.",
        "description": (
            "Personal job-search kanban with six stages (Applied, Phone Screen, Interview, "
            "Final Round, Offer, Rejected). Add companies with role, date, salary range, and "
            "notes; drag cards between stages; press N to add a card. All data is saved in "
            "your personal app store via the Forge API."
        ),
        "category": "Other",
        "tags": "kanban,job-search,personal",
        "author_name": "Sarah Chen",
        "author_email": "sarah@navan.com",
        "reliability_score": 95,
        "safety_score": 95,
        "verified_score": 75,
        "complexity_score": 82,
        "data_sensitivity": "internal",
        "app_html": APP_HTML_JOB_SEARCH,
        "run_count": 38,
        "avg_rating": 4.6,
    },
    {
        "slug": "meeting-prep",
        "name": "Meeting Prep Generator",
        "tagline": "Turn a company name into a structured pre-call brief in seconds.",
        "description": (
            "One-page app for sales reps preparing for a call. Enter the company, contact, "
            "and meeting purpose; the app calls the Account Research Brief tool under the "
            "hood and formats the output into a pre-call brief (snapshot, priorities, "
            "openers, risks). The last five briefs are saved in the sidebar for quick recall "
            "and a print button produces a physical copy."
        ),
        "category": "Account Research",
        "tags": "meeting-prep,discovery,brief",
        "author_name": "Marcus Patel",
        "author_email": "marcus@navan.com",
        "reliability_score": 72,
        "safety_score": 85,
        "verified_score": 70,
        "complexity_score": 85,
        "data_sensitivity": "internal",
        "app_html": APP_HTML_MEETING_PREP,
        "run_count": 61,
        "avg_rating": 4.4,
    },
    {
        "slug": "account-health-dashboard",
        "name": "Account Health Dashboard",
        "tagline": "Live account data from Salesforce in one view",
        "description": (
            "Governed, read-only view of Salesforce account data. Search accounts, then "
            "drill into opportunities (with a pipeline funnel), contacts, and recent "
            "activity — all surfaced through Forge's ForgeData layer so every read is "
            "logged. If Salesforce credentials aren't configured yet, the app shows a "
            "friendly banner listing the endpoints it would use once connected."
        ),
        "category": "Account Research",
        "tags": "salesforce,accounts,dashboard,forgedata",
        "author_name": "Nick Ruzicka",
        "author_email": "nick@navan.com",
        "reliability_score": 92,
        "safety_score": 90,
        "verified_score": 70,
        "complexity_score": 78,
        "data_sensitivity": "internal",
        "app_html": APP_HTML_ACCOUNT_HEALTH,
        "run_count": 0,
        "avg_rating": 0.0,
    },
    {
        "slug": "pipeline-velocity",
        "name": "Pipeline Velocity Dashboard",
        "tagline": "Manual pipeline tracker with velocity metrics and at-risk flags.",
        "description": (
            "Enter deals (company, stage, days in stage, value, close date) and the dashboard "
            "computes total pipeline value, average days in stage, at-risk deals (more than 30 "
            "days idle), and likely 30-day close value. Includes a Chart.js breakdown by stage "
            "and a one-click CSV export. Persists deals via the Forge app store."
        ),
        "category": "Reporting",
        "tags": "pipeline,velocity,reporting",
        "author_name": "Priya Shah",
        "author_email": "priya@navan.com",
        "reliability_score": 90,
        "safety_score": 80,
        "verified_score": 70,
        "complexity_score": 70,
        "data_sensitivity": "confidential",
        "app_html": APP_HTML_PIPELINE_VELOCITY,
        "run_count": 22,
        "avg_rating": 4.3,
    },
]


SEED_TOOLS = [
    {
        "slug": "account-research-brief",
        "name": "Account Research Brief",
        "tagline": "Generate a pre-call prospect profile in seconds.",
        "description": (
            "Produces a structured account briefing for a sales rep before a discovery call.\n\n"
            "Covers company overview, likely pain points, and conversation hooks. Useful for Mid-Market "
            "and Enterprise segments."
        ),
        "category": "Account Research",
        "tags": "discovery,prep,research",
        "reliability_score": 72,
        "safety_score": 88,
        "data_sensitivity": "internal",
        "complexity_score": 80,
        "verified_score": 75,
        "output_type": "probabilistic",
        "output_format": "markdown",
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1500,
        "temperature": 0.4,
        "system_prompt": (
            "You are a Navan revenue-operations research assistant. Produce a structured pre-call brief "
            "for {{company_name}} ({{company_website}}). Include: 1) company snapshot, 2) likely priorities "
            "in the {{segment}} segment, 3) three conversation openers, 4) risks or red flags. If any fact "
            "is unknown, write 'unknown' — never fabricate numbers or names."
        ),
        "hardened_prompt": (
            "You are a Navan revenue-operations research assistant. Produce a structured pre-call brief "
            "for the company provided. Only use information you are confident about. Never invent specific "
            "numbers, dates, executives, or customer names. If anything is uncertain, write 'unknown'.\n\n"
            "Company: {{company_name}}\nWebsite: {{company_website}}\nSegment: {{segment}}\n\n"
            "Produce exactly four sections (Markdown h2): 'Company Snapshot', 'Likely Priorities', "
            "'Conversation Openers' (three bullets), 'Risks / Red Flags'."
        ),
        "input_schema": [
            {"name": "company_name", "label": "Company name", "type": "text", "required": True},
            {"name": "company_website", "label": "Company website", "type": "text", "required": False},
            {"name": "segment", "label": "Segment", "type": "select",
             "options": ["SMB", "Mid-Market", "Enterprise"], "required": True},
        ],
        "author_name": "Sarah Chen",
        "author_email": "sarah@navan.com",
        "run_count": 247,
        "avg_rating": 4.3,
    },
    {
        "slug": "prospect-email-draft",
        "name": "Prospect Email Draft",
        "tagline": "Draft a personalized outreach email from a few facts.",
        "description": (
            "Writes a short, tailored outbound email draft. Output is a draft — always review and personalize "
            "before sending."
        ),
        "category": "Email Generation",
        "tags": "email,outreach,draft",
        "reliability_score": 45,
        "safety_score": 68,
        "data_sensitivity": "internal",
        "complexity_score": 82,
        "verified_score": 60,
        "output_type": "probabilistic",
        "output_format": "email_draft",
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 800,
        "temperature": 0.6,
        "system_prompt": (
            "Write a first-draft outbound email to {{prospect_name}} at {{company_name}}. "
            "Reference the context: {{context}}. Keep it under 120 words and professional."
        ),
        "hardened_prompt": (
            "You are drafting an outbound email. Produce only the email (Subject line + Body). Never send, "
            "never claim to have sent, and never fabricate specific metrics, quotes, or prior interactions.\n\n"
            "Recipient: {{prospect_name}} at {{company_name}}\nRole: {{role}}\nContext: {{context}}\n\n"
            "Output format:\nSubject: <subject>\n\n<body under 120 words, professional tone, one clear ask>\n\n"
            "If context is thin, keep the email generic rather than inventing details."
        ),
        "input_schema": [
            {"name": "prospect_name", "label": "Prospect name", "type": "text", "required": True},
            {"name": "company_name", "label": "Company", "type": "text", "required": True},
            {"name": "role", "label": "Their role", "type": "text", "required": False},
            {"name": "context", "label": "Context / reason for outreach", "type": "textarea", "required": True},
        ],
        "author_name": "Marcus Patel",
        "author_email": "marcus@navan.com",
        "run_count": 512,
        "avg_rating": 4.1,
    },
    {
        "slug": "icp-qualification-check",
        "name": "ICP Qualification Check",
        "tagline": "Score how well an account fits Navan's ICP.",
        "description": (
            "Given a company's basics, returns a structured ICP fit score with supporting reasons. Use as a "
            "starting point — always confirm with live data before routing."
        ),
        "category": "Contact Scoring",
        "tags": "icp,scoring,qualification",
        "reliability_score": 65,
        "safety_score": 80,
        "data_sensitivity": "internal",
        "complexity_score": 75,
        "verified_score": 70,
        "output_type": "mixed",
        "output_format": "json",
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 900,
        "temperature": 0.2,
        "system_prompt": (
            "Score ICP fit for {{company_name}} with {{employee_count}} employees in {{industry}} "
            "(HQ {{hq_location}}). Return a JSON object."
        ),
        "hardened_prompt": (
            "Score ICP fit for a company against Navan's ideal customer profile. Respond ONLY with a "
            "single JSON object. Never include prose before or after the JSON.\n\n"
            "Company: {{company_name}}\nEmployee count: {{employee_count}}\nIndustry: {{industry}}\n"
            "HQ location: {{hq_location}}\n\n"
            "JSON schema: {\"fit_score\": 0-100 integer, \"tier\": \"high|medium|low\", "
            "\"positive_signals\": [<string>], \"negative_signals\": [<string>], "
            "\"recommended_next_step\": <string>}. If a field cannot be determined, set tier to 'low' and "
            "explain in negative_signals."
        ),
        "input_schema": [
            {"name": "company_name", "label": "Company", "type": "text", "required": True},
            {"name": "employee_count", "label": "Employee count", "type": "number", "required": True},
            {"name": "industry", "label": "Industry", "type": "text", "required": True},
            {"name": "hq_location", "label": "HQ location", "type": "text", "required": False},
        ],
        "author_name": "Priya Shah",
        "author_email": "priya@navan.com",
        "run_count": 134,
        "avg_rating": 4.0,
    },
    {
        "slug": "call-prep-summary",
        "name": "Call Prep Summary",
        "tagline": "Summarize open opportunities into a 2-minute prep sheet.",
        "description": (
            "Condenses notes, last touch, and deal stage into a tight call-prep summary. Treat as a "
            "starting point — the rep still needs to verify specifics in Salesforce."
        ),
        "category": "Call Prep",
        "tags": "call-prep,summary,deals",
        "reliability_score": 55,
        "safety_score": 75,
        "data_sensitivity": "confidential",
        "complexity_score": 70,
        "verified_score": 55,
        "output_type": "probabilistic",
        "output_format": "markdown",
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1200,
        "temperature": 0.3,
        "system_prompt": (
            "Produce a 2-minute call prep summary from the provided deal context: {{deal_name}} "
            "stage {{stage}}, last activity {{last_activity}}."
        ),
        "hardened_prompt": (
            "Produce a concise call-prep summary using only the provided context. Do NOT invent people, "
            "numbers, or prior interactions. If a detail is missing, mark it as 'unknown'.\n\n"
            "Deal: {{deal_name}}\nStage: {{stage}}\nLast activity: {{last_activity}}\n"
            "Notes: {{notes}}\n\n"
            "Output format (Markdown):\n## Where we stand\n<2-3 sentences>\n## Open questions\n"
            "<bullet list>\n## Suggested focus for this call\n<bullet list>"
        ),
        "input_schema": [
            {"name": "deal_name", "label": "Deal name", "type": "text", "required": True},
            {"name": "stage", "label": "Current stage", "type": "text", "required": True},
            {"name": "last_activity", "label": "Last activity", "type": "text", "required": False},
            {"name": "notes", "label": "Notes", "type": "textarea", "required": False},
        ],
        "author_name": "Devon Wu",
        "author_email": "devon@navan.com",
        "run_count": 88,
        "avg_rating": 3.9,
    },
    {
        "slug": "churn-risk-check",
        "name": "Churn Risk Check",
        "tagline": "Flag accounts showing early warning signs of churn.",
        "description": (
            "Analyzes usage, support, and engagement signals to surface churn risk level with a short "
            "rationale. Output drives review, not automated action."
        ),
        "category": "Reporting",
        "tags": "churn,risk,customer-success",
        "reliability_score": 68,
        "safety_score": 82,
        "data_sensitivity": "confidential",
        "complexity_score": 65,
        "verified_score": 80,
        "output_type": "mixed",
        "output_format": "json",
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 800,
        "temperature": 0.2,
        "system_prompt": (
            "Evaluate churn risk for {{account_name}}. Usage trend: {{usage_trend}}. "
            "Last CSM touch: {{last_touch_days}} days ago. Support tickets open: {{open_tickets}}."
        ),
        "hardened_prompt": (
            "Evaluate churn risk for the provided account. Return ONLY JSON. Never include prose outside "
            "the JSON object.\n\n"
            "Account: {{account_name}}\nUsage trend: {{usage_trend}}\nLast CSM touch (days ago): "
            "{{last_touch_days}}\nOpen support tickets: {{open_tickets}}\n\n"
            "JSON schema: {\"risk_level\": \"low|medium|high\", \"confidence\": 0-1 float, "
            "\"warning_signals\": [<string>], \"recommended_action\": <string>}. If signals are ambiguous, "
            "downgrade risk_level rather than guessing."
        ),
        "input_schema": [
            {"name": "account_name", "label": "Account", "type": "text", "required": True},
            {"name": "usage_trend", "label": "Usage trend",
             "type": "select", "options": ["up", "flat", "down"], "required": True},
            {"name": "last_touch_days", "label": "Days since last CSM touch", "type": "number", "required": True},
            {"name": "open_tickets", "label": "Open support tickets", "type": "number", "required": False},
        ],
        "author_name": "Elena Torres",
        "author_email": "elena@navan.com",
        "run_count": 192,
        "avg_rating": 4.2,
    },
]


def _tool_exists(slug: str) -> bool:
    return db.get_tool_by_slug(slug) is not None


def seed_tools():
    inserted = []
    now = datetime.utcnow()
    for t in SEED_TOOLS:
        if _tool_exists(t["slug"]):
            continue
        tier = compute_trust_tier(
            reliability=t.get("reliability_score", 0),
            safety=t.get("safety_score", 0),
            verified=t.get("verified_score", 0),
            data_sensitivity=t.get("data_sensitivity", "internal"),
            run_count=t.get("run_count", 0),
        )
        access_token = uuid.uuid4().hex
        row = {
            "slug": t["slug"],
            "name": t["name"],
            "tagline": t["tagline"],
            "description": t["description"],
            "category": t["category"],
            "tags": t.get("tags", ""),
            "reliability_score": t["reliability_score"],
            "safety_score": t["safety_score"],
            "data_sensitivity": t["data_sensitivity"],
            "complexity_score": t["complexity_score"],
            "verified_score": t["verified_score"],
            "trust_tier": tier,
            "output_type": t["output_type"],
            "output_format": t["output_format"],
            "system_prompt": t["system_prompt"],
            "hardened_prompt": t["hardened_prompt"],
            "input_schema": json.dumps(t["input_schema"]),
            "model": t["model"],
            "max_tokens": t["max_tokens"],
            "temperature": t["temperature"],
            "status": "approved",
            "version": 1,
            "author_name": t["author_name"],
            "author_email": t["author_email"],
            "deployed": True,
            "deployed_at": now,
            "endpoint_url": f"/tools/{t['slug']}/run",
            "access_token": access_token,
            "instructions_url": f"/api/tools/{t['slug']}/instructions",
            "run_count": t.get("run_count", 0),
            "avg_rating": t.get("avg_rating", 0.0),
            "submitted_at": now,
            "approved_at": now,
            "approved_by": "seed",
        }
        tid = db.insert_tool(row)
        inserted.append((tid, t["slug"]))
    return inserted


def seed_apps():
    """Seed the 3 launch apps (app_type='app'). Skips if slug already exists."""
    inserted = []
    now = datetime.utcnow()
    for a in SEED_APPS:
        if _tool_exists(a["slug"]):
            continue
        tier = compute_trust_tier(
            reliability=a.get("reliability_score", 0),
            safety=a.get("safety_score", 0),
            verified=a.get("verified_score", 0),
            data_sensitivity=a.get("data_sensitivity", "internal"),
            run_count=a.get("run_count", 0),
        )
        access_token = uuid.uuid4().hex
        row = {
            "slug": a["slug"],
            "name": a["name"],
            "tagline": a["tagline"],
            "description": a["description"],
            "category": a["category"],
            "tags": a.get("tags", ""),
            "reliability_score": a.get("reliability_score", 0),
            "safety_score": a.get("safety_score", 0),
            "data_sensitivity": a.get("data_sensitivity", "internal"),
            "complexity_score": a.get("complexity_score", 0),
            "verified_score": a.get("verified_score", 0),
            "trust_tier": tier,
            "output_type": "deterministic",
            "output_format": "text",
            "tool_type": "app",
            "app_type": "app",
            "app_html": a["app_html"],
            "input_schema": json.dumps([]),
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1000,
            "temperature": 0.3,
            "status": "approved",
            "version": 1,
            "author_name": a["author_name"],
            "author_email": a["author_email"],
            "deployed": True,
            "deployed_at": now,
            "endpoint_url": f"/apps/{a['slug']}",
            "access_token": access_token,
            "instructions_url": f"/api/tools/{a['slug']}/instructions",
            "run_count": a.get("run_count", 0),
            "avg_rating": a.get("avg_rating", 0.0),
            "submitted_at": now,
            "approved_at": now,
            "approved_by": "seed",
        }
        tid = db.insert_tool(row)
        inserted.append((tid, a["slug"]))
    return inserted


def _skill_md(name: str, description: str, body: str) -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


def _dedupe_existing_skills():
    """Remove duplicate skill rows, keeping the earliest copy of each title."""
    with db.get_db(dict_cursor=False) as cur:
        cur.execute(
            """
            DELETE FROM skills
            WHERE id NOT IN (
                SELECT MIN(id) FROM skills GROUP BY LOWER(title)
            )
            """
        )


def seed_skills():
    # Real, publicly available skills from:
    #   - obra/superpowers (Jesse Vincent) — https://github.com/obra/superpowers
    #   - anthropics/skills (Anthropic)   — https://github.com/anthropics/skills
    _dedupe_existing_skills()
    skills = [
        # ---------- obra/superpowers ----------
        {
            "title": "brainstorming",
            "description": "Explore intent, requirements, and design before any creative work.",
            "category": "Planning",
            "use_case": "Before creating features, components, or modifying behavior",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/brainstorming",
            "prompt_text": _skill_md(
                "brainstorming",
                "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation.",
                "Use this skill to diverge before converging. Ask open questions about who the "
                "user is, what success looks like, and what constraints exist. Only move to "
                "implementation once the problem shape is clear.",
            ),
        },
        {
            "title": "test-driven-development",
            "description": "Red → Green → Refactor discipline for any feature or bugfix.",
            "category": "Testing",
            "use_case": "Before writing implementation code for a feature or bugfix",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/test-driven-development",
            "prompt_text": _skill_md(
                "test-driven-development",
                "Use when implementing any feature or bugfix, before writing implementation code.",
                "Write the failing test first. Run it and confirm red. Write the minimum code to "
                "make it green. Refactor. Never write production code without a failing test.",
            ),
        },
        {
            "title": "systematic-debugging",
            "description": "Hypothesis-driven root-cause investigation instead of guess-and-patch.",
            "category": "Debugging",
            "use_case": "When hitting any bug, test failure, or unexpected behavior",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/systematic-debugging",
            "prompt_text": _skill_md(
                "systematic-debugging",
                "Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes.",
                "State the observed behavior, the expected behavior, and a hypothesis. Design "
                "the cheapest experiment that would falsify the hypothesis. Iterate until the "
                "root cause is proven, not just plausible.",
            ),
        },
        {
            "title": "verification-before-completion",
            "description": "Prove the work passes before claiming it does. Evidence first.",
            "category": "Code Review",
            "use_case": "Before committing, opening a PR, or claiming a task is done",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/verification-before-completion",
            "prompt_text": _skill_md(
                "verification-before-completion",
                "Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always.",
                "Run the tests. Run the linter. Run the type checker. Start the dev server and "
                "actually use the feature. Only then may you say the work is done.",
            ),
        },
        {
            "title": "writing-plans",
            "description": "Turn a spec into a reviewable, step-by-step implementation plan.",
            "category": "Planning",
            "use_case": "Before touching code on a multi-step task",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/writing-plans",
            "prompt_text": _skill_md(
                "writing-plans",
                "Use when you have a spec or requirements for a multi-step task, before touching code.",
                "Break the work into verifiable steps. Each step states what changes, why, and "
                "how it will be tested. Surface risks up front. Write the plan so a reviewer "
                "can redirect cheaply before code is written.",
            ),
        },
        {
            "title": "executing-plans",
            "description": "Execute a written plan in a separate session with review checkpoints.",
            "category": "Planning",
            "use_case": "When you have a plan ready to implement",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/executing-plans",
            "prompt_text": _skill_md(
                "executing-plans",
                "Use when you have a written implementation plan to execute in a separate session with review checkpoints.",
                "Work one plan step at a time. After each step, stop and summarize what "
                "changed, then wait for the human to redirect or greenlight the next step.",
            ),
        },
        {
            "title": "requesting-code-review",
            "description": "Ask for review so the reviewer can actually redirect you.",
            "category": "Code Review",
            "use_case": "Before merging a branch or completing a feature",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/requesting-code-review",
            "prompt_text": _skill_md(
                "requesting-code-review",
                "Use when completing tasks, implementing major features, or before merging to verify work meets requirements.",
                "State what the change does, why, and what would make it wrong. Point the "
                "reviewer at the riskiest diff and the test that should catch regressions.",
            ),
        },
        {
            "title": "receiving-code-review",
            "description": "Engage feedback with rigor, not performative agreement.",
            "category": "Code Review",
            "use_case": "When responding to code review comments",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/receiving-code-review",
            "prompt_text": _skill_md(
                "receiving-code-review",
                "Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation.",
                "For each comment: restate what the reviewer is asking for, decide whether "
                "you agree, and if you disagree, push back with evidence. Do not blindly apply "
                "suggestions that would break correctness.",
            ),
        },
        {
            "title": "using-git-worktrees",
            "description": "Isolate feature work in a git worktree without disturbing the main checkout.",
            "category": "Development",
            "use_case": "Starting feature work or executing a plan in isolation",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/using-git-worktrees",
            "prompt_text": _skill_md(
                "using-git-worktrees",
                "Use when starting feature work that needs isolation from current workspace or before executing implementation plans - creates isolated git worktrees with smart directory selection and safety verification.",
                "Create a worktree off the correct base branch. Verify clean state. Do the "
                "work. Return to the original checkout before cleaning up.",
            ),
        },
        {
            "title": "dispatching-parallel-agents",
            "description": "Fan out independent work to subagents when there's no shared state.",
            "category": "Development",
            "use_case": "Facing 2+ tasks with no sequential dependency",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/dispatching-parallel-agents",
            "prompt_text": _skill_md(
                "dispatching-parallel-agents",
                "Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies.",
                "Identify which tasks are truly independent. Dispatch each to its own subagent "
                "with a self-contained prompt. Merge results once all return.",
            ),
        },
        {
            "title": "writing-skills",
            "description": "Author new skills that actually get invoked at the right time.",
            "category": "Development",
            "use_case": "Creating or editing a skill",
            "author_name": "obra",
            "source_url": "https://github.com/obra/superpowers/tree/main/skills/writing-skills",
            "prompt_text": _skill_md(
                "writing-skills",
                "Use when creating new skills, editing existing skills, or verifying skills work before deployment.",
                "A skill lives or dies by its description — that's the trigger the model sees. "
                "Write it so the model can tell, from the description alone, exactly when the "
                "skill applies. Test by asking an adjacent question and checking activation.",
            ),
        },
        # ---------- anthropics/skills ----------
        {
            "title": "pdf",
            "description": "Read, extract, create, and edit PDF files (forms, tables, text).",
            "category": "Documents",
            "use_case": "Anything involving PDFs — forms, extraction, generation",
            "author_name": "anthropics",
            "source_url": "https://github.com/anthropics/skills/tree/main/pdf",
            "prompt_text": _skill_md(
                "pdf",
                "Comprehensive PDF processing including form filling, text/table extraction, creation from HTML, merging, splitting, and page manipulation.",
                "Use pypdf / pdfplumber for reading. Use reportlab or HTML-to-PDF for generation. "
                "Fill forms by mapping field names to values. Extract tables with pdfplumber.",
            ),
        },
        {
            "title": "docx",
            "description": "Create and edit Microsoft Word documents while preserving formatting.",
            "category": "Documents",
            "use_case": "Generating or editing .docx files",
            "author_name": "anthropics",
            "source_url": "https://github.com/anthropics/skills/tree/main/docx",
            "prompt_text": _skill_md(
                "docx",
                "Create, read, and edit Microsoft Word .docx files while preserving styles, headings, tables, and track changes.",
                "Use python-docx. Preserve existing styles when inserting content. For track "
                "changes, operate on the underlying XML rather than the high-level API.",
            ),
        },
        {
            "title": "xlsx",
            "description": "Create and edit Excel workbooks — formulas, formatting, multiple sheets.",
            "category": "Documents",
            "use_case": "Building spreadsheets or editing .xlsx files",
            "author_name": "anthropics",
            "source_url": "https://github.com/anthropics/skills/tree/main/xlsx",
            "prompt_text": _skill_md(
                "xlsx",
                "Create and edit Microsoft Excel workbooks, including formulas, number/date formatting, styles, and multi-sheet workbooks.",
                "Use openpyxl. Write formulas as strings beginning with '='. Preserve existing "
                "styles by reading them before overwriting cells.",
            ),
        },
        {
            "title": "pptx",
            "description": "Build PowerPoint decks programmatically with layouts, images, and speaker notes.",
            "category": "Documents",
            "use_case": "Generating presentations",
            "author_name": "anthropics",
            "source_url": "https://github.com/anthropics/skills/tree/main/pptx",
            "prompt_text": _skill_md(
                "pptx",
                "Create and edit Microsoft PowerPoint presentations, including layouts, text, images, tables, and speaker notes.",
                "Use python-pptx. Pick a layout from the template, then populate placeholders "
                "by index. Add speaker notes via slide.notes_slide.notes_text_frame.",
            ),
        },
        {
            "title": "mcp-builder",
            "description": "Scaffold a Model Context Protocol server the right way.",
            "category": "Development",
            "use_case": "Building an MCP server to expose tools to Claude",
            "author_name": "anthropics",
            "source_url": "https://github.com/anthropics/skills/tree/main/mcp-builder",
            "prompt_text": _skill_md(
                "mcp-builder",
                "Build Model Context Protocol (MCP) servers with correct transport, tool registration, and schema definitions.",
                "Start from the official SDK. Define tools with clear JSON schemas. Keep each "
                "tool focused on one action. Test locally with the MCP inspector before "
                "wiring into Claude.",
            ),
        },
        {
            "title": "skill-creator",
            "description": "Create a new skill correctly — frontmatter, trigger, structure.",
            "category": "Development",
            "use_case": "Authoring a new SKILL.md",
            "author_name": "anthropics",
            "source_url": "https://github.com/anthropics/skills/tree/main/skill-creator",
            "prompt_text": _skill_md(
                "skill-creator",
                "Create new skills with correct frontmatter (name, description), trigger phrasing, and directory layout.",
                "A skill is a directory containing SKILL.md. Frontmatter must have 'name' and "
                "'description'. The description is the trigger the model reads — make it "
                "describe when to invoke, not what the skill contains.",
            ),
        },
        {
            "title": "webapp-testing",
            "description": "Drive a browser via Playwright to test UI end-to-end.",
            "category": "Testing",
            "use_case": "Verifying a web app actually works in a real browser",
            "author_name": "anthropics",
            "source_url": "https://github.com/anthropics/skills/tree/main/webapp-testing",
            "prompt_text": _skill_md(
                "webapp-testing",
                "Test web applications via headless browser automation (Playwright): navigate, interact, assert visible state.",
                "Use Playwright's Python or Node binding. Prefer role-based locators "
                "(getByRole) over brittle CSS selectors. Assert on rendered state, not "
                "implementation details.",
            ),
        },
    ]
    inserted = []
    with db.get_db() as cur:
        cur.execute("SELECT LOWER(title) AS title FROM skills")
        existing = {row["title"] for row in cur.fetchall()}
    for s in skills:
        if s["title"].lower() in existing:
            continue
        try:
            sid = db.insert_skill(s)
            inserted.append(sid)
            existing.add(s["title"].lower())
        except Exception:
            pass
    return inserted


def main():
    print("Initializing database...")
    try:
        db.init_db()
    except Exception as e:
        print(f"[warn] init_db: {e}")

    print("Seeding tools...")
    tools = seed_tools()
    print(f"  inserted {len(tools)} tools")

    print("Seeding apps...")
    apps = seed_apps()
    print(f"  inserted {len(apps)} apps")

    print("Seeding skills...")
    skills = seed_skills()
    print(f"  inserted {len(skills)} skills")


if __name__ == "__main__":
    main()
