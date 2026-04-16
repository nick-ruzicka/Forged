/* Forge GTM Analytics dashboard.
   Consumes /api/admin/analytics + /api/analytics/*.
   Admin key: read from localStorage; prompt once if missing. */

(function () {
  const LS_KEY = 'forge_admin_key';
  const EMPTY_HINT = 'Run scripts/run_eval.py to populate';

  const PALETTE = {
    accent:      '#0066FF',
    accentSoft:  'rgba(0,102,255,0.22)',
    accentFaint: 'rgba(0,102,255,0.02)',
    muted:       '#888',
    grid:        'rgba(255,255,255,0.04)',
    tick:        '#888',
    tickStrong:  '#bbb',
    trusted:     '#1a7f4b',
    verified:    '#1a4fa0',
    caution:     '#b8860b',
    restricted:  '#c45c00',
    unverified:  '#555',
    danger:      '#c0392b',
  };
  const CATEGORY_PALETTE = [
    '#0066FF', '#1a7f4b', '#b8860b', '#c45c00', '#1a4fa0',
    '#7a4fa0', '#c0392b', '#2aa198', '#d33682', '#859900',
  ];

  // Tracks Chart.js instances per canvas so refresh doesn't stack them.
  const charts = new Map();

  // -------------------- Admin key --------------------

  function getAdminKey() {
    let key = null;
    try { key = localStorage.getItem(LS_KEY); } catch (_) {}
    if (key) return key;
    key = window.prompt('Enter Forge admin key (X-Admin-Key):') || '';
    key = key.trim();
    if (!key) return '';
    try { localStorage.setItem(LS_KEY, key); } catch (_) {}
    return key;
  }

  function authHeaders() { return { 'X-Admin-Key': getAdminKey() }; }

  async function fetchJSON(url) {
    const res = await fetch(url, { headers: authHeaders() });
    if (res.status === 401) {
      try { localStorage.removeItem(LS_KEY); } catch (_) {}
      throw new Error('unauthorized');
    }
    if (!res.ok) throw new Error('HTTP ' + res.status + ' for ' + url);
    return res.json();
  }

  // -------------------- Helpers --------------------

  function $(id) { return document.getElementById(id); }

  function fmtNumber(n) {
    if (n === null || n === undefined) return '—';
    const v = Number(n);
    if (!isFinite(v)) return '—';
    if (Math.abs(v) >= 1000) return v.toLocaleString();
    return String(v);
  }

  function fmtUsd(n) {
    const v = Number(n || 0);
    if (v === 0) return '$0';
    if (v < 1) return '$' + v.toFixed(3);
    return '$' + v.toFixed(2);
  }

  function fmtMs(ms) {
    const v = Number(ms || 0);
    if (v >= 1000) return (v / 1000).toFixed(1) + 's';
    return Math.round(v) + 'ms';
  }

  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  function initials(name, email) {
    const src = (name || email || '').trim();
    if (!src) return '·';
    const parts = src.split(/[\s@._-]+/).filter(Boolean);
    const a = parts[0]?.[0] || '';
    const b = parts[1]?.[0] || '';
    return (a + b).toUpperCase() || '·';
  }

  function markReady(bodyId) {
    const el = $(bodyId);
    if (el) el.classList.add('ready');
  }

  function markEmpty(bodyId, msg) {
    const el = $(bodyId);
    if (!el) return;
    const sk = el.querySelector('.card-skeleton');
    if (sk) sk.remove();
    // Clear any previous chart content except the empty-note.
    Array.from(el.children).forEach((c) => {
      if (c.classList && c.classList.contains('empty-note')) return;
      if (c.tagName === 'CANVAS') c.style.display = 'none';
      if (c.id && ['funnel-body', 'quality-body', 'builders-body'].includes(c.id)) {
        c.innerHTML = '';
      }
    });
    let note = el.querySelector('.empty-note');
    if (!note) {
      note = document.createElement('div');
      note.className = 'empty-note';
      el.appendChild(note);
    }
    note.textContent = msg || EMPTY_HINT;
    el.classList.add('ready');
  }

  function destroyChart(canvasId) {
    const old = charts.get(canvasId);
    if (old) { try { old.destroy(); } catch (_) {} charts.delete(canvasId); }
  }

  function clearContainer(id) {
    const el = $(id);
    if (!el) return;
    el.innerHTML = '';
  }

  function resetCards() {
    ['body-adoption','body-cost','body-funnel','body-quality','body-latency',
     'body-risk','body-top-tools','body-builders'].forEach((id) => {
      const el = $(id);
      if (!el) return;
      el.classList.remove('ready');
      // Restore skeleton if missing.
      if (!el.querySelector('.card-skeleton')) {
        const sk = document.createElement('div');
        sk.className = 'card-skeleton';
        el.insertBefore(sk, el.firstChild);
      }
      const note = el.querySelector('.empty-note');
      if (note) note.remove();
    });
    ['chart-adoption','chart-cost','chart-latency','chart-risk','chart-top-tools']
      .forEach(destroyChart);
    ['funnel-body','quality-body','builders-body'].forEach(clearContainer);
  }

  // -------------------- Chart.js shared styling --------------------

  Chart.defaults.font.family = "'DM Sans', system-ui, sans-serif";
  Chart.defaults.color = PALETTE.tick;
  Chart.defaults.animation.duration = 500;
  Chart.defaults.animation.easing = 'easeOutCubic';

  const tooltipStyle = {
    enabled: true,
    backgroundColor: 'rgba(20,20,22,0.96)',
    titleColor: '#e8e8e8',
    titleFont: { family: "'DM Mono'", size: 10, weight: 500 },
    titleMarginBottom: 6,
    bodyColor: '#f0f0f0',
    bodyFont: { family: "'DM Sans'", size: 12, weight: 600 },
    borderColor: 'transparent',
    borderWidth: 0,
    padding: { top: 8, bottom: 8, left: 10, right: 10 },
    cornerRadius: 8,
    displayColors: false,
    boxPadding: 4,
    usePointStyle: true,
  };

  function baseScales(opts) {
    const gridX = { display: false, drawBorder: false };
    const gridY = { color: PALETTE.grid, drawBorder: false, drawTicks: false };
    return {
      x: {
        ticks: {
          color: PALETTE.tick,
          font: { family: "'DM Mono'", size: 10 },
          padding: 6, maxRotation: 0, autoSkip: true,
        },
        grid: gridX,
        border: { display: false },
        ...(opts && opts.x),
      },
      y: {
        ticks: {
          color: PALETTE.tick,
          font: { family: "'DM Mono'", size: 10 },
          padding: 8,
        },
        grid: gridY,
        border: { display: false },
        beginAtZero: true,
        ...(opts && opts.y),
      },
    };
  }

  function makeGradient(ctx, area, colorTop, colorBottom) {
    const g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
    g.addColorStop(0, colorTop);
    g.addColorStop(1, colorBottom);
    return g;
  }

  // -------------------- KPIs + sparkline --------------------

  function renderSparkline(series) {
    const el = $('kpi-runs-spark');
    if (!el) return;
    el.innerHTML = '';
    const vals = (series || []).map((r) => Number(r.count || 0));
    if (vals.length < 2) return;
    const w = 120, h = 28, pad = 2;
    const max = Math.max(1, ...vals);
    const n = vals.length;
    const step = (w - pad * 2) / (n - 1);
    const pts = vals.map((v, i) => [
      pad + i * step,
      h - pad - (v / max) * (h - pad * 2),
    ]);
    const d = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(2) + ' ' + p[1].toFixed(2)).join(' ');
    const dFill = d + ' L ' + pts[pts.length - 1][0].toFixed(2) + ' ' + (h - pad) + ' L ' + pts[0][0].toFixed(2) + ' ' + (h - pad) + ' Z';
    const NS = 'http://www.w3.org/2000/svg';
    const defs = document.createElementNS(NS, 'defs');
    const lg = document.createElementNS(NS, 'linearGradient');
    const gid = 'sparkg';
    lg.setAttribute('id', gid);
    lg.setAttribute('x1', '0'); lg.setAttribute('y1', '0');
    lg.setAttribute('x2', '0'); lg.setAttribute('y2', '1');
    const stopTop = document.createElementNS(NS, 'stop');
    stopTop.setAttribute('offset', '0%');
    stopTop.setAttribute('stop-color', PALETTE.accent);
    stopTop.setAttribute('stop-opacity', '0.35');
    lg.appendChild(stopTop);
    const stopBot = document.createElementNS(NS, 'stop');
    stopBot.setAttribute('offset', '100%');
    stopBot.setAttribute('stop-color', PALETTE.accent);
    stopBot.setAttribute('stop-opacity', '0');
    lg.appendChild(stopBot);
    defs.appendChild(lg);
    el.appendChild(defs);

    const fill = document.createElementNS(NS, 'path');
    fill.setAttribute('d', dFill);
    fill.setAttribute('fill', 'url(#' + gid + ')');
    el.appendChild(fill);

    const line = document.createElementNS(NS, 'path');
    line.setAttribute('d', d);
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', PALETTE.accent);
    line.setAttribute('stroke-width', '1.5');
    line.setAttribute('stroke-linecap', 'round');
    line.setAttribute('stroke-linejoin', 'round');
    el.appendChild(line);

    const last = pts[pts.length - 1];
    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('cx', last[0]);
    dot.setAttribute('cy', last[1]);
    dot.setAttribute('r', '2.2');
    dot.setAttribute('fill', PALETTE.accent);
    el.appendChild(dot);
  }

  function renderKPIs(admin) {
    $('kpi-total-tools').textContent = fmtNumber(admin.total_tools);
    $('kpi-runs-month').textContent  = fmtNumber(admin.total_runs_month);
    $('kpi-avg-rating').textContent  = (Number(admin.avg_rating || 0)).toFixed(2);
    const pass = Number(admin.agent_pass_rate || 0);
    $('kpi-pass-rate').textContent   = (pass * 100).toFixed(1) + '%';
    $('kpi-pending').textContent     = fmtNumber(admin.pending_count);

    // Runs delta: split the 30d series in half and compare sums.
    const series = admin.runs_per_day || [];
    const delta = $('kpi-runs-delta');
    if (delta) {
      delta.className = 'kpi-delta';
      delta.textContent = '';
      if (series.length >= 4) {
        const mid = Math.floor(series.length / 2);
        const prev = series.slice(0, mid).reduce((a, r) => a + Number(r.count || 0), 0);
        const curr = series.slice(mid).reduce((a, r) => a + Number(r.count || 0), 0);
        if (prev > 0 || curr > 0) {
          const pct = prev === 0 ? 100 : ((curr - prev) / prev) * 100;
          const sign = pct > 0.5 ? 'up' : pct < -0.5 ? 'down' : 'flat';
          const arrow = sign === 'up' ? '↑' : sign === 'down' ? '↓' : '→';
          delta.classList.add(sign);
          delta.textContent = arrow + ' ' + Math.abs(pct).toFixed(0) + '%';
          delta.title = 'Last ' + (series.length - mid) + 'd vs prior ' + mid + 'd';
        }
      }
    }

    renderSparkline(series);
  }

  // -------------------- Adoption (line with gradient fill) --------------------

  function renderAdoption(runs_per_day) {
    const rows = runs_per_day || [];
    if (!rows.length) { markEmpty('body-adoption', 'no runs in last 30 days'); return; }
    const labels = rows.map((r) => r.date);
    const data   = rows.map((r) => Number(r.count || 0));

    destroyChart('chart-adoption');
    const canvas = $('chart-adoption');
    canvas.style.display = '';
    // Single-point fallback: draw a bar so the card isn't visually empty.
    if (rows.length === 1) {
      const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: 'runs', data,
            backgroundColor: PALETTE.accent,
            borderWidth: 0, borderRadius: 4, maxBarThickness: 48,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { ...tooltipStyle, callbacks: { label: (ctx) => fmtNumber(ctx.parsed.y) + ' runs' } },
          },
          scales: baseScales({
            y: { ticks: { maxTicksLimit: 4, callback: (v) => fmtNumber(v) } },
          }),
        },
      });
      charts.set('chart-adoption', chart);
      markReady('body-adoption');
      return;
    }
    const chart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'runs',
          data,
          borderColor: PALETTE.accent,
          borderWidth: 1.75,
          backgroundColor: (ctx) => {
            const { chart } = ctx;
            const { ctx: c, chartArea } = chart;
            if (!chartArea) return PALETTE.accentSoft;
            return makeGradient(c, chartArea, PALETTE.accentSoft, PALETTE.accentFaint);
          },
          fill: true,
          tension: 0.35,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: PALETTE.accent,
          pointHoverBorderColor: '#0d0d0d',
          pointHoverBorderWidth: 2,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltipStyle,
            callbacks: {
              title: (items) => items[0]?.label || '',
              label: (ctx) => fmtNumber(ctx.parsed.y) + ' runs',
            },
          },
        },
        scales: baseScales({
          x: { ticks: { maxTicksLimit: 6 } },
          y: { ticks: { maxTicksLimit: 4, callback: (v) => fmtNumber(v) } },
        }),
      },
    });
    charts.set('chart-adoption', chart);
    markReady('body-adoption');
  }

  // -------------------- Cost breakdown (stacked bar) --------------------

  function renderCost(payload) {
    const entries = (payload && payload.entries) || [];
    const categories = (payload && payload.categories) || [];
    if (!entries.length) { markEmpty('body-cost', 'no runs with cost in last 90 days'); return; }

    const weeks = Array.from(new Set(entries.map((e) => e.week))).sort();
    const byKey = new Map();
    for (const e of entries) byKey.set(e.week + '|' + e.category, e.cost_usd);

    const datasets = categories.map((cat, i) => ({
      label: cat,
      data: weeks.map((w) => byKey.get(w + '|' + cat) || 0),
      backgroundColor: CATEGORY_PALETTE[i % CATEGORY_PALETTE.length],
      borderWidth: 0,
      borderRadius: i === categories.length - 1 ? { topLeft: 4, topRight: 4 } : 0,
      stack: 'cost',
      maxBarThickness: 18,
    }));

    destroyChart('chart-cost');
    const canvas = $('chart-cost');
    canvas.style.display = '';
    const chart = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: { labels: weeks, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: {
            position: 'bottom', align: 'start',
            labels: {
              color: PALETTE.tick, font: { family: "'DM Sans'", size: 10 },
              boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: 'circle', padding: 10,
            },
          },
          tooltip: {
            ...tooltipStyle,
            callbacks: {
              title: (items) => 'Week of ' + (items[0]?.label || ''),
              label: (ctx) => ctx.dataset.label + ': ' + fmtUsd(ctx.parsed.y),
            },
          },
        },
        scales: {
          x: {
            stacked: true,
            ticks: { color: PALETTE.tick, font: { family: "'DM Mono'", size: 9 }, maxTicksLimit: 8 },
            grid: { display: false },
            border: { display: false },
          },
          y: {
            stacked: true,
            ticks: {
              color: PALETTE.tick, font: { family: "'DM Mono'", size: 10 },
              maxTicksLimit: 4, callback: (v) => '$' + v,
            },
            grid: { color: PALETTE.grid, drawTicks: false },
            border: { display: false },
            beginAtZero: true,
          },
        },
      },
    });
    charts.set('chart-cost', chart);
    markReady('body-cost');
  }

  // -------------------- Lifecycle funnel (horizontal bands w/ retention) --------------------

  function renderFunnel(f) {
    const STAGES = [
      ['submitted',  'Submitted'],
      ['reviewed',   'Reviewed'],
      ['approved',   'Approved'],
      ['run_once',   'Run ≥1×'],
      ['run_10x',    'Run ≥10×'],
      ['active_30d', 'Active 30d'],
    ];
    const host = $('funnel-body');
    host.innerHTML = '';
    const values = STAGES.map(([k]) => Number(f[k] || 0));
    const max = Math.max(1, ...values);

    const stages = document.createElement('div');
    stages.className = 'funnel-stages';
    host.appendChild(stages);

    STAGES.forEach(([, label], i) => {
      const v = values[i];
      const pct = Math.max(3, Math.round((v / max) * 100));
      const stage = document.createElement('div');
      stage.className = 'funnel-stage';
      stage.innerHTML =
        '<div class="bg" style="width:' + pct + '%"></div>' +
        '<div class="label">' + escapeHtml(label) + '</div>' +
        '<div class="count">' + fmtNumber(v) + '</div>';
      stages.appendChild(stage);

      if (i < STAGES.length - 1) {
        const nextV = values[i + 1];
        const drop = document.createElement('div');
        drop.className = 'funnel-drop';
        if (v > 0) {
          const deltaPct = ((nextV - v) / v) * 100;
          if (deltaPct >= 0) drop.classList.add('positive');
          const arrow = deltaPct >= 0 ? '↑' : '↓';
          drop.textContent = arrow + ' ' + Math.abs(deltaPct).toFixed(0) + '%  ·  ' + fmtNumber(Math.abs(nextV - v)) + ' lost';
          if (deltaPct >= 0) drop.textContent = arrow + ' ' + deltaPct.toFixed(0) + '%  ·  ' + fmtNumber(nextV - v) + ' gained';
        } else {
          drop.textContent = '·';
        }
        stages.appendChild(drop);
      }
    });
    markReady('body-funnel');
  }

  // -------------------- Pipeline quality (2×2 heatmap) --------------------

  function renderQuality(q) {
    const host = $('quality-body');
    host.innerHTML = '';
    if (!q || q.empty) { markEmpty('body-quality', EMPTY_HINT); return; }

    const c = q.confusion || {};
    const cells = [
      ['tp', 'True positive', c.tp, 'correct'],
      ['fp', 'False positive', c.fp, 'error'],
      ['fn', 'False negative', c.fn, 'error'],
      ['tn', 'True negative', c.tn, 'correct'],
    ];
    const max = Math.max(1, ...cells.map((x) => x[2] || 0));

    const grid = document.createElement('div');
    grid.className = 'qm-grid';
    grid.innerHTML =
      '<div class="qm-cell qm-header"></div>' +
      '<div class="qm-cell qm-header">Pred reject</div>' +
      '<div class="qm-cell qm-header">Pred pass</div>' +
      '<div class="qm-cell qm-row-label">Actual reject</div>' +
      qmCell(cells[0]) + qmCell(cells[2]) +
      '<div class="qm-cell qm-row-label">Actual pass</div>' +
      qmCell(cells[1]) + qmCell(cells[3]);
    host.appendChild(grid);

    // Apply opacity by count after render.
    grid.querySelectorAll('.qm-data').forEach((el) => {
      const n = Number(el.dataset.count || 0);
      const fill = el.querySelector('.fill');
      if (fill) fill.style.opacity = (0.08 + 0.32 * (n / max)).toFixed(3);
    });

    const scores = document.createElement('div');
    scores.className = 'qm-scores';
    scores.innerHTML =
      '<div class="qm-score"><span class="lbl">Precision</span><span class="val">' + (Number(q.precision) * 100).toFixed(1) + '%</span></div>' +
      '<div class="qm-score"><span class="lbl">Recall</span><span class="val">' + (Number(q.recall) * 100).toFixed(1) + '%</span></div>';
    host.appendChild(scores);
    markReady('body-quality');

    function qmCell(cell) {
      const [, label, val, kind] = cell;
      return (
        '<div class="qm-cell qm-data ' + kind + '" data-count="' + (val || 0) + '">' +
          '<div class="fill"></div>' +
          '<div class="v">' + fmtNumber(val) + '</div>' +
          '<div class="t">' + escapeHtml(label) + '</div>' +
        '</div>'
      );
    }
  }

  // -------------------- Latency histogram + percentile lines --------------------

  function computePercentiles(buckets) {
    // buckets = [{min_ms, max_ms, count}]. Assume uniform within bucket.
    const total = buckets.reduce((a, b) => a + Number(b.count || 0), 0);
    if (total === 0) return null;
    const targets = { p50: 0.5, p95: 0.95, p99: 0.99 };
    const out = {};
    let running = 0;
    const sorted = [...buckets].sort((a, b) => a.min_ms - b.min_ms);
    for (const [name, q] of Object.entries(targets)) {
      const target = q * total;
      let cum = 0;
      for (const b of sorted) {
        const next = cum + Number(b.count || 0);
        if (next >= target) {
          const span = Math.max(1, b.max_ms - b.min_ms);
          const frac = (target - cum) / Math.max(1, Number(b.count || 0));
          out[name] = b.min_ms + span * frac;
          break;
        }
        cum = next;
      }
    }
    return out;
  }

  const percentileLinesPlugin = {
    id: 'percentileLines',
    afterDatasetsDraw(chart, _args, opts) {
      const lines = opts && opts.lines;
      if (!lines) return;
      const { ctx, scales: { x }, chartArea } = chart;
      ctx.save();
      ctx.font = "10px 'DM Mono', monospace";
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      for (const [label, value] of Object.entries(lines)) {
        if (value == null) continue;
        const px = x.getPixelForValue(value);
        if (px < chartArea.left || px > chartArea.right) continue;
        ctx.beginPath();
        ctx.setLineDash([3, 3]);
        ctx.strokeStyle = 'rgba(255,255,255,0.22)';
        ctx.lineWidth = 1;
        ctx.moveTo(px, chartArea.top);
        ctx.lineTo(px, chartArea.bottom);
        ctx.stroke();
        ctx.setLineDash([]);
        // Label block.
        const text = label.toUpperCase() + '  ' + fmtMs(value);
        const w = ctx.measureText(text).width;
        ctx.fillStyle = 'rgba(20,20,22,0.95)';
        ctx.fillRect(px + 4, chartArea.top + 2, w + 10, 16);
        ctx.fillStyle = '#f0f0f0';
        ctx.fillText(text, px + 9, chartArea.top + 5);
      }
      ctx.restore();
    },
  };

  function renderLatency(l) {
    if (!l || l.empty) { markEmpty('body-latency', EMPTY_HINT); return; }
    const buckets = l.buckets || [];
    if (!buckets.length) { markEmpty('body-latency', EMPTY_HINT); return; }

    // x-axis: bucket center (ms); y-axis: count.
    const points = buckets.map((b) => ({
      x: Math.round((Number(b.min_ms) + Number(b.max_ms)) / 2),
      y: Number(b.count || 0),
    })).sort((a, b) => a.x - b.x);

    const pct = computePercentiles(buckets) || {};

    destroyChart('chart-latency');
    const canvas = $('chart-latency');
    canvas.style.display = '';
    const chart = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        datasets: [{
          label: 'runs',
          data: points,
          backgroundColor: (ctx) => {
            const { chart } = ctx;
            const { ctx: c, chartArea } = chart;
            if (!chartArea) return PALETTE.accent;
            const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
            g.addColorStop(0, PALETTE.accent);
            g.addColorStop(1, 'rgba(0,102,255,0.55)');
            return g;
          },
          borderWidth: 0,
          borderRadius: { topLeft: 3, topRight: 3 },
          maxBarThickness: 18,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        parsing: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltipStyle,
            callbacks: {
              title: (items) => fmtMs(items[0].parsed.x),
              label: (ctx) => fmtNumber(ctx.parsed.y) + ' runs',
            },
          },
          percentileLines: { lines: pct },
        },
        scales: {
          x: {
            type: 'linear',
            ticks: {
              color: PALETTE.tick, font: { family: "'DM Mono'", size: 10 },
              callback: (v) => fmtMs(v), maxTicksLimit: 5,
            },
            grid: { display: false },
            border: { display: false },
          },
          y: {
            ticks: {
              color: PALETTE.tick, font: { family: "'DM Mono'", size: 10 },
              maxTicksLimit: 4,
            },
            grid: { color: PALETTE.grid, drawTicks: false },
            border: { display: false },
            beginAtZero: true,
          },
        },
      },
      plugins: [percentileLinesPlugin],
    });
    charts.set('chart-latency', chart);
    markReady('body-latency');
  }

  // -------------------- Risk (thin doughnut with center label) --------------------

  const doughnutCenterPlugin = {
    id: 'doughnutCenter',
    afterDraw(chart, _args, opts) {
      if (chart.config.type !== 'doughnut') return;
      const { ctx, chartArea: { left, right, top, bottom } } = chart;
      const total = (opts && opts.total) ?? chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
      const label = (opts && opts.label) || 'total';
      const cx = (left + right) / 2;
      const cy = (top + bottom) / 2;
      ctx.save();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#f0f0f0';
      ctx.font = "700 20px 'DM Sans', sans-serif";
      ctx.fillText(fmtNumber(total), cx, cy - 6);
      ctx.fillStyle = '#888';
      ctx.font = "10px 'DM Mono', monospace";
      ctx.fillText(label.toUpperCase(), cx, cy + 12);
      ctx.restore();
    },
  };

  function renderRisk(tools_by_trust_tier, total_pii_masked) {
    const counter = $('pii-counter');
    counter.innerHTML = '<strong>' + fmtNumber(total_pii_masked || 0) + '</strong> PII masked';

    const entries = Object.entries(tools_by_trust_tier || {});
    if (!entries.length) { markEmpty('body-risk', 'no approved tools yet'); return; }

    const tierColor = {
      trusted: PALETTE.trusted, verified: PALETTE.verified,
      caution: PALETTE.caution, restricted: PALETTE.restricted,
      unverified: PALETTE.unverified,
    };
    const labels = entries.map(([k]) => k);
    const data   = entries.map(([, v]) => v);
    const bg     = entries.map(([k]) => tierColor[k] || PALETTE.muted);
    const total  = data.reduce((a, b) => a + b, 0);

    destroyChart('chart-risk');
    const canvas = $('chart-risk');
    canvas.style.display = '';
    const chart = new Chart(canvas.getContext('2d'), {
      type: 'doughnut',
      data: { labels, datasets: [{ data, backgroundColor: bg, borderWidth: 0, hoverOffset: 6 }] },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '78%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              color: PALETTE.tick, font: { family: "'DM Sans'", size: 10 },
              boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: 'circle', padding: 10,
            },
          },
          tooltip: {
            ...tooltipStyle,
            callbacks: {
              label: (ctx) => ctx.label + ': ' + fmtNumber(ctx.parsed) +
                ' (' + ((ctx.parsed / total) * 100).toFixed(0) + '%)',
            },
          },
          doughnutCenter: { total, label: 'tools' },
        },
      },
      plugins: [doughnutCenterPlugin],
    });
    charts.set('chart-risk', chart);
    markReady('body-risk');
  }

  // -------------------- Top tools (horizontal bar) --------------------

  function renderTopTools(top_tools) {
    const rows = top_tools || [];
    if (!rows.length) { markEmpty('body-top-tools', 'no run data yet'); return; }
    const labels = rows.map((r) => r.name);
    const data   = rows.map((r) => r.runs);

    destroyChart('chart-top-tools');
    const canvas = $('chart-top-tools');
    canvas.style.display = '';
    const chart = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'runs', data,
          backgroundColor: (ctx) => {
            const { chart } = ctx;
            const { ctx: c, chartArea } = chart;
            if (!chartArea) return PALETTE.accent;
            const g = c.createLinearGradient(chartArea.left, 0, chartArea.right, 0);
            g.addColorStop(0, 'rgba(0,102,255,0.55)');
            g.addColorStop(1, PALETTE.accent);
            return g;
          },
          borderWidth: 0,
          borderRadius: 3,
          maxBarThickness: 14,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltipStyle,
            callbacks: { label: (ctx) => fmtNumber(ctx.parsed.x) + ' runs' },
          },
        },
        scales: {
          x: {
            ticks: {
              color: PALETTE.tick, font: { family: "'DM Mono'", size: 10 },
              maxTicksLimit: 4,
            },
            grid: { color: PALETTE.grid, drawTicks: false },
            border: { display: false },
            beginAtZero: true,
          },
          y: {
            ticks: { color: PALETTE.tickStrong, font: { family: "'DM Sans'", size: 11 } },
            grid: { display: false },
            border: { display: false },
          },
        },
      },
    });
    charts.set('chart-top-tools', chart);
    markReady('body-top-tools');
  }

  // -------------------- Leaderboard (avatar + inline bar) --------------------

  function renderBuilders(payload) {
    const host = $('builders-body');
    host.innerHTML = '';
    const rows = (payload && payload.builders) || [];
    if (!rows.length) { markEmpty('body-builders', 'no builders yet'); return; }
    const table = document.createElement('table');
    table.className = 'leaderboard';
    table.innerHTML =
      '<thead><tr>' +
        '<th>Builder</th>' +
        '<th class="num">Submissions</th>' +
        '<th class="num">Approval</th>' +
        '<th class="num">Avg reliability</th>' +
        '<th class="num">Total runs</th>' +
      '</tr></thead>';
    const tbody = document.createElement('tbody');
    for (const b of rows) {
      const tr = document.createElement('tr');
      const rate = Math.max(0, Math.min(1, Number(b.approval_rate || 0)));
      tr.innerHTML =
        '<td><div class="lb-builder">' +
          '<div class="lb-avatar">' + escapeHtml(initials(b.author_name, b.author_email)) + '</div>' +
          '<div>' +
            '<div class="lb-name">' + escapeHtml(b.author_name || b.author_email) + '</div>' +
            '<div class="lb-email">' + escapeHtml(b.author_email) + '</div>' +
          '</div>' +
        '</div></td>' +
        '<td class="num">' + fmtNumber(b.submissions) + '</td>' +
        '<td class="num">' +
          '<div class="lb-rate-cell">' +
            '<div class="lb-rate-bar"><div style="width:' + (rate * 100).toFixed(0) + '%;"></div></div>' +
            '<span>' + (rate * 100).toFixed(0) + '%</span>' +
          '</div>' +
        '</td>' +
        '<td class="num">' + (Number(b.avg_reliability)).toFixed(1) + '</td>' +
        '<td class="num">' + fmtNumber(b.total_runs) + '</td>';
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    host.appendChild(table);
    markReady('body-builders');
  }

  // -------------------- Orchestration --------------------

  async function safeFetch(url) {
    try { return await fetchJSON(url); }
    catch (err) {
      if (String(err.message).includes('unauthorized')) throw err;
      console.warn('[analytics] fetch failed', url, err);
      return null;
    }
  }

  function updateTimestamp() {
    const el = $('dash-timestamp');
    if (!el) return;
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    el.textContent = 'Updated ' + hh + ':' + mm;
  }

  async function main() {
    resetCards();
    if (!getAdminKey()) {
      document.querySelectorAll('.card-skeleton').forEach((n) => n.remove());
      document.querySelectorAll('.card-body').forEach((b) => {
        const note = document.createElement('div');
        note.className = 'empty-note';
        note.textContent = 'Admin key required — reload to retry';
        b.appendChild(note);
        b.classList.add('ready');
      });
      return;
    }

    let admin, funnelRes, buildersRes, qualityRes, latencyRes, costRes;
    try {
      [admin, funnelRes, buildersRes, qualityRes, latencyRes, costRes] = await Promise.all([
        safeFetch('/api/admin/analytics'),
        safeFetch('/api/analytics/funnel'),
        safeFetch('/api/analytics/builders'),
        safeFetch('/api/analytics/quality'),
        safeFetch('/api/analytics/latency'),
        safeFetch('/api/analytics/cost-breakdown'),
      ]);
    } catch (err) {
      document.querySelectorAll('.card-body').forEach((b) => {
        b.innerHTML = '<div class="empty-note">Unauthorized — reload to re-enter key</div>';
        b.classList.add('ready');
      });
      return;
    }

    if (admin) {
      renderKPIs(admin);
      renderAdoption(admin.runs_per_day);
      renderRisk(admin.tools_by_trust_tier, admin.total_pii_masked);
      renderTopTools(admin.top_tools);
    } else {
      ['kpi-total-tools','kpi-runs-month','kpi-avg-rating','kpi-pass-rate','kpi-pending']
        .forEach((id) => { $(id).textContent = '—'; });
      markEmpty('body-adoption', 'admin analytics unavailable');
      markEmpty('body-risk', 'admin analytics unavailable');
      markEmpty('body-top-tools', 'admin analytics unavailable');
    }

    if (funnelRes)   renderFunnel(funnelRes);
    else             markEmpty('body-funnel', 'funnel unavailable');

    renderQuality(qualityRes);
    renderLatency(latencyRes);

    if (costRes)     renderCost(costRes);
    else             markEmpty('body-cost', 'cost breakdown unavailable');

    if (buildersRes) renderBuilders(buildersRes);
    else             markEmpty('body-builders', 'leaderboard unavailable');

    updateTimestamp();
  }

  function wireRefresh() {
    const btn = $('dash-refresh');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      btn.classList.remove('spinning');
      void btn.offsetWidth;
      btn.classList.add('spinning');
      await main();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { wireRefresh(); main(); });
  } else {
    wireRefresh();
    main();
  }
})();
