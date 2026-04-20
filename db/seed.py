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
