/* Forge Admin UI — T4
 * Tab switching, queue/live/runs/analytics/settings.
 * Auth: X-Admin-Key from localStorage key "forge_admin_key".
 */
(function () {
  "use strict";

  // ---------------- Key management ----------------

  const KEY_STORAGE = "forge_admin_key";
  const SETTINGS_STORAGE = "forge_admin_settings";

  function getKey() {
    try { return localStorage.getItem(KEY_STORAGE) || ""; } catch (_) { return ""; }
  }
  function setKey(k) {
    try { localStorage.setItem(KEY_STORAGE, k); } catch (_) { /* ignore */ }
  }
  function clearKey() {
    try { localStorage.removeItem(KEY_STORAGE); } catch (_) { /* ignore */ }
  }

  function showKeySetup() {
    document.getElementById("key-setup").classList.remove("hidden");
    document.getElementById("admin-main").classList.add("hidden");
    const badge = document.getElementById("queue-badge");
    if (badge) badge.classList.add("hidden");
    const input = document.getElementById("key-input");
    input.focus();
  }
  function showAdmin() {
    document.getElementById("key-setup").classList.add("hidden");
    document.getElementById("admin-main").classList.remove("hidden");
  }

  // ---------------- API helper ----------------

  async function api(method, path, body) {
    const opts = {
      method: method,
      headers: {
        "X-Admin-Key": getKey(),
      },
    };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (res.status === 401) {
      toast("Admin key rejected — clearing.", "error");
      clearKey();
      showKeySetup();
      throw new Error("unauthorized");
    }
    let data = null;
    try { data = await res.json(); } catch (_) { data = null; }
    if (!res.ok) {
      const msg = (data && (data.error || data.message)) || ("HTTP " + res.status);
      throw new Error(msg);
    }
    return data;
  }

  // ---------------- Toasts ----------------

  function toast(msg, kind) {
    const wrap = document.getElementById("toasts");
    const el = document.createElement("div");
    el.className = "toast " + (kind || "");
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      el.style.transition = "opacity .3s";
    }, 2600);
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 3000);
  }

  // ---------------- Modal ----------------

  function openModal(html) {
    const root = document.getElementById("modal-root");
    root.innerHTML = "";
    const back = document.createElement("div");
    back.className = "modal-backdrop";
    back.addEventListener("click", function (e) {
      if (e.target === back) closeModal();
    });
    const m = document.createElement("div");
    m.className = "modal";
    m.innerHTML = '<button class="close" aria-label="Close">×</button>' + html;
    m.querySelector(".close").addEventListener("click", closeModal);
    back.appendChild(m);
    root.appendChild(back);
    return m;
  }
  function closeModal() {
    document.getElementById("modal-root").innerHTML = "";
  }

  // ---------------- Utilities ----------------

  function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fmtDate(s) {
    if (!s) return "—";
    try {
      const d = new Date(s);
      if (isNaN(d.getTime())) return String(s);
      return d.toLocaleString();
    } catch (_) { return String(s); }
  }

  function fmtRel(s) {
    if (!s) return "—";
    const d = new Date(s);
    if (isNaN(d.getTime())) return String(s);
    const secs = Math.floor((Date.now() - d.getTime()) / 1000);
    if (secs < 60) return secs + "s ago";
    if (secs < 3600) return Math.floor(secs / 60) + "m ago";
    if (secs < 86400) return Math.floor(secs / 3600) + "h ago";
    return Math.floor(secs / 86400) + "d ago";
  }

  function trustBadge(tier) {
    const t = (tier || "unverified").toLowerCase();
    const label = t.charAt(0).toUpperCase() + t.slice(1);
    return '<span class="badge ' + esc(t) + '">' + esc(label) + "</span>";
  }

  function recBadge(rec) {
    if (!rec) return "";
    const cls = "rec-" + String(rec).toLowerCase().replace(/\s+/g, "_");
    const label = String(rec).replace(/_/g, " ");
    return '<span class="badge ' + esc(cls) + '">' + esc(label) + "</span>";
  }

  function scoreBar(value) {
    const v = Math.max(0, Math.min(100, Number(value) || 0));
    return '<div class="score-bar"><span style="width:' + v + '%"></span></div>';
  }

  function inputSchemaFields(tool) {
    let schema = tool.input_schema;
    if (typeof schema === "string") {
      try { schema = JSON.parse(schema); } catch (_) { schema = []; }
    }
    return Array.isArray(schema) ? schema : [];
  }

  // ---------------- Tab switching ----------------

  const TAB_LOADERS = {
    queue: loadQueue,
    live: loadLiveTools,
    runs: loadRunMonitor,
    analytics: loadAnalytics,
    settings: loadSettings,
  };

  function setActiveTab(name) {
    document.querySelectorAll(".tab").forEach(function (t) {
      t.classList.toggle("active", t.dataset.tab === name);
    });
    document.querySelectorAll(".tab-pane").forEach(function (p) {
      p.classList.toggle("hidden", p.id !== "tab-" + name);
    });
    if (typeof TAB_LOADERS[name] === "function") TAB_LOADERS[name]();
  }

  document.addEventListener("click", function (e) {
    const t = e.target.closest(".tab");
    if (t && t.dataset.tab) {
      e.preventDefault();
      setActiveTab(t.dataset.tab);
    }
  });

  // ---------------- Queue badge ----------------

  async function refreshQueueBadge() {
    try {
      const data = await api("GET", "/api/admin/queue/count");
      const n = Number(data && data.count) || 0;
      const el = document.getElementById("queue-badge");
      el.textContent = String(n);
      el.classList.toggle("zero", n === 0);
      el.classList.remove("hidden");
    } catch (_) {
      const el = document.getElementById("queue-badge");
      if (el) el.classList.add("hidden");
    }
  }

  // ---------------- Queue tab ----------------

  let QUEUE_CACHE = [];

  async function loadQueue() {
    const root = document.getElementById("queue-root");
    root.innerHTML = '<div class="muted">Loading queue…</div>';
    try {
      const data = await api("GET", "/api/admin/queue");
      QUEUE_CACHE = (data && data.tools) || [];
      renderQueue(QUEUE_CACHE);
    } catch (err) {
      root.innerHTML = '<div class="panel">Failed to load queue: ' + esc(err.message) + "</div>";
    }
  }

  function renderQueue(tools) {
    const root = document.getElementById("queue-root");
    if (!tools.length) {
      root.innerHTML = '<div class="panel">Queue is empty — no tools pending review.</div>';
      return;
    }
    const head = '<h2>' + tools.length + " tool" + (tools.length === 1 ? "" : "s") + " pending review</h2>";
    const rows = tools.map(queueRowHtml).join("");
    root.innerHTML = head + rows;

    tools.forEach(function (t) {
      const expandBtn = document.querySelector('[data-expand="' + t.id + '"]');
      if (expandBtn) expandBtn.addEventListener("click", function () { toggleReview(t.id); });
    });
  }

  function queueRowHtml(tool) {
    const review = tool.agent_review || {};
    const rec = review.agent_recommendation || "pending";
    const conf = review.agent_confidence != null ? Math.round(Number(review.agent_confidence) * 100) + "%" : "—";
    const submitted = tool.submitted_at || tool.created_at;
    return (
      '<div class="panel review-card" id="queue-row-' + tool.id + '">' +
        '<div class="spread">' +
          '<div>' +
            '<div style="font-weight:600;font-size:15px">' + esc(tool.name) +
              ' <span class="muted small">v' + esc(tool.version || 1) + '</span>' +
            '</div>' +
            '<div class="muted small">' +
              esc(tool.author_name || "unknown") + ' · ' + esc(fmtRel(submitted)) +
              ' · category: ' + esc(tool.category || "—") +
            '</div>' +
            '<div style="margin-top:6px">' + recBadge(rec) +
              ' <span class="muted small" style="margin-left:6px">confidence: ' + esc(conf) + "</span>" +
            '</div>' +
          '</div>' +
          '<div class="row">' +
            '<button class="btn small" data-expand="' + tool.id + '">View Full Review</button>' +
          '</div>' +
        '</div>' +
        '<div class="review-body hidden" id="review-body-' + tool.id + '"></div>' +
      '</div>'
    );
  }

  function toggleReview(toolId) {
    const body = document.getElementById("review-body-" + toolId);
    if (!body) return;
    if (!body.classList.contains("hidden")) {
      body.classList.add("hidden");
      return;
    }
    const tool = QUEUE_CACHE.find(function (x) { return x.id === toolId; });
    if (!tool) return;
    body.innerHTML = reviewPanelHtml(tool);
    body.classList.remove("hidden");
    wireReviewPanel(tool);
  }

  // ---------------- Review Panel ----------------

  function reviewPanelHtml(tool) {
    const review = tool.agent_review || {};
    const rec = review.agent_recommendation || "pending";
    const conf = review.agent_confidence != null ? Math.round(Number(review.agent_confidence) * 100) : 0;

    return (
      '<hr style="border:0;border-top:1px solid var(--border);margin:12px 0">' +
      '<div class="kv">' +
        '<div class="k">Tagline</div><div>' + esc(tool.tagline || "") + '</div>' +
        '<div class="k">Description</div><div class="small">' + esc(tool.description || "") + '</div>' +
        '<div class="k">Category</div><div>' + esc(tool.category || "—") + '</div>' +
        '<div class="k">Model</div><div class="mono small">' + esc(tool.model || "—") + '</div>' +
      '</div>' +

      '<div class="panel tight" style="margin-top:12px">' +
        '<div class="spread">' +
          '<div>' +
            '<h3>Agent recommendation</h3>' +
            '<div>' + recBadge(rec) +
              ' <span class="muted small" style="margin-left:6px">confidence: ' + conf + '%</span>' +
            '</div>' +
            '<div class="small muted" style="margin-top:4px">' +
              esc(review.review_summary || "") +
            '</div>' +
          '</div>' +
          '<div>' +
            '<button class="btn ghost small" data-rerun="' + tool.id + '">Re-run pipeline</button>' +
          '</div>' +
        '</div>' +
      '</div>' +

      '<div class="review-tabs" data-tool="' + tool.id + '">' +
        '<button class="review-tab active" data-rtab="classifier">Classifier</button>' +
        '<button class="review-tab" data-rtab="security">Security</button>' +
        '<button class="review-tab" data-rtab="redteam">Red Team</button>' +
        '<button class="review-tab" data-rtab="diff">Prompt Diff</button>' +
        '<button class="review-tab" data-rtab="qa">QA Tests</button>' +
      '</div>' +
      '<div class="review-body" id="rtab-body-' + tool.id + '">' +
        renderRTab("classifier", tool) +
      '</div>' +

      '<div class="panel tight" style="margin-top:12px">' +
        '<h3>Governance Scores (editable)</h3>' +
        scoreEditorHtml(tool) +
      '</div>' +

      '<div class="panel tight" style="margin-top:12px">' +
        '<h3>Test it yourself</h3>' +
        testRunnerHtml(tool) +
      '</div>' +

      '<div class="panel tight" style="margin-top:12px">' +
        '<h3>Decision</h3>' +
        decisionHtml(tool) +
      '</div>'
    );
  }

  function wireReviewPanel(tool) {
    // Review tabs
    const tabs = document.querySelector('[data-tool="' + tool.id + '"]');
    if (tabs) {
      tabs.querySelectorAll(".review-tab").forEach(function (btn) {
        btn.addEventListener("click", function () {
          tabs.querySelectorAll(".review-tab").forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
          const body = document.getElementById("rtab-body-" + tool.id);
          body.innerHTML = renderRTab(btn.dataset.rtab, tool);
        });
      });
    }

    // Rerun
    const rerunBtn = document.querySelector('[data-rerun="' + tool.id + '"]');
    if (rerunBtn) {
      rerunBtn.addEventListener("click", async function () {
        rerunBtn.disabled = true;
        try {
          await api("POST", "/api/agent/rerun/" + tool.id);
          toast("Pipeline re-queued for " + tool.name, "success");
          await loadQueue();
          await refreshQueueBadge();
        } catch (err) { toast("Re-run failed: " + err.message, "error"); }
        finally { rerunBtn.disabled = false; }
      });
    }

    wireScoreEditor(tool);
    wireTestRunner(tool);
    wireDecision(tool);
  }

  function renderRTab(name, tool) {
    const r = tool.agent_review || {};
    if (name === "classifier") {
      return (
        '<div class="kv small">' +
          '<div class="k">Detected output type</div><div>' + esc(r.detected_output_type || "—") + '</div>' +
          '<div class="k">Detected category</div><div>' + esc(r.detected_category || "—") + '</div>' +
          '<div class="k">Confidence</div><div>' +
            (r.classification_confidence != null ? Math.round(Number(r.classification_confidence) * 100) + "%" : "—") +
          '</div>' +
        '</div>' +
        '<pre class="code" style="margin-top:10px">' +
          esc(pretty(r.classifier_output)) + '</pre>'
      );
    }
    if (name === "security") {
      const flags = Array.isArray(r.security_flags) ? r.security_flags : [];
      const flagHtml = flags.length
        ? '<ul class="small" style="padding-left:18px">' +
            flags.map(function (f) {
              return '<li><b>' + esc(f.type || "flag") + '</b> <span class="muted">[' + esc(f.severity || "low") + ']</span> — ' +
                esc(f.detail || "") +
                (f.suggestion ? '<div class="muted small">↳ ' + esc(f.suggestion) + '</div>' : "") +
              '</li>';
            }).join("") +
          '</ul>'
        : '<div class="muted small">No flags.</div>';
      return (
        '<div class="kv small">' +
          '<div class="k">Security score</div><div>' + esc(r.security_score != null ? r.security_score : "—") + '</div>' +
          '<div class="k">PII risk</div><div>' + (r.pii_risk ? "yes" : "no") + '</div>' +
          '<div class="k">Injection risk</div><div>' + (r.injection_risk ? "yes" : "no") + '</div>' +
          '<div class="k">Data exfil risk</div><div>' + (r.data_exfil_risk ? "yes" : "no") + '</div>' +
        '</div>' +
        '<div style="margin-top:10px">' + flagHtml + '</div>'
      );
    }
    if (name === "redteam") {
      const vulns = Array.isArray(r.vulnerabilities) ? r.vulnerabilities : [];
      const succeeded = r.attacks_succeeded || r.red_team_attacks_succeeded || 0;
      const attempted = r.attacks_attempted || 0;
      const vulnHtml = vulns.length
        ? '<ul class="small" style="padding-left:18px">' +
            vulns.map(function (v) {
              return '<li><b>' + esc(v.attack_type || "attack") + '</b> <span class="muted">[' + esc(v.severity || "low") + ']</span><div class="muted small">input: ' + esc(v.input_used || "") + '</div><div class="small">result: ' + esc(v.result || "") + '</div></li>';
            }).join("") +
          '</ul>'
        : '<div class="muted small">No vulnerabilities surfaced.</div>';
      return (
        '<div class="kv small">' +
          '<div class="k">Attacks attempted</div><div>' + esc(attempted) + '</div>' +
          '<div class="k">Attacks succeeded</div><div>' + esc(succeeded) + '</div>' +
        '</div>' +
        '<div style="margin-top:10px">' + vulnHtml + '</div>'
      );
    }
    if (name === "diff") {
      return renderPromptDiff(
        r.original_prompt || tool.system_prompt || "",
        r.hardened_prompt || tool.hardened_prompt || "",
        Array.isArray(r.changes_made) ? r.changes_made : []
      );
    }
    if (name === "qa") {
      const cases = Array.isArray(r.test_cases) ? r.test_cases : [];
      const rate = r.qa_pass_rate != null ? Math.round(Number(r.qa_pass_rate) * 100) + "%" : "—";
      const caseHtml = cases.length
        ? cases.map(function (c, idx) {
          return '<div class="panel tight" style="margin-top:6px">' +
            '<div class="small"><b>Test ' + (idx + 1) + '</b> — score: ' +
              esc(c.evaluation && c.evaluation.score != null ? c.evaluation.score : "—") + '</div>' +
            '<pre class="code small">Inputs: ' + esc(pretty(c.inputs)) + '</pre>' +
            '<pre class="code small">Output: ' + esc(truncate(c.output || "", 600)) + '</pre>' +
          '</div>';
        }).join("")
        : '<div class="muted small">No QA runs recorded.</div>';
      return (
        '<div class="kv small"><div class="k">Pass rate</div><div>' + rate + '</div></div>' + caseHtml
      );
    }
    return "";
  }

  function pretty(v) {
    if (v === null || v === undefined) return "—";
    if (typeof v === "string") {
      try { return JSON.stringify(JSON.parse(v), null, 2); } catch (_) { return v; }
    }
    try { return JSON.stringify(v, null, 2); } catch (_) { return String(v); }
  }

  function truncate(s, n) {
    s = String(s || "");
    if (s.length <= n) return s;
    return s.slice(0, n) + "\n…(truncated)";
  }

  // Prompt diff viewer — SPEC-required
  function renderPromptDiff(original, hardened, changes) {
    const changeCount = Array.isArray(changes) ? changes.length : 0;
    let rightHtml = esc(hardened || "(no hardened prompt)");

    // Highlight changed sections by "changed_to" or "added" strings
    if (Array.isArray(changes)) {
      changes.forEach(function (c, idx) {
        const needle = c.changed_to || c.added;
        if (!needle) return;
        const safeNeedle = esc(needle);
        const reason = esc(c.reason || "");
        const hoverAttr = ' title="' + reason.replace(/"/g, "&quot;") + '"';
        const replacement = '<span class="changed" data-change="' + idx + '"' + hoverAttr + '>' + safeNeedle + '</span>';
        // simple substring replacement in escaped content
        rightHtml = rightHtml.split(safeNeedle).join(replacement);
      });
    }

    return (
      '<div class="spread" style="margin-bottom:8px">' +
        '<div class="muted small">Side-by-side prompt comparison</div>' +
        '<span class="badge verified">' + changeCount + " change" + (changeCount === 1 ? "" : "s") + '</span>' +
      '</div>' +
      '<div class="diff">' +
        '<div class="original"><h4>Original</h4>' + esc(original || "(empty)") + '</div>' +
        '<div class="hardened"><h4>Hardened</h4>' + rightHtml + '</div>' +
      '</div>'
    );
  }

  // ---------------- Score editor ----------------

  function scoreEditorHtml(tool) {
    return (
      '<div class="score-grid">' +
        scoreInput("reliability_score", "Reliability", tool.reliability_score) +
        scoreInput("safety_score", "Safety", tool.safety_score) +
        scoreInput("complexity_score", "Complexity", tool.complexity_score) +
        scoreInput("verified_score", "Verified", tool.verified_score) +
        dsSelect(tool.data_sensitivity) +
        tierSelect(tool.trust_tier) +
      '</div>' +
      '<div style="margin-top:10px">' +
        '<label>Override reason (optional)</label>' +
        '<input type="text" data-field="override-reason-' + tool.id + '" placeholder="Why are you changing these?">' +
      '</div>' +
      '<div style="margin-top:8px;display:flex;gap:8px;justify-content:flex-end">' +
        '<button class="btn small ghost" data-save-scores="' + tool.id + '">Save overrides</button>' +
      '</div>'
    );
  }

  function scoreInput(field, label, value) {
    return (
      '<div>' +
        '<label>' + esc(label) + '</label>' +
        '<input type="number" min="0" max="100" data-score="' + field + '" value="' + esc(value != null ? value : 0) + '">' +
      '</div>'
    );
  }

  function dsSelect(current) {
    const opts = ["public", "internal", "confidential", "pii"];
    return (
      '<div>' +
        '<label>Data sensitivity</label>' +
        '<select data-score="data_sensitivity">' +
          opts.map(function (o) {
            return '<option value="' + o + '"' + (o === current ? " selected" : "") + ">" + o + "</option>";
          }).join("") +
        '</select>' +
      '</div>'
    );
  }

  function tierSelect(current) {
    const opts = ["auto", "trusted", "verified", "caution", "restricted", "unverified"];
    const val = current || "auto";
    return (
      '<div>' +
        '<label>Trust tier</label>' +
        '<select data-score="trust_tier">' +
          opts.map(function (o) {
            return '<option value="' + o + '"' + (o === val ? " selected" : "") + ">" + o + "</option>";
          }).join("") +
        '</select>' +
      '</div>'
    );
  }

  function collectScoreOverrides(toolRow) {
    const inputs = toolRow.querySelectorAll("[data-score]");
    const overrides = {};
    inputs.forEach(function (i) {
      const k = i.dataset.score;
      let v = i.value;
      if (k === "trust_tier" && v === "auto") return;
      if (["reliability_score", "safety_score", "complexity_score", "verified_score"].indexOf(k) !== -1) {
        v = Number(v);
        if (isNaN(v)) return;
      }
      overrides[k] = v;
    });
    return overrides;
  }

  function wireScoreEditor(tool) {
    const btn = document.querySelector('[data-save-scores="' + tool.id + '"]');
    if (!btn) return;
    btn.addEventListener("click", async function () {
      const row = document.getElementById("queue-row-" + tool.id);
      const overrides = collectScoreOverrides(row);
      btn.disabled = true;
      try {
        const res = await api("POST", "/api/admin/tools/" + tool.id + "/override-scores", { overrides: overrides });
        toast("Scores updated → " + (res.trust_tier || "—"), "success");
      } catch (err) {
        toast("Override failed: " + err.message, "error");
      } finally { btn.disabled = false; }
    });
  }

  // ---------------- Inline test runner ----------------

  function testRunnerHtml(tool) {
    const fields = inputSchemaFields(tool);
    if (!fields.length) {
      return '<div class="muted small">This tool has no defined inputs — nothing to test.</div>';
    }
    const form = fields.map(function (f) {
      const name = f.name || f.field_name || "field";
      const label = f.label || f.display_label || name;
      const ph = f.placeholder || "";
      const type = (f.type || "text").toLowerCase();
      if (type === "textarea") {
        return '<div><label>' + esc(label) + '</label><textarea data-tinput="' + esc(name) + '" placeholder="' + esc(ph) + '"></textarea></div>';
      }
      if (type === "select" && Array.isArray(f.options)) {
        return '<div><label>' + esc(label) + '</label><select data-tinput="' + esc(name) + '">' +
          f.options.map(function (o) {
            const val = typeof o === "string" ? o : (o.value || o.label || "");
            return '<option value="' + esc(val) + '">' + esc(val) + '</option>';
          }).join("") +
          '</select></div>';
      }
      return '<div><label>' + esc(label) + '</label><input type="' +
        (type === "number" || type === "email" ? type : "text") +
        '" data-tinput="' + esc(name) + '" placeholder="' + esc(ph) + '"></div>';
    }).join("");
    return (
      '<div class="col">' + form + '</div>' +
      '<div style="margin-top:10px;display:flex;gap:8px;justify-content:flex-end">' +
        '<button class="btn small" data-test="' + tool.id + '">Run Test</button>' +
      '</div>' +
      '<div id="test-output-' + tool.id + '"></div>'
    );
  }

  function wireTestRunner(tool) {
    const btn = document.querySelector('[data-test="' + tool.id + '"]');
    if (!btn) return;
    btn.addEventListener("click", async function () {
      const row = document.getElementById("queue-row-" + tool.id);
      const inputs = {};
      row.querySelectorAll("[data-tinput]").forEach(function (i) {
        inputs[i.dataset.tinput] = i.value;
      });
      const out = document.getElementById("test-output-" + tool.id);
      out.innerHTML = '<div class="muted small" style="margin-top:8px">Running…</div>';
      btn.disabled = true;
      try {
        const res = await fetch("/api/tools/" + tool.id + "/run", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Admin-Key": getKey() },
          body: JSON.stringify({
            input_data: inputs,
            user_name: "admin",
            user_email: "admin@forge.local",
            source: "admin_test",
          }),
        });
        const body = await res.json().catch(function () { return {}; });
        if (!res.ok) throw new Error(body.error || ("HTTP " + res.status));
        out.innerHTML =
          '<pre class="code" style="margin-top:8px">' +
          esc(truncate(body.output || body.output_data || pretty(body), 2000)) +
          '</pre>';
      } catch (err) {
        out.innerHTML = '<div class="toast error" style="margin-top:8px">' + esc(err.message) + '</div>';
      } finally { btn.disabled = false; }
    });
  }

  // ---------------- Decision ----------------

  function decisionHtml(tool) {
    return (
      '<div class="row" style="gap:20px;margin-bottom:10px">' +
        '<label><input type="radio" name="dec-' + tool.id + '" value="approve" checked> Approve</label>' +
        '<label><input type="radio" name="dec-' + tool.id + '" value="needs_changes"> Request changes</label>' +
        '<label><input type="radio" name="dec-' + tool.id + '" value="reject"> Reject</label>' +
      '</div>' +
      '<label>Notes (internal — not shown to author)</label>' +
      '<textarea data-decision-notes="' + tool.id + '" placeholder="Reviewer notes"></textarea>' +
      '<label style="margin-top:8px">Feedback for author (for changes/reject)</label>' +
      '<textarea data-decision-feedback="' + tool.id + '" placeholder="What needs to change, or why rejected"></textarea>' +
      '<div style="margin-top:10px;display:flex;gap:8px;justify-content:flex-end">' +
        '<button class="btn" data-submit-decision="' + tool.id + '">Submit Decision</button>' +
      '</div>'
    );
  }

  function wireDecision(tool) {
    const btn = document.querySelector('[data-submit-decision="' + tool.id + '"]');
    if (!btn) return;
    btn.addEventListener("click", async function () {
      const row = document.getElementById("queue-row-" + tool.id);
      const picked = row.querySelector('input[name="dec-' + tool.id + '"]:checked');
      const choice = picked ? picked.value : "approve";
      const notes = (row.querySelector('[data-decision-notes="' + tool.id + '"]') || {}).value || "";
      const feedback = (row.querySelector('[data-decision-feedback="' + tool.id + '"]') || {}).value || "";
      const overrides = collectScoreOverrides(row);

      btn.disabled = true;
      try {
        if (choice === "approve") {
          const res = await api("POST", "/api/admin/tools/" + tool.id + "/approve", {
            notes: notes,
            score_overrides: overrides,
          });
          toast(tool.name + " approved → " + (res.trust_tier || "—"), "success");
        } else if (choice === "needs_changes") {
          await api("POST", "/api/admin/tools/" + tool.id + "/needs-changes", {
            feedback: feedback, notes: notes,
          });
          toast(tool.name + ": changes requested", "success");
        } else {
          await api("POST", "/api/admin/tools/" + tool.id + "/reject", {
            feedback: feedback, notes: notes,
          });
          toast(tool.name + " rejected", "success");
        }
        const el = document.getElementById("queue-row-" + tool.id);
        if (el) el.remove();
        QUEUE_CACHE = QUEUE_CACHE.filter(function (t) { return t.id !== tool.id; });
        refreshQueueBadge();
      } catch (err) {
        toast("Decision failed: " + err.message, "error");
      } finally { btn.disabled = false; }
    });
  }

  // ---------------- Live Tools tab ----------------

  async function loadLiveTools() {
    const root = document.getElementById("live-root");
    root.innerHTML = '<div class="muted">Loading live tools…</div>';
    try {
      const res = await fetch("/api/tools?status=approved&limit=200", {
        headers: { "X-Admin-Key": getKey() },
      });
      const data = await res.json();
      const tools = (data && (data.tools || data.items || data)) || [];
      renderLiveTools(Array.isArray(tools) ? tools : []);
    } catch (err) {
      root.innerHTML = '<div class="panel">Failed to load live tools: ' + esc(err.message) + "</div>";
    }
  }

  function renderLiveTools(tools) {
    const root = document.getElementById("live-root");
    if (!tools.length) {
      root.innerHTML = '<div class="panel">No approved tools yet.</div>';
      return;
    }
    const rows = tools.map(function (t) {
      const flags = Number(t.flag_count || 0);
      const flagCls = flags === 0 ? "ok" : (flags < 3 ? "warn" : "fail");
      const flagHtml = '<span class="' + flagCls + '">' + flags + "</span>";
      return (
        '<tr>' +
          '<td><div style="font-weight:600">' + esc(t.name) + '</div><div class="muted small">' + esc(t.tagline || "") + '</div></td>' +
          '<td>' + trustBadge(t.trust_tier) + '</td>' +
          '<td>' + esc(t.run_count || 0) + '</td>' +
          '<td>' + esc(Number(t.avg_rating || 0).toFixed(2)) + '</td>' +
          '<td>' + flagHtml + '</td>' +
          '<td>' + fmtRel(t.last_run_at) + '</td>' +
          '<td>' +
            '<button class="btn small ghost" data-archive="' + t.id + '">Archive</button>' +
          '</td>' +
        '</tr>'
      );
    }).join("");
    root.innerHTML =
      '<div class="panel">' +
        '<h2>' + tools.length + " live tools</h2>" +
        '<table><thead><tr>' +
          '<th>Name</th><th>Trust</th><th>Runs</th><th>Rating</th><th>Flags</th><th>Last run</th><th></th>' +
        '</tr></thead><tbody>' + rows + '</tbody></table>' +
      '</div>';

    document.querySelectorAll("[data-archive]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        const id = btn.dataset.archive;
        if (!confirm("Archive this tool?")) return;
        btn.disabled = true;
        try {
          await api("POST", "/api/admin/tools/" + id + "/archive");
          toast("Archived", "success");
          loadLiveTools();
        } catch (err) { toast(err.message, "error"); btn.disabled = false; }
      });
    });
  }

  // ---------------- Run Monitor tab ----------------

  let RUNS_REFRESH_TIMER = null;
  let RUNS_CACHE = [];

  async function loadRunMonitor() {
    if (RUNS_REFRESH_TIMER) { clearInterval(RUNS_REFRESH_TIMER); RUNS_REFRESH_TIMER = null; }
    await fetchAndRenderRuns();
    RUNS_REFRESH_TIMER = setInterval(fetchAndRenderRuns, 30000);
  }

  function currentRunFilters() {
    const root = document.getElementById("runs-root");
    if (!root) return {};
    const tool = root.querySelector("[data-filter='tool_id']");
    const user = root.querySelector("[data-filter='user_email']");
    const flagged = root.querySelector("[data-filter='flagged']");
    const out = {};
    if (tool && tool.value) out.tool_id = tool.value;
    if (user && user.value) out.user_email = user.value;
    if (flagged && flagged.value && flagged.value !== "all") out.flagged = flagged.value;
    return out;
  }

  async function fetchAndRenderRuns() {
    const root = document.getElementById("runs-root");
    const qs = new URLSearchParams(currentRunFilters()).toString();
    try {
      const data = await api("GET", "/api/admin/runs" + (qs ? "?" + qs : ""));
      RUNS_CACHE = (data && data.runs) || [];
      renderRuns(RUNS_CACHE);
    } catch (err) {
      root.innerHTML = '<div class="panel">Failed to load runs: ' + esc(err.message) + "</div>";
    }
  }

  function renderRuns(runs) {
    const filters = currentRunFilters();
    const head =
      '<div class="panel tight">' +
        '<div class="row" style="gap:10px;flex-wrap:wrap">' +
          '<div style="flex:1;min-width:140px"><label>Tool ID</label>' +
            '<input data-filter="tool_id" type="text" placeholder="all" value="' + esc(filters.tool_id || "") + '"></div>' +
          '<div style="flex:1;min-width:160px"><label>User email</label>' +
            '<input data-filter="user_email" type="text" placeholder="all" value="' + esc(filters.user_email || "") + '"></div>' +
          '<div style="min-width:120px"><label>Flagged</label>' +
            '<select data-filter="flagged">' +
              '<option value="all">all</option>' +
              '<option value="true"' + (filters.flagged === "true" ? " selected" : "") + '>flagged</option>' +
              '<option value="false"' + (filters.flagged === "false" ? " selected" : "") + '>not flagged</option>' +
            '</select></div>' +
          '<div><label>&nbsp;</label><button class="btn small" id="runs-apply">Apply</button></div>' +
        '</div>' +
      '</div>';

    const rows = runs.map(runRowHtml).join("");
    const body =
      '<div class="panel"><div class="spread"><h2>' + runs.length + " recent runs</h2>" +
        '<div class="muted small">auto-refresh 30s</div></div>' +
        '<table><thead><tr>' +
          '<th>Time</th><th>Tool</th><th>User</th><th>Duration</th><th>Cost</th><th>Rating</th><th>Flag</th>' +
        '</tr></thead><tbody>' + rows + '</tbody></table>' +
      '</div>';
    document.getElementById("runs-root").innerHTML = head + body;

    const apply = document.getElementById("runs-apply");
    if (apply) apply.addEventListener("click", fetchAndRenderRuns);

    document.querySelectorAll("[data-run-id]").forEach(function (tr) {
      tr.addEventListener("click", function (e) {
        if (e.target.closest("[data-flag-run]")) return;
        openRunModal(tr.dataset.runId);
      });
    });
    document.querySelectorAll("[data-flag-run]").forEach(function (btn) {
      btn.addEventListener("click", async function (e) {
        e.stopPropagation();
        const id = btn.dataset.flagRun;
        const reason = prompt("Flag reason (optional):") || "admin_flag";
        try {
          await api("POST", "/api/admin/runs/" + id + "/flag", { reason: reason });
          toast("Run flagged", "success");
          fetchAndRenderRuns();
        } catch (err) { toast(err.message, "error"); }
      });
    });
  }

  function runRowHtml(r) {
    const dur = Number(r.run_duration_ms || 0);
    let durCls = "";
    if (dur > 0 && dur < 2000) durCls = "green";
    else if (dur < 5000) durCls = "yellow";
    else durCls = "red";
    const stars = r.rating != null ? "★".repeat(Number(r.rating)) + "☆".repeat(5 - Number(r.rating)) : '<span class="muted">—</span>';
    const flagBtn = r.output_flagged
      ? '<span class="badge caution">flagged</span>'
      : '<button class="btn small ghost" data-flag-run="' + r.id + '">Flag</button>';
    const dlp = Number(r.dlp_tokens_found || 0);
    const dlpBadge = dlp > 0
      ? ' <span class="badge restricted" title="DLP masked ' + dlp + ' PII token' + (dlp === 1 ? '' : 's') + '">🛡 DLP ' + dlp + '</span>'
      : '';
    return (
      '<tr class="clickable" data-run-id="' + r.id + '">' +
        '<td>' + fmtRel(r.created_at) + '</td>' +
        '<td>' + esc(r.tool_name || ("tool " + r.tool_id)) + dlpBadge + '</td>' +
        '<td>' + esc(r.user_email || r.user_name || "anon") + '</td>' +
        '<td><span class="dur-badge ' + durCls + '">' + (dur ? dur + "ms" : "—") + '</span></td>' +
        '<td>' + (r.cost_usd != null ? "$" + Number(r.cost_usd).toFixed(4) : "—") + '</td>' +
        '<td>' + stars + '</td>' +
        '<td>' + flagBtn + '</td>' +
      '</tr>'
    );
  }

  async function openRunModal(runId) {
    const idNum = Number(runId);
    let run = RUNS_CACHE.find(function (r) { return Number(r.id) === idNum; });
    if (!run) {
      try {
        const res = await fetch("/api/runs/" + runId, { headers: { "X-Admin-Key": getKey() } });
        if (res.ok) run = await res.json();
      } catch (_) { /* ignore */ }
    }
    if (!run) { toast("Run not found", "error"); return; }

    const inputs = typeof run.input_data === "string" ? safeJson(run.input_data) : run.input_data;
    openModal(
      '<h2>Run #' + esc(run.id) + '</h2>' +
      '<div class="kv small">' +
        '<div class="k">Tool</div><div>' + esc(run.tool_name || run.tool_id) + '</div>' +
        '<div class="k">User</div><div>' + esc(run.user_email || run.user_name || "anon") + '</div>' +
        '<div class="k">Created</div><div>' + fmtDate(run.created_at) + '</div>' +
        '<div class="k">Duration</div><div>' + esc(run.run_duration_ms || 0) + 'ms</div>' +
        '<div class="k">Tokens</div><div>' + esc(run.tokens_used || "—") + '</div>' +
        '<div class="k">Cost</div><div>' + (run.cost_usd != null ? "$" + Number(run.cost_usd).toFixed(4) : "—") + '</div>' +
      '</div>' +
      '<h3 style="margin-top:14px">Input</h3>' +
      '<pre class="code">' + esc(pretty(inputs)) + '</pre>' +
      '<h3 style="margin-top:10px">Rendered prompt</h3>' +
      '<pre class="code">' + esc(truncate(run.rendered_prompt || "—", 2000)) + '</pre>' +
      '<h3 style="margin-top:10px">Output</h3>' +
      '<pre class="code">' + esc(truncate(run.output_data || run.output_parsed || "—", 3000)) + '</pre>'
    );
  }

  function safeJson(s) {
    try { return JSON.parse(s); } catch (_) { return s; }
  }

  // ---------------- Analytics tab ----------------

  const CHARTS = {};

  function destroyCharts() {
    Object.keys(CHARTS).forEach(function (k) {
      try { CHARTS[k].destroy(); } catch (_) {}
      delete CHARTS[k];
    });
  }

  async function loadAnalytics() {
    const root = document.getElementById("analytics-root");
    root.innerHTML = '<div class="muted">Loading analytics…</div>';
    try {
      const a = await api("GET", "/api/admin/analytics");
      destroyCharts();
      root.innerHTML =
        '<div class="metric-grid">' +
          metricCard("Live tools", a.total_tools || 0) +
          metricCard("Runs (30d)", a.total_runs_month || 0) +
          metricCard("Avg rating", (a.avg_rating != null ? Number(a.avg_rating).toFixed(2) : "—")) +
          metricCard("Pending review", a.pending_count || 0) +
        '</div>' +
        '<div class="chart-grid">' +
          '<div class="panel"><h3>Runs per day — last 30d</h3><canvas id="chart-runs"></canvas></div>' +
          '<div class="panel"><h3>Trust tier distribution</h3><canvas id="chart-trust"></canvas></div>' +
        '</div>' +
        '<div class="chart-grid">' +
          '<div class="panel"><h3>Top tools (by runs)</h3><canvas id="chart-top"></canvas></div>' +
          '<div class="panel"><h3>Category distribution</h3><canvas id="chart-cat"></canvas></div>' +
        '</div>' +
        '<div class="panel tight"><h3>Agent pipeline pass rate</h3>' +
          '<div style="font-size:22px;font-weight:700">' + ((Number(a.agent_pass_rate || 0) * 100).toFixed(1)) + '%</div>' +
          '<div class="muted small">approvals vs (approvals + rejections)</div>' +
        '</div>';

      renderAnalyticsCharts(a);
    } catch (err) {
      root.innerHTML = '<div class="panel">Failed to load analytics: ' + esc(err.message) + "</div>";
    }
  }

  function metricCard(label, value) {
    return '<div class="metric-card"><div class="label">' + esc(label) + '</div><div class="value">' + esc(value) + '</div></div>';
  }

  function renderAnalyticsCharts(a) {
    if (typeof Chart === "undefined") return;

    const runs = Array.isArray(a.runs_per_day) ? a.runs_per_day : [];
    const rLabels = runs.map(function (r) { return r.date; });
    const rData = runs.map(function (r) { return r.count; });
    CHARTS.runs = new Chart(document.getElementById("chart-runs"), {
      type: "line",
      data: {
        labels: rLabels,
        datasets: [{
          label: "runs",
          data: rData,
          borderColor: "#0066ff",
          backgroundColor: "rgba(0,102,255,0.15)",
          fill: true, tension: 0.3,
        }],
      },
      options: chartOpts(),
    });

    const tiers = a.tools_by_trust_tier || {};
    CHARTS.trust = new Chart(document.getElementById("chart-trust"), {
      type: "doughnut",
      data: {
        labels: Object.keys(tiers),
        datasets: [{
          data: Object.values(tiers),
          backgroundColor: ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#6b7280"],
        }],
      },
      options: chartOpts(),
    });

    const top = Array.isArray(a.top_tools) ? a.top_tools : [];
    CHARTS.top = new Chart(document.getElementById("chart-top"), {
      type: "bar",
      data: {
        labels: top.map(function (t) { return t.name; }),
        datasets: [{
          label: "runs", data: top.map(function (t) { return t.runs; }),
          backgroundColor: "#3b82f6",
        }],
      },
      options: Object.assign(chartOpts(), { indexAxis: "y" }),
    });

    const cats = a.category_distribution || {};
    CHARTS.cat = new Chart(document.getElementById("chart-cat"), {
      type: "doughnut",
      data: {
        labels: Object.keys(cats),
        datasets: [{
          data: Object.values(cats),
          backgroundColor: ["#0066ff", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#a855f7", "#38bdf8", "#84cc16"],
        }],
      },
      options: chartOpts(),
    });
  }

  function chartOpts() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#e7e9ee" } },
      },
      scales: {
        x: { ticks: { color: "#9aa3b2" }, grid: { color: "#222735" } },
        y: { ticks: { color: "#9aa3b2" }, grid: { color: "#222735" }, beginAtZero: true },
      },
    };
  }

  // ---------------- Settings tab ----------------

  function getSettings() {
    try {
      const raw = localStorage.getItem(SETTINGS_STORAGE);
      return raw ? JSON.parse(raw) : {};
    } catch (_) { return {}; }
  }
  function saveSettings(s) {
    try { localStorage.setItem(SETTINGS_STORAGE, JSON.stringify(s)); } catch (_) {}
  }

  function loadSettings() {
    const s = getSettings();
    const root = document.getElementById("settings-root");
    root.innerHTML =
      '<div class="panel">' +
        '<h2>Platform settings</h2>' +
        '<div class="muted small" style="margin-bottom:10px">Stored locally for now. Phase 2: persist to server.</div>' +
        '<label>Slack webhook URL (#forge-releases)</label>' +
        '<div class="row"><input id="set-slack" type="text" value="' + esc(s.slack_webhook || "") + '" placeholder="https://hooks.slack.com/…">' +
          '<button class="btn small ghost" id="set-slack-test">Test</button>' +
        '</div>' +
        '<div style="margin-top:10px">' +
          '<label>Default model for new tools</label>' +
          '<select id="set-model">' +
            ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-6'].map(function (m) {
              return '<option value="' + m + '"' + (m === (s.default_model || 'claude-haiku-4-5-20251001') ? ' selected' : '') + '>' + m + '</option>';
            }).join('') +
          '</select>' +
        '</div>' +
        '<div style="margin-top:10px">' +
          '<label>Admin key</label>' +
          '<div class="row"><input id="set-key" type="password" value="' + esc(getKey()) + '"><button class="btn small ghost" id="set-key-rotate">Rotate</button></div>' +
          '<div class="muted small">Rotate by generating a new key, saving in your .env, and pasting here.</div>' +
        '</div>' +
        '<div style="margin-top:10px">' +
          '<label><input type="checkbox" id="set-maint"' + (s.maintenance ? ' checked' : '') + '> Maintenance mode</label>' +
        '</div>' +
        '<div style="margin-top:14px;display:flex;gap:8px;justify-content:flex-end">' +
          '<button class="btn" id="set-save">Save settings</button>' +
        '</div>' +
      '</div>';

    document.getElementById("set-slack-test").addEventListener("click", function () {
      const url = (document.getElementById("set-slack").value || "").trim();
      if (!url) { toast("Enter a webhook URL first", "error"); return; }
      toast("Test would POST to " + url.slice(0, 40) + "…", "success");
    });
    document.getElementById("set-key-rotate").addEventListener("click", function () {
      const next = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now());
      document.getElementById("set-key").value = "forge-admin-" + next.slice(0, 12);
      toast("Key generated — paste into .env ADMIN_KEY and save", "success");
    });
    document.getElementById("set-save").addEventListener("click", function () {
      const next = {
        slack_webhook: document.getElementById("set-slack").value,
        default_model: document.getElementById("set-model").value,
        maintenance: document.getElementById("set-maint").checked,
      };
      saveSettings(next);
      const newKey = document.getElementById("set-key").value;
      if (newKey && newKey !== getKey()) setKey(newKey);
      toast("Settings saved", "success");
    });
  }

  // ---------------- Boot ----------------

  function boot() {
    document.getElementById("key-save").addEventListener("click", function () {
      const v = document.getElementById("key-input").value.trim();
      if (!v) { toast("Enter a key", "error"); return; }
      setKey(v);
      showAdmin();
      refreshQueueBadge();
      setActiveTab("queue");
    });
    document.getElementById("key-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter") document.getElementById("key-save").click();
    });
    document.getElementById("logout-btn").addEventListener("click", function () {
      clearKey();
      showKeySetup();
    });

    if (!getKey()) {
      showKeySetup();
      return;
    }
    showAdmin();
    refreshQueueBadge();
    setActiveTab("queue");
    setInterval(refreshQueueBadge, 60000);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
