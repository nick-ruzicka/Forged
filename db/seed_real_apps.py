"""
Seed the catalog with real, working items.

Three embedded apps + one external app (Meetily).
Each app is genuinely functional, not AI-generated sketches.
Run: venv/bin/python3 db/seed_real_apps.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import db


# ---------------------------------------------------------------------------
# 1. MARKDOWN EDITOR (embedded)
# ---------------------------------------------------------------------------
MARKDOWN_EDITOR_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Markdown Editor</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
<style>
:root { --bg:#0d0d0d; --surface:#141414; --border:#2a2a2a; --text:#e0e0e0; --muted:#888; --accent:#0066FF; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, system-ui, sans-serif; height: 100vh; display: flex; flex-direction: column; }
.toolbar { display: flex; gap: 6px; padding: 10px 14px; background: var(--surface); border-bottom: 1px solid var(--border); flex-wrap: wrap; align-items: center; }
.toolbar button { background: #1f1f1f; color: var(--text); border: 1px solid var(--border); padding: 6px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; font-family: ui-monospace, Menlo, monospace; }
.toolbar button:hover { background: #2a2a2a; border-color: var(--accent); }
.toolbar .spacer { flex: 1; }
.toolbar .meta { color: var(--muted); font-size: 12px; }
.panes { flex: 1; display: grid; grid-template-columns: 1fr 1fr; min-height: 0; }
.pane { display: flex; flex-direction: column; min-height: 0; }
.pane-header { padding: 6px 14px; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; background: var(--surface); border-bottom: 1px solid var(--border); }
#editor { flex: 1; background: var(--bg); color: var(--text); border: none; padding: 14px; font-family: ui-monospace, Menlo, monospace; font-size: 13px; line-height: 1.55; resize: none; outline: none; }
#preview { flex: 1; padding: 14px 20px; overflow: auto; line-height: 1.55; border-left: 1px solid var(--border); }
#preview h1, #preview h2, #preview h3 { color: #fff; margin-top: 1.2em; }
#preview h1 { font-size: 22px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
#preview h2 { font-size: 18px; }
#preview a { color: var(--accent); }
#preview code { background: #1a1a1a; padding: 2px 6px; border-radius: 3px; font-size: 90%; }
#preview pre { background: #1a1a1a; padding: 12px; border-radius: 6px; overflow: auto; }
#preview pre code { background: transparent; padding: 0; }
#preview blockquote { border-left: 3px solid var(--accent); margin: 0; padding-left: 14px; color: var(--muted); }
#preview table { border-collapse: collapse; }
#preview th, #preview td { border: 1px solid var(--border); padding: 6px 10px; }
#preview hr { border: none; border-top: 1px solid var(--border); margin: 20px 0; }
@media (max-width: 720px) { .panes { grid-template-columns: 1fr; } #preview { border-left: none; border-top: 1px solid var(--border); } }
</style>
</head>
<body>
<div class="toolbar">
  <button data-wrap="**">Bold</button>
  <button data-wrap="*">Italic</button>
  <button data-wrap="`">Code</button>
  <button data-prefix="# ">H1</button>
  <button data-prefix="## ">H2</button>
  <button data-prefix="- ">List</button>
  <button data-prefix="> ">Quote</button>
  <button data-link>Link</button>
  <span class="spacer"></span>
  <span class="meta" id="meta">0 chars · 0 words</span>
  <button id="copy-md">Copy MD</button>
  <button id="copy-html">Copy HTML</button>
  <button id="download">Download .md</button>
</div>
<div class="panes">
  <div class="pane">
    <div class="pane-header">Markdown</div>
    <textarea id="editor" spellcheck="false" placeholder="Type Markdown here..."></textarea>
  </div>
  <div class="pane">
    <div class="pane-header">Preview</div>
    <div id="preview"></div>
  </div>
</div>
<script>
const editor = document.getElementById('editor');
const preview = document.getElementById('preview');
const meta = document.getElementById('meta');
const STORAGE = 'forge_markdown_editor_v1';

async function loadInitial() {
  let saved = '';
  try { if (window.ForgeAPI && window.ForgeAPI.getData) saved = await window.ForgeAPI.getData('doc'); } catch(e) {}
  if (!saved) {
    try { saved = localStorage.getItem(STORAGE) || ''; } catch(e) {}
  }
  if (!saved) saved = '# Welcome\n\nThis is a Markdown editor.\n\n- Edit on the **left**\n- See preview on the **right**\n- Auto-saves as you type\n\n## Try it\n\n```js\nconsole.log("hello");\n```\n\n> Quotes look like this.\n';
  editor.value = saved;
  render();
}

function render() {
  preview.innerHTML = marked.parse(editor.value || '');
  const text = editor.value || '';
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  meta.textContent = `${text.length} chars · ${words} words`;
}

let saveTimer;
function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try { localStorage.setItem(STORAGE, editor.value); } catch(e) {}
    try { if (window.ForgeAPI && window.ForgeAPI.setData) await window.ForgeAPI.setData('doc', editor.value); } catch(e) {}
  }, 600);
}

editor.addEventListener('input', () => { render(); save(); });

document.querySelectorAll('[data-wrap]').forEach(btn => btn.addEventListener('click', () => {
  const wrap = btn.dataset.wrap;
  const s = editor.selectionStart, e = editor.selectionEnd;
  const sel = editor.value.slice(s, e) || 'text';
  editor.value = editor.value.slice(0, s) + wrap + sel + wrap + editor.value.slice(e);
  editor.focus();
  editor.setSelectionRange(s + wrap.length, s + wrap.length + sel.length);
  render(); save();
}));

document.querySelectorAll('[data-prefix]').forEach(btn => btn.addEventListener('click', () => {
  const pre = btn.dataset.prefix;
  const s = editor.selectionStart;
  // find start of line
  const lineStart = editor.value.lastIndexOf('\n', s - 1) + 1;
  editor.value = editor.value.slice(0, lineStart) + pre + editor.value.slice(lineStart);
  editor.focus();
  editor.setSelectionRange(s + pre.length, s + pre.length);
  render(); save();
}));

document.querySelector('[data-link]').addEventListener('click', () => {
  const url = prompt('Link URL:'); if (!url) return;
  const s = editor.selectionStart, e = editor.selectionEnd;
  const sel = editor.value.slice(s, e) || 'link text';
  editor.value = editor.value.slice(0, s) + `[${sel}](${url})` + editor.value.slice(e);
  render(); save();
});

document.getElementById('copy-md').addEventListener('click', async () => {
  await navigator.clipboard.writeText(editor.value);
});
document.getElementById('copy-html').addEventListener('click', async () => {
  await navigator.clipboard.writeText(preview.innerHTML);
});
document.getElementById('download').addEventListener('click', () => {
  const blob = new Blob([editor.value], { type: 'text/markdown' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'note.md';
  a.click();
});

loadInitial();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 2. REGEX TESTER (embedded)
# ---------------------------------------------------------------------------
REGEX_TESTER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Regex Tester</title>
<style>
:root { --bg:#0d0d0d; --surface:#141414; --border:#2a2a2a; --text:#e0e0e0; --muted:#888; --accent:#0066FF; --hl:#ffeb3b40; --hl-current:#ffc10780; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, system-ui, sans-serif; padding: 24px; max-width: 980px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 6px; }
.subtitle { color: var(--muted); font-size: 14px; margin-bottom: 24px; }
.pattern-row { display: flex; gap: 8px; align-items: stretch; margin-bottom: 8px; }
.slash { font-family: ui-monospace, Menlo, monospace; font-size: 18px; color: var(--muted); display: flex; align-items: center; padding: 0 4px; }
#pattern { flex: 1; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 12px; font-family: ui-monospace, Menlo, monospace; font-size: 14px; border-radius: 6px; }
#pattern:focus { outline: 1px solid var(--accent); border-color: var(--accent); }
#pattern.invalid { border-color: #f44336; }
#flags { width: 120px; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 12px; font-family: ui-monospace, Menlo, monospace; font-size: 14px; border-radius: 6px; }
.error { color: #ff8a80; font-size: 12px; margin: 4px 0 12px; min-height: 16px; }
.presets { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 18px; }
.presets button { background: #1f1f1f; color: var(--text); border: 1px solid var(--border); padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.presets button:hover { border-color: var(--accent); }
.section { margin-bottom: 18px; }
.section-label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
#test { width: 100%; min-height: 160px; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 12px; font-family: ui-monospace, Menlo, monospace; font-size: 13px; line-height: 1.6; border-radius: 6px; resize: vertical; }
#highlighted { white-space: pre-wrap; word-wrap: break-word; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 12px; font-family: ui-monospace, Menlo, monospace; font-size: 13px; line-height: 1.6; border-radius: 6px; min-height: 160px; }
mark { background: var(--hl); color: inherit; padding: 1px 0; border-radius: 2px; cursor: pointer; }
mark.current { background: var(--hl-current); }
.match-list { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; max-height: 280px; overflow: auto; }
.match-item { padding: 10px 14px; border-bottom: 1px solid var(--border); cursor: pointer; }
.match-item:last-child { border-bottom: none; }
.match-item:hover { background: #1f1f1f; }
.match-item.current { background: #0d1a2e; }
.match-num { color: var(--muted); font-size: 11px; margin-right: 8px; }
.match-text { font-family: ui-monospace, Menlo, monospace; color: #ffeb3b; }
.match-groups { color: var(--muted); font-size: 11px; margin-top: 4px; padding-left: 32px; }
.summary { color: var(--muted); font-size: 13px; margin-top: 8px; }
</style>
</head>
<body>
<h1>Regex Tester</h1>
<p class="subtitle">Test regular expressions against text. Highlights matches, shows capture groups.</p>

<div class="section">
  <div class="section-label">Pattern</div>
  <div class="pattern-row">
    <span class="slash">/</span>
    <input id="pattern" type="text" spellcheck="false" placeholder="\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b">
    <span class="slash">/</span>
    <input id="flags" type="text" spellcheck="false" placeholder="g, i, m..." value="gi">
  </div>
  <div class="error" id="error"></div>
  <div class="presets">
    <span style="color:var(--muted);font-size:12px;align-self:center;">Presets:</span>
    <button data-preset='{"p":"\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b","f":"gi"}'>Email</button>
    <button data-preset='{"p":"https?:\\/\\/[\\w\\d.\\-_]+(?:\\/[\\w\\d.\\-_~:?#@!$&%\\+,;=*]*)?","f":"gi"}'>URL</button>
    <button data-preset='{"p":"\\b\\d{3}[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b","f":"g"}'>US Phone</button>
    <button data-preset='{"p":"\\d{3}-\\d{2}-\\d{4}","f":"g"}'>SSN</button>
    <button data-preset='{"p":"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\\b","f":"g"}'>Hex Color</button>
    <button data-preset='{"p":"\\b\\d{4}[-\\s]?\\d{4}[-\\s]?\\d{4}[-\\s]?\\d{4}\\b","f":"g"}'>Credit Card</button>
  </div>
</div>

<div class="section">
  <div class="section-label">Test string</div>
  <textarea id="test" spellcheck="false" placeholder="Paste text here...">Email me at sarah@navan.com or marcus.patel+contact@example.co.uk.
You can also reach me at 555-123-4567 or visit https://navan.com/contact.
The deal closed on March 5 for $124,500 (ID: deal_98a-7c23).</textarea>
</div>

<div class="section">
  <div class="section-label">Result</div>
  <div id="highlighted"></div>
  <div class="summary" id="summary"></div>
</div>

<div class="section">
  <div class="section-label">Matches</div>
  <div id="matches" class="match-list"></div>
</div>

<script>
const patternInput = document.getElementById('pattern');
const flagsInput = document.getElementById('flags');
const testInput = document.getElementById('test');
const highlighted = document.getElementById('highlighted');
const errorEl = document.getElementById('error');
const summary = document.getElementById('summary');
const matchesEl = document.getElementById('matches');

let currentMatchIdx = -1;
let lastMatches = [];

function escapeHtml(s) { return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function update() {
  const pattern = patternInput.value;
  const flags = flagsInput.value;
  errorEl.textContent = '';
  patternInput.classList.remove('invalid');
  if (!pattern) {
    highlighted.textContent = testInput.value;
    summary.textContent = '';
    matchesEl.innerHTML = '';
    return;
  }
  let re;
  try { re = new RegExp(pattern, flags.includes('g') ? flags : flags + 'g'); }
  catch (e) { errorEl.textContent = 'Invalid regex: ' + e.message; patternInput.classList.add('invalid'); return; }

  const text = testInput.value;
  const matches = [...text.matchAll(re)];
  lastMatches = matches;

  // Build highlighted HTML
  if (matches.length === 0) {
    highlighted.innerHTML = escapeHtml(text);
    summary.textContent = 'No matches.';
    matchesEl.innerHTML = '<div style="padding:14px;color:var(--muted);font-size:13px;">No matches found.</div>';
    return;
  }
  let html = '';
  let idx = 0;
  matches.forEach((m, i) => {
    html += escapeHtml(text.slice(idx, m.index));
    html += `<mark data-i="${i}">${escapeHtml(m[0])}</mark>`;
    idx = m.index + m[0].length;
  });
  html += escapeHtml(text.slice(idx));
  highlighted.innerHTML = html;
  summary.textContent = `${matches.length} match${matches.length === 1 ? '' : 'es'}.`;

  // Match list
  matchesEl.innerHTML = matches.map((m, i) => {
    const groups = m.length > 1 ? `<div class="match-groups">${m.slice(1).map((g, gi) => `Group ${gi + 1}: <span style="color:#9cc8ff;">${g === undefined ? '(undefined)' : escapeHtml(g)}</span>`).join(' · ')}</div>` : '';
    return `<div class="match-item" data-i="${i}"><span class="match-num">#${i + 1}</span><span class="match-text">${escapeHtml(m[0])}</span>${groups}</div>`;
  }).join('');
  attachMatchHandlers();
}

function attachMatchHandlers() {
  document.querySelectorAll('.match-item').forEach(el => {
    el.addEventListener('click', () => focusMatch(parseInt(el.dataset.i)));
  });
  document.querySelectorAll('mark').forEach(el => {
    el.addEventListener('click', () => focusMatch(parseInt(el.dataset.i)));
  });
}

function focusMatch(i) {
  currentMatchIdx = i;
  document.querySelectorAll('mark').forEach((el, idx) => el.classList.toggle('current', idx === i));
  document.querySelectorAll('.match-item').forEach((el, idx) => el.classList.toggle('current', idx === i));
}

[patternInput, flagsInput, testInput].forEach(el => el.addEventListener('input', update));
document.querySelectorAll('[data-preset]').forEach(btn => btn.addEventListener('click', () => {
  const preset = JSON.parse(btn.dataset.preset);
  patternInput.value = preset.p;
  flagsInput.value = preset.f;
  update();
}));

// Restore from ForgeAPI
(async function restore() {
  try {
    if (window.ForgeAPI && window.ForgeAPI.getData) {
      const saved = await window.ForgeAPI.getData('regex_state');
      if (saved && typeof saved === 'object') {
        patternInput.value = saved.pattern || '';
        flagsInput.value = saved.flags || 'gi';
        if (saved.test) testInput.value = saved.test;
      }
    }
  } catch (e) {}
  update();
})();

let saveTimer;
function persist() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try { if (window.ForgeAPI && window.ForgeAPI.setData) window.ForgeAPI.setData('regex_state', { pattern: patternInput.value, flags: flagsInput.value, test: testInput.value }); } catch(e) {}
  }, 800);
}
[patternInput, flagsInput, testInput].forEach(el => el.addEventListener('input', persist));
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 3. JSON FORMATTER (embedded)
# ---------------------------------------------------------------------------
JSON_FORMATTER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>JSON Formatter</title>
<style>
:root { --bg:#0d0d0d; --surface:#141414; --border:#2a2a2a; --text:#e0e0e0; --muted:#888; --accent:#0066FF; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, system-ui, sans-serif; height: 100vh; display: flex; flex-direction: column; }
.toolbar { display: flex; gap: 6px; padding: 10px 14px; background: var(--surface); border-bottom: 1px solid var(--border); align-items: center; flex-wrap: wrap; }
.toolbar button { background: #1f1f1f; color: var(--text); border: 1px solid var(--border); padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.toolbar button.primary { background: var(--accent); border-color: var(--accent); color: white; }
.toolbar button:hover { border-color: var(--accent); }
.toolbar .spacer { flex: 1; }
.toolbar .meta { color: var(--muted); font-size: 12px; font-family: ui-monospace, Menlo, monospace; }
.toolbar .meta.error { color: #ff8a80; }
.toolbar select { background: #1f1f1f; color: var(--text); border: 1px solid var(--border); padding: 6px 8px; border-radius: 4px; font-size: 12px; }
.panes { flex: 1; display: grid; grid-template-columns: 1fr 1fr; min-height: 0; }
.pane { display: flex; flex-direction: column; min-height: 0; }
.pane-header { padding: 6px 14px; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; background: var(--surface); border-bottom: 1px solid var(--border); }
#input, #output { flex: 1; background: var(--bg); color: var(--text); border: none; padding: 14px; font-family: ui-monospace, Menlo, monospace; font-size: 12.5px; line-height: 1.55; resize: none; outline: none; }
#output { border-left: 1px solid var(--border); white-space: pre; overflow: auto; }
.tk-key { color: #9cc8ff; }
.tk-string { color: #c3e88d; }
.tk-number { color: #f78c6c; }
.tk-bool { color: #ff5370; }
.tk-null { color: #c792ea; }
.tk-punct { color: var(--muted); }
@media (max-width: 720px) { .panes { grid-template-columns: 1fr; } #output { border-left: none; border-top: 1px solid var(--border); } }
</style>
</head>
<body>
<div class="toolbar">
  <button class="primary" id="format-btn">Format</button>
  <button id="minify-btn">Minify</button>
  <button id="copy-btn">Copy output</button>
  <span style="color:var(--muted);font-size:12px;">Indent:</span>
  <select id="indent">
    <option value="2" selected>2 spaces</option>
    <option value="4">4 spaces</option>
    <option value="\t">Tabs</option>
  </select>
  <button id="sample-btn">Load sample</button>
  <span class="spacer"></span>
  <span class="meta" id="meta">Paste JSON to start</span>
</div>
<div class="panes">
  <div class="pane">
    <div class="pane-header">Input</div>
    <textarea id="input" spellcheck="false" placeholder='{"paste": "JSON here"}'></textarea>
  </div>
  <div class="pane">
    <div class="pane-header">Output</div>
    <pre id="output" tabindex="0"></pre>
  </div>
</div>
<script>
const input = document.getElementById('input');
const output = document.getElementById('output');
const meta = document.getElementById('meta');
const indentSel = document.getElementById('indent');

const SAMPLE = JSON.stringify({
  account: { id: "acc_8a23", name: "Acme Corp", arr: 240000, tier: "enterprise" },
  contacts: [
    { name: "Sarah Chen", role: "Champion", email: "sarah@acme.com" },
    { name: "Marcus Patel", role: "Decision Maker", email: "marcus@acme.com" }
  ],
  open_opps: [
    { id: "opp_1", stage: "Negotiation", amount: 45000, close_date: "2026-04-30" }
  ],
  last_activity: null,
  is_at_risk: false
});

function escapeHtml(s) { return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function tokenize(text) {
  // Walk char-by-char; classify outside-string vs inside-string
  let html = '';
  let i = 0;
  const n = text.length;
  while (i < n) {
    const c = text[i];
    if (c === '"') {
      // string — could be a key or value. Look ahead for closing quote (handle escapes).
      let end = i + 1;
      while (end < n) {
        if (text[end] === '\\') { end += 2; continue; }
        if (text[end] === '"') break;
        end++;
      }
      const str = text.slice(i, end + 1);
      // Determine if this is an object key: skip whitespace forward; if next non-space is ':' it's a key.
      let look = end + 1;
      while (look < n && /\s/.test(text[look])) look++;
      const isKey = text[look] === ':';
      html += `<span class="${isKey ? 'tk-key' : 'tk-string'}">${escapeHtml(str)}</span>`;
      i = end + 1;
    } else if (c === 't' && text.slice(i, i + 4) === 'true') { html += '<span class="tk-bool">true</span>'; i += 4; }
    else if (c === 'f' && text.slice(i, i + 5) === 'false') { html += '<span class="tk-bool">false</span>'; i += 5; }
    else if (c === 'n' && text.slice(i, i + 4) === 'null') { html += '<span class="tk-null">null</span>'; i += 4; }
    else if (/[-0-9]/.test(c)) {
      let m = text.slice(i).match(/^-?\d+(\.\d+)?([eE][+-]?\d+)?/);
      if (m) { html += `<span class="tk-number">${m[0]}</span>`; i += m[0].length; continue; }
      html += escapeHtml(c); i++;
    }
    else if ('{}[]:,'.includes(c)) { html += `<span class="tk-punct">${c}</span>`; i++; }
    else { html += escapeHtml(c); i++; }
  }
  return html;
}

function indentSize() {
  const v = indentSel.value;
  return v === '\\t' ? '\t' : parseInt(v) || 2;
}

function format() {
  const raw = input.value.trim();
  if (!raw) { output.innerHTML = ''; meta.textContent = 'Paste JSON to start'; meta.classList.remove('error'); return; }
  try {
    const parsed = JSON.parse(raw);
    const pretty = JSON.stringify(parsed, null, indentSize());
    output.innerHTML = tokenize(pretty);
    const size = new Blob([pretty]).size;
    meta.textContent = `valid · ${size} bytes`;
    meta.classList.remove('error');
  } catch (e) {
    output.innerHTML = '';
    meta.textContent = 'Invalid: ' + e.message;
    meta.classList.add('error');
  }
}

function minify() {
  const raw = input.value.trim();
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw);
    const minified = JSON.stringify(parsed);
    input.value = minified;
    output.innerHTML = tokenize(minified);
    meta.textContent = `valid · ${new Blob([minified]).size} bytes (minified)`;
    meta.classList.remove('error');
    persist();
  } catch (e) {
    meta.textContent = 'Invalid: ' + e.message;
    meta.classList.add('error');
  }
}

document.getElementById('format-btn').addEventListener('click', format);
document.getElementById('minify-btn').addEventListener('click', minify);
document.getElementById('copy-btn').addEventListener('click', async () => {
  await navigator.clipboard.writeText(output.innerText);
});
document.getElementById('sample-btn').addEventListener('click', () => {
  input.value = SAMPLE;
  format();
  persist();
});
indentSel.addEventListener('change', format);

let formatTimer;
input.addEventListener('input', () => {
  clearTimeout(formatTimer);
  formatTimer = setTimeout(() => { format(); persist(); }, 250);
});

let saveTimer;
function persist() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try { if (window.ForgeAPI && window.ForgeAPI.setData) window.ForgeAPI.setData('input', input.value); } catch(e) {}
  }, 600);
}

(async function restore() {
  try {
    if (window.ForgeAPI && window.ForgeAPI.getData) {
      const saved = await window.ForgeAPI.getData('input');
      if (saved) input.value = saved;
    }
  } catch (e) {}
  format();
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 4. MEETILY (external) — no app_html, just a catalog entry pointing at the install
# ---------------------------------------------------------------------------
MEETILY_DESCRIPTION = """\
Meetily is the open-source alternative to Granola. Captures meeting audio, transcribes \
locally with Whisper, generates AI-enhanced notes — entirely on your machine, no SaaS.

**Why teams choose this over Granola:**
- Privacy: nothing leaves your laptop
- Free, MIT-licensed
- Use any LLM (Ollama, Groq, Anthropic, OpenAI)
- Multi-language transcription support
- Works offline once installed

**System requirements:** macOS Monterey or later, Apple Silicon recommended."""


MEETILY_INSTALL = """\
# 1. Tap the formula
brew tap zackriya-solutions/meetily

# 2. Install the desktop app + the backend
brew install --cask meetily
brew install meetily-backend

# 3. Start the backend (in a terminal — leave it running)
meetily-server --language en --model medium

# 4. Open the Meetily app from your Applications folder."""


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------
ITEMS = [
    {
        "slug": "markdown-editor",
        "name": "Markdown Editor",
        "tagline": "Write Markdown with live preview, auto-saving as you type.",
        "description": (
            "A clean two-pane Markdown editor with live preview. Toolbar shortcuts for "
            "bold, italic, code, headings, lists, quotes, and links. Auto-saves your "
            "doc to your Forge profile so it persists across devices. Copy MD or HTML, "
            "or download as a .md file."
        ),
        "category": "Writing",
        "delivery": "embedded",
        "trust_tier": "trusted",
        "app_html": MARKDOWN_EDITOR_HTML,
        "icon": "✎",
        "tags": "markdown,notes,writing,editor",
    },
    {
        "slug": "regex-tester",
        "name": "Regex Tester",
        "tagline": "Test regular expressions live with highlighted matches and capture groups.",
        "description": (
            "Type a regex pattern and a test string. Matches are highlighted inline and "
            "listed with capture groups. Includes presets for email, URL, phone, SSN, "
            "credit cards, and hex colors. State persists in your Forge profile."
        ),
        "category": "Developer Tools",
        "delivery": "embedded",
        "trust_tier": "trusted",
        "app_html": REGEX_TESTER_HTML,
        "icon": "⌘",
        "tags": "regex,developer,validation,patterns",
    },
    {
        "slug": "json-formatter",
        "name": "JSON Formatter",
        "tagline": "Pretty-print, minify, and inspect JSON with syntax highlighting.",
        "description": (
            "Paste JSON, get formatted output with syntax highlighting. Configurable "
            "indentation (2/4 spaces or tabs). Minify, copy, or save. Shows byte count "
            "and parse errors with line numbers."
        ),
        "category": "Developer Tools",
        "delivery": "embedded",
        "trust_tier": "trusted",
        "app_html": JSON_FORMATTER_HTML,
        "icon": "{ }",
        "tags": "json,developer,formatter,parser",
    },
    {
        "slug": "meetily",
        "name": "Meetily",
        "tagline": "Open-source AI meeting notes. Runs locally, your data never leaves your machine.",
        "description": MEETILY_DESCRIPTION,
        "category": "Meetings",
        "delivery": "external",
        "trust_tier": "verified",
        "app_html": None,
        "install_command": MEETILY_INSTALL,
        "source_url": "https://github.com/Zackriya-Solutions/meeting-minutes",
        "launch_url": None,  # launched via the OS; no URL
        "icon": "🎙️",
        "tags": "meetings,transcription,ai,local,privacy",
    },
]


def main() -> int:
    inserted = 0
    skipped = 0
    for item in ITEMS:
        with db.get_db() as cur:
            cur.execute("SELECT id FROM tools WHERE slug = %s", (item["slug"],))
            existing = cur.fetchone()
            if existing:
                print(f"  skip   {item['slug']} (already exists, id={existing['id']})")
                skipped += 1
                continue

        row = {
            "slug": item["slug"],
            "name": item["name"],
            "tagline": item["tagline"],
            "description": item["description"],
            "category": item["category"],
            "tags": item.get("tags") or "",
            "trust_tier": item.get("trust_tier") or "verified",
            "app_type": "app",
            "app_html": item.get("app_html"),
            "delivery": item["delivery"],
            "install_command": item.get("install_command"),
            "source_url": item.get("source_url"),
            "launch_url": item.get("launch_url"),
            "icon": item.get("icon"),
            "status": "approved",
            "version": 1,
            "author_name": "Forge Seed",
            "author_email": "seed@forge.internal",
            "deployed": True,
            "deployed_at": datetime.utcnow(),
            "endpoint_url": f"/apps/{item['slug']}",
            "approved_at": datetime.utcnow(),
            "approved_by": "seed",
            "submitted_at": datetime.utcnow(),
        }
        new_id = db.insert_tool(row)
        print(f"  insert {item['slug']} (id={new_id}, delivery={item['delivery']})")
        inserted += 1

    print(f"\nseed complete: {inserted} inserted, {skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
