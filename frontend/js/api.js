// Forge API client. Vanilla fetch wrapper — JSON in/out, error envelope normalized.

const BASE_URL = '/api';

class ApiError extends Error {
  constructor(message, { status = 0, body = null } = {}) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${BASE_URL}${path}`;
  const headers = {
    'Accept': 'application/json',
    ...(options.headers || {}),
  };
  let body = options.body;
  if (body && typeof body === 'object' && !(body instanceof FormData) && !(body instanceof Blob)) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, { ...options, headers, body });
  } catch (e) {
    throw new ApiError('Network error. Check your connection.', { status: 0 });
  }
  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  let payload = null;
  try {
    payload = isJson ? await res.json() : await res.text();
  } catch (e) { payload = null; }
  if (!res.ok) {
    const msg =
      (payload && typeof payload === 'object' && (payload.error || payload.message)) ||
      (typeof payload === 'string' && payload) ||
      `Request failed (${res.status})`;
    throw new ApiError(msg, { status: res.status, body: payload });
  }
  return payload;
}

function qs(params) {
  if (!params) return '';
  const filtered = Object.entries(params).filter(([, v]) =>
    v != null && v !== '' && !(Array.isArray(v) && v.length === 0)
  );
  if (filtered.length === 0) return '';
  const parts = [];
  for (const [k, v] of filtered) {
    if (Array.isArray(v)) v.forEach((item) => parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(item)}`));
    else parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(v)}`);
  }
  return `?${parts.join('&')}`;
}

// ---------- Tools ----------

async function getTools(filters = {}) {
  return apiFetch(`/tools${qs(filters)}`);
}

async function getTool(id) {
  return apiFetch(`/tools/${encodeURIComponent(id)}`);
}

async function getToolBySlug(slug) {
  return apiFetch(`/tools/slug/${encodeURIComponent(slug)}`);
}

async function submitTool(data) {
  return apiFetch('/tools/submit', { method: 'POST', body: data });
}

async function updateTool(id, data) {
  return apiFetch(`/tools/${encodeURIComponent(id)}`, { method: 'PUT', body: data });
}

async function forkTool(id, data) {
  return apiFetch(`/tools/${encodeURIComponent(id)}/fork`, { method: 'POST', body: data });
}

async function getToolVersions(id) {
  return apiFetch(`/tools/${encodeURIComponent(id)}/versions`);
}

async function getToolInstructions(id) {
  return apiFetch(`/tools/${encodeURIComponent(id)}/instructions`);
}

function toolInstructionsPdfUrl(id) {
  return `${BASE_URL}/tools/${encodeURIComponent(id)}/instructions.pdf`;
}

// ---------- Runs ----------

async function runTool(id, inputs, user) {
  return apiFetch(`/tools/${encodeURIComponent(id)}/run`, {
    method: 'POST',
    body: {
      input_data: inputs,
      user_name: user?.name || '',
      user_email: user?.email || '',
      source: 'web',
    },
  });
}

async function getRuns(toolId, filters = {}) {
  return apiFetch(`/tools/${encodeURIComponent(toolId)}/runs${qs(filters)}`);
}

async function getRun(id) {
  return apiFetch(`/runs/${encodeURIComponent(id)}`);
}

async function rateRun(id, rating, note) {
  return apiFetch(`/runs/${encodeURIComponent(id)}/rate`, {
    method: 'POST',
    body: { rating, note: note || '' },
  });
}

async function flagRun(id, reason) {
  return apiFetch(`/runs/${encodeURIComponent(id)}/flag`, {
    method: 'POST',
    body: { reason },
  });
}

async function resolveToken(token) {
  return apiFetch(`/t/${encodeURIComponent(token)}`);
}

// ---------- Skills ----------

async function getSkills(filters = {}) {
  return apiFetch(`/skills${qs(filters)}`);
}

async function submitSkill(data) {
  return apiFetch('/skills', { method: 'POST', body: data });
}

async function upvoteSkill(id) {
  return apiFetch(`/skills/${encodeURIComponent(id)}/upvote`, { method: 'POST' });
}

async function copySkill(id) {
  return apiFetch(`/skills/${encodeURIComponent(id)}/copy`, { method: 'POST' });
}

function skillDownloadUrl(id) {
  return `${BASE_URL}/skills/${encodeURIComponent(id)}/download`;
}

// ---------- Agent Pipeline ----------

async function getAgentStatus(toolId) {
  return apiFetch(`/agent/status/${encodeURIComponent(toolId)}`);
}

async function getAgentReview(toolId) {
  return apiFetch(`/agent/review/${encodeURIComponent(toolId)}`);
}

// ---------- My Tools ----------

async function getMyTools(email) {
  return apiFetch(`/tools${qs({ author_email: email, include_all_statuses: 'true' })}`);
}

window.ForgeApi = {
  BASE_URL, ApiError, apiFetch,
  getTools, getTool, getToolBySlug,
  submitTool, updateTool, forkTool,
  getToolVersions, getToolInstructions, toolInstructionsPdfUrl,
  runTool, getRuns, getRun, rateRun, flagRun, resolveToken,
  getSkills, submitSkill, upvoteSkill, copySkill, skillDownloadUrl,
  getAgentStatus, getAgentReview,
  getMyTools,
};
