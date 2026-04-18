# Forge Frontend Rewrite — Next.js + shadcn/ui

**Date:** 2026-04-18
**Status:** Draft
**Scope:** Full frontend rewrite of Forge from vanilla JS to Next.js/React/Tailwind/shadcn

---

## 1. Overview

Forge is an internal AI tool marketplace. The current frontend is vanilla JS (IIFE-per-page, inline styles, no component reuse). This spec describes a complete rewrite using Next.js App Router, React, Tailwind CSS, and shadcn/ui to achieve a modern SaaS aesthetic (Linear/Vercel dark monochrome with persistent sidebar navigation).

**What changes:** The entire `frontend/` directory is replaced by a new `web/` Next.js app.

**What does not change:** The Flask API backend (`api/`), database, migrations, agent pipeline, and all server-side logic remain as-is. The new frontend is a pure consumer of the existing REST API.

**Auth model:** Unchanged. Client-generated `X-Forge-User-Id` stored in localStorage. No login flow. Auth is a separate future project.

---

## 2. Architecture

### Monorepo Layout

```
forge/
├── api/                  ← Flask backend (unchanged)
├── web/                  ← NEW: Next.js frontend
│   ├── app/              ← App Router pages
│   ├── components/       ← UI components
│   ├── lib/              ← API client, hooks, utils
│   ├── public/           ← Static assets
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── tsconfig.json
│   └── package.json
├── frontend/             ← OLD: delete after migration
├── db/                   ← Migrations (unchanged)
├── agents/               ← Agent pipeline (unchanged)
└── ...
```

### Dev Setup

- Next.js runs on port 3000
- Flask runs on port 8090
- `next.config.ts` rewrites `/api/*` to `http://localhost:8090/api/*`
- `npm run dev` starts Next.js; Flask started separately

### Production

- nginx routes `/api/*` to Flask (Gunicorn on 8090)
- nginx routes everything else to Next.js (port 3000, or static export)
- The existing `deploy/nginx.conf` gains a new upstream for Next.js

---

## 3. Design Language

### Aesthetic

Dark monochrome (Linear/Vercel) with a persistent sidebar (like Linear/GitHub).

### Color Tokens

```
--background:     #000000    (page bg)
--surface:        #0a0a0a    (sidebar, cards)
--surface-2:      #111111    (elevated surfaces, hovers)
--border:         #1a1a1a    (default borders)
--border-strong:  #2a2a2a    (emphasized borders)
--text:           #ededed    (primary text)
--text-secondary: #888888    (secondary text)
--text-muted:     #555555    (disabled, hints)
--accent:         #0066FF    (primary action, active state)
--accent-soft:    #0066FF15  (accent backgrounds)
--success:        #2dcc8e    (installed, approved)
--danger:         #ef4444    (reject, remove, error)
--warning:        #f59e0b    (caution badges)
```

### Typography

- Sans: Inter (with system font fallback)
- Mono: Geist Mono (with system monospace fallback)
- Base size: 14px
- Scale: headings use font-weight and size, not color, for hierarchy

### Spacing & Radii

- Spacing scale: 4px base (Tailwind default)
- Border radius: `rounded-md` (6px) for cards/inputs, `rounded-lg` (8px) for modals, `rounded-full` for pills/avatars
- Borders: 1px solid `--border` everywhere

### Loading States

Skeleton placeholders matching content shapes. No spinners for page loads. Spinners only for in-progress mutations (install, submit).

---

## 4. Layout

### Root Layout (`app/layout.tsx`)

Every page shares the same root layout:

```
┌─────────────────────────────────────────────┐
│ [Sidebar]  │         [Content Area]         │
│            │                                │
│ ⚒ Forge    │   (page content renders here)  │
│            │                                │
│ 🔍 Search  │                                │
│            │                                │
│ Apps       │                                │
│ Skills     │                                │
│ My Forge   │                                │
│ Publish    │                                │
│ ────────   │                                │
│ Meeting Pr │                                │
│ Pipeline   │                                │
│ Job Search │                                │
│            │                                │
│            │                                │
│ Admin      │                                │
│ [NR]       │                                │
└─────────────────────────────────────────────┘
```

### Sidebar (`components/sidebar.tsx`)

**Sections (top to bottom):**

1. **Logo** — `⚒ Forge`, monospaced, links to `/`
2. **Search trigger** — text button "Search...", opens `⌘K` command palette
3. **Main nav** — Apps (`/`), Skills (`/skills`), My Forge (`/my-forge`), Publish (`/publish`)
4. **Divider**
5. **Installed Apps** — dynamic list from `GET /api/me/items`. Shows icon + name per app, links to `/apps/[slug]`. Ordered by last opened. Max 8 visible; "Show all" link to My Forge if more.
6. **Spacer** (flex-grow)
7. **Admin** — link to `/admin`, only rendered if `forge_admin_key` exists in localStorage
8. **User avatar** — initials circle at bottom, or `?` if anonymous

**Behavior:**

- Desktop: 220px fixed width
- Collapsed mode: 56px icon-only, toggle button at bottom. Collapse state persisted in localStorage.
- Mobile (<768px): hidden by default, opens as overlay via hamburger button in a slim top bar. Tapping a nav link closes it.
- Active page: highlighted with `accent-soft` background + `accent` text color

---

## 5. Routing

| URL | Page | Data Source |
|-----|------|-------------|
| `/` | Catalog | `GET /api/tools` |
| `/apps/[slug]` | App detail | `GET /api/tools/slug/{slug}` |
| `/skills` | Skills library | `GET /api/skills` |
| `/my-forge` | User shelf | `GET /api/me/items`, `GET /api/me/stars`, `GET /api/me/skills` |
| `/publish` | Submit app | `POST /api/submit/app`, `POST /api/submit/from-github` |
| `/admin` | Review queue | `GET /api/admin/queue`, `GET /api/admin/analytics` |
| `/admin/runs` | Claude runs | `GET /api/claude-runs` |

---

## 6. Pages

### 6.1 Catalog (`/`)

**Layout:** Search bar at top, category filter pills below, card grid below that.

**Search bar:** Full-width input with magnifying glass icon and `⌘K` hint badge. Typing filters the grid via `search` query param to `GET /api/tools`. Debounced 300ms. Also openable via `⌘K` command palette which searches both apps and skills.

**Category pills:** Horizontal scrolling row. "All" + dynamic categories from API results. Active pill uses accent color.

**Recommendations:** If the user has set a role (stored in localStorage from role picker), show a "Recommended for you" section above the main grid with role-matched apps as chips. Apps with matching `role_tags` float to the top of the grid.

**Card grid:** 3 columns desktop, 2 tablet, 1 mobile.

**App card (`components/app-card.tsx`):**
- Icon (emoji, 32x32)
- Name (font-weight 500)
- Tagline (text-secondary, 1 line truncated)
- Footer: author name, install count, star button (☆/★)
- Click anywhere on card → navigate to `/apps/[slug]`
- Install/Open button: "Install" for external, "Open" for embedded, "✓" if already installed

**Empty state:** "No apps match" with suggestion to adjust filters.

**First-visit:** Role picker modal on first load if no role in localStorage. "Welcome to Forge — What's your role?" with 8 buttons: AE, SDR, RevOps, CS, Product, Eng, Recruiter, Other. Selection stored in localStorage, drives recommendations.

### 6.2 App Detail (`/apps/[slug]`)

**Top section:**
- Back link ("← Apps")
- Icon (large, 48x48) + name + tagline
- Author, category badge, install count
- Action buttons: Install/Open (primary), Star (ghost), Full screen link, Source link (if source_url exists)

**Tabs (shadcn `tabs`):**
- **Overview** — description (markdown rendered), features list (bold lines parsed from description), reviews section
- **Open App** — sandboxed iframe loading `/apps/{slug}` from Flask

**Preview banner:** If the app is embedded and not yet installed, show a banner above the iframe: "Sample data — install to make this yours" with "+ Add to my Forge" button. Dismissed once installed.

**Reviews section (within Overview tab):**
- Star rating input (interactive 1-5 stars)
- Text review textarea
- Submit review button
- List of existing reviews: stars, text, author, date
- Data: `GET /api/tools/{id}/reviews`, `POST /api/tools/{id}/reviews`

**Install progress (external apps):**
- When installing an external app, show inline progress: spinner, status label, progress bar, log output
- If forge-agent is unavailable, show fallback: install command in a monospace box with copy button
- Data: `POST /api/me/items/{id}/install`, poll `GET /api/forge-agent/running`

**Iframe sandbox:**
```
sandbox="allow-scripts allow-forms allow-modals allow-downloads"
```
No `allow-same-origin`. This is a deliberate security decision.

### 6.3 Skills (`/skills`)

**Layout:** Same pattern as catalog — search + category pills + sort dropdown + card grid.

**Category pills:** All, Development, Testing, Debugging, Planning, Code Review, Documents, Other.

**Sort dropdown:** Most Upvoted, Newest, Most Downloaded.

**Skill card (`components/skill-card.tsx`):**
- Category badge (top left)
- Download count (top right, if > 0)
- Title (h3)
- Use case / description (text-secondary)
- Prompt preview (monospace, truncated 300 chars)
- Install disclosure: `<details>` with "Install with curl" summary + copy button. Expanded: full command in monospace.
- Footer: upvote button (`⬆ N`), author link, Subscribe button, Download .md button

**Subscribe button:** `+ Subscribe` → calls `POST /api/me/skills/{id}` → becomes `✓ Subscribed` (green). Toast: "Subscribed to [skill]. Run `forge sync` to install."

**Upvote:** Toggle, deduped in localStorage. Toast on double-click: "Already upvoted".

**Submit skill modal (shadcn `dialog`):**
- Trigger: "+ Submit a Skill" button in page header
- Fields: Title (required), "Use this when..." (required), Category (dropdown), SKILL.md contents (monospace textarea, required), GitHub URL (optional), GitHub handle (optional)
- Actions: Cancel, Submit
- On success: toast "Skill submitted", modal closes, grid reloads

**Empty state:** "No skills yet — Be the first to share a prompt template" with "+ Submit a Skill" button.

### 6.4 My Forge (`/my-forge`)

**Tabs (shadcn `tabs`):** Installed (count), Saved (count), Skills (count).

**Identity row:** Top right shows user name + "sign out" link, or "anonymous · set email" button.

**Installed tab:**
- Grid of installed app tiles
- Each tile: icon, name, tagline, open count
- External app badge if `delivery === 'external'`
- Status indicator for external apps: green dot "Running" or gray dot "Not running" (polled every 15s via `GET /api/forge-agent/running`)
- Buttons: "Open" / "Launch" / "Focus" (label varies by state), "Remove" (hover reveals red)
- Click "Open" on embedded app → opens inline pane with app bar (name, "↗ Full screen", "Close") + sandboxed iframe
- Click "Launch" on external app → triggers launch via `POST /api/me/items/{id}/launch`

**Saved tab:**
- Grid of starred apps (same tile layout)
- "Unsave" button instead of "Remove"

**Skills tab:**
- Grid of subscribed skills: icon (📄), title, category, author
- Non-interactive (display only)

**External app modal (shadcn `dialog`):**
- Opens when clicking an external app that needs install info
- Shows: name, tagline, install command (copy-on-click), "View on GitHub →" button (if source_url), Close button

**Empty states per tab:**
- Installed: "Nothing installed yet — Browse the catalog and install apps you want to use." + "Browse apps →"
- Saved: "No saved apps — Star ☆ apps in the catalog to save them for later." + "Browse apps →"
- Skills: "No skills synced — Subscribe to skills in the Skills library, then run `forge sync`." + "Browse skills →"

### 6.5 Publish (`/publish`)

**Mode selector:** Three pills at top: 📝 Paste HTML (default), 📦 Upload file, 🐙 From GitHub.

**Paste panel:**
- Large textarea (min-height 300px) with monospace font
- Placeholder text explaining the format
- Tip: "Tip: drag-drop an .html file directly into this box."
- Drag-drop: accepts `.html` files, reads content into textarea

**Upload panel:**
- Drag-and-drop zone with dashed border
- Label: "📦 Drop a zip or .html file here, or click to browse"
- Drag-over state: highlighted border
- After drop: shows filename + size
- Hidden file input for click-to-browse

**GitHub panel:**
- URL input: placeholder "https://github.com/your-team/your-app"
- Tip: "Public repos work out of the box. Private repos need a deploy token."

**Metadata form (shared across all modes):**
- Name (text, max 60 chars, required)
- Tagline (text, max 100 chars, required, placeholder "What does it do, in 8 words?")
- Category (dropdown: Productivity, Account Research, Email, Reporting, Onboarding, Forecasting, Developer Tools, Writing, Meetings, Other)
- Icon (emoji input, max 3 chars, default ⊞)
- Description (textarea, optional)
- Your name (text, auto-filled from localStorage)
- Your email (email, auto-filled from localStorage, required)

**Submit:**
- "Publish" button (primary)
- Status message above button (red on error)
- On submit: calls `POST /api/submit/app` (paste/upload) or `POST /api/submit/from-github`

**Success view (replaces form):**
- Celebration card with 🎉
- Heading: "[App name] published"
- Message: "It's pending admin review. Once approved, anyone on your team can add it to their Forge."
- App URL in monospace
- Buttons: "Open it", "Go to My Forge", "Publish another"

### 6.6 Admin (`/admin`)

**Gate (`components/admin-gate.tsx`):**
- If no `forge_admin_key` in localStorage: show key input + "Continue" button
- Enter key submits
- Verify via `GET /api/admin/queue` with header — if 401, show "Wrong key — try again"
- On success: store key in localStorage, show admin view

**Stats row:** Three cards — Apps live, Pending review, Skills total. Data: `GET /api/admin/analytics`.

**Review queue:**
- List of pending app tiles
- Each tile: icon (32x32 in bordered box), name, tagline, category, author name + email, HTML byte size
- Inspection badges (lazy-loaded from `GET /api/tools/{id}/inspection`): icon + label + tooltip. Warning badges use amber styling.
- Actions: Approve (green), Reject (red), Preview (ghost)
- Approve: confirm dialog "Approve this app? It becomes live in the catalog immediately." → `POST /api/admin/tools/{id}/approve`
- Reject: prompt for reason → `POST /api/admin/tools/{id}/reject`
- Preview: opens `/apps/{slug}` in new tab

**Empty state:** "🎉 Queue is empty — Nothing pending. Check back when authors publish new apps."

**Toasts:** "Approved" (success), "Rejected" (info), error toasts on failure.

### 6.7 Admin Runs (`/admin/runs`)

**Gate:** Same admin key check as `/admin`.

**Layout:** Split view — run list (280px left sidebar within content area) + detail pane (right).

**Run list:**
- Header: "Claude Runs" with link back to Admin
- Each run item: ID + status badge (running=green, complete=blue, error=red), prompt preview (truncated), timestamp
- Selected item highlighted with accent border
- New run input: textarea "Enter a prompt to run with Claude Code..." + "▶ Run" button
- Auto-refreshes list every 5s

**Detail pane:**
- Status badge + exit code
- Two-column split: Prompt (left) | Output (right)
- Both monospace, scrollable, full height
- If run is still "running", output auto-refreshes every 3s

**Empty state:** "← Select a run to view its log"

---

## 7. Data Fetching & State

### API Client (`lib/api.ts`)

Typed fetch wrapper. All requests include `X-Forge-User-Id` header from localStorage.

```typescript
type ApiOptions = { method?: string; body?: unknown; headers?: Record<string, string> };

async function api<T>(path: string, opts?: ApiOptions): Promise<T> {
  const userId = localStorage.getItem('forge_user_id') || generateUserId();
  const res = await fetch(path, {
    method: opts?.method || 'GET',
    headers: {
      'Accept': 'application/json',
      'X-Forge-User-Id': userId,
      ...(opts?.body ? { 'Content-Type': 'application/json' } : {}),
      ...opts?.headers,
    },
    body: opts?.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}
```

Base URL: reads from `NEXT_PUBLIC_API_URL` env var, defaults to `/api` (proxied to Flask by Next.js).

### SWR Hooks (`lib/hooks.ts`)

```typescript
useApps(filters?)      → SWR → GET /api/tools?...
useApp(slug)           → SWR → GET /api/tools/slug/{slug}
useSkills(filters?)    → SWR → GET /api/skills?...
useMyItems()           → SWR → GET /api/me/items
useMyStars()           → SWR → GET /api/me/stars
useMySkills()          → SWR → GET /api/me/skills
useReviews(toolId)     → SWR → GET /api/tools/{id}/reviews
useAdminQueue()        → SWR → GET /api/admin/queue
useAdminStats()        → SWR → GET /api/admin/analytics
useClaudeRuns()        → SWR → GET /api/claude-runs (refreshInterval: 5000)
useClaudeRun(id)       → SWR → GET /api/claude-runs/{id}/log
```

**Server vs client fetching:** The API client uses `localStorage` for user identity, which is only available on the client. All fetching is client-side via SWR. Server components render the page shell and loading skeletons; data populates after hydration. This is simpler than trying to thread user identity through server components, and SWR's caching makes subsequent navigations instant.

**Optimistic updates:** Install, uninstall, star, unstar, upvote all update the local SWR cache immediately, fire the API call in the background, and roll back on error via `onError` callback.

### User Context (`lib/user-context.tsx`)

React context providing:
- `userId` — from localStorage (generated on first visit)
- `role` — from localStorage (set by role picker)
- `name`, `email` — from localStorage
- `adminKey` — from localStorage (null if not admin)
- `setRole(role)`, `setIdentity(name, email)`, `setAdminKey(key)`, `clearIdentity()`

No global state library. SWR + UserContext covers all needs.

---

## 8. Components

### shadcn/ui Components (installed from registry)

`button`, `badge`, `card`, `command`, `dialog`, `dropdown-menu`, `input`, `textarea`, `select`, `tabs`, `toast` (via sonner), `tooltip`, `separator`, `skeleton`

### Custom Components

| Component | File | Purpose |
|-----------|------|---------|
| Sidebar | `components/sidebar.tsx` | Persistent nav, installed apps list, collapse toggle |
| CommandMenu | `components/command-menu.tsx` | ⌘K palette: searches apps + skills, keyboard navigable, navigates on select |
| AppCard | `components/app-card.tsx` | Catalog grid card with icon, name, tagline, author, install count, star |
| SkillCard | `components/skill-card.tsx` | Skills grid card with upvote, subscribe, install disclosure, download |
| AppEmbed | `components/app-embed.tsx` | Sandboxed iframe wrapper (`allow-scripts allow-forms allow-modals allow-downloads`, no `allow-same-origin`) |
| StarButton | `components/star-button.tsx` | Toggle star with optimistic SWR update |
| InstallButton | `components/install-button.tsx` | Install/Open with optimistic update + sidebar installed-apps refresh |
| CategoryPills | `components/category-pills.tsx` | Horizontal scrolling filter pills with active state |
| EmptyState | `components/empty-state.tsx` | Reusable: icon + heading + message + optional CTA button |
| AdminGate | `components/admin-gate.tsx` | Admin key input, verify, persist to localStorage |
| ReviewCard | `components/review-card.tsx` | Individual review display: stars, text, author, date |
| ReviewForm | `components/review-form.tsx` | Star rating input + text area + submit button |
| RolePicker | `components/role-picker.tsx` | First-visit modal: 8 role buttons, stores selection |
| InstallProgress | `components/install-progress.tsx` | Spinner, status label, progress bar, log output for external installs |
| AppPane | `components/app-pane.tsx` | Inline app viewer on My Forge: app bar (name, fullscreen, close) + iframe |
| PublishForm | `components/publish-form.tsx` | Mode tabs (paste/upload/github) + metadata fields + submit |
| DropZone | `components/drop-zone.tsx` | Drag-and-drop file upload area |
| RunDetail | `components/run-detail.tsx` | Claude run: prompt/output split, status badge, auto-refresh |

---

## 9. Keyboard Shortcuts

Handled in root layout via a `useEffect` on `document.addEventListener('keydown', ...)`.

| Shortcut | Action |
|----------|--------|
| `⌘K` / `Ctrl+K` | Open command palette |
| `/` | Focus search input (if on catalog or skills page) |
| `Esc` | Close command palette, close modals, close app pane |
| `↑` / `↓` | Navigate cards in catalog grid (when grid is focused) |
| `Enter` | Open selected card |
| `I` | Install selected app (when card is focused) |
| `g` then `c` | Navigate to catalog |
| `g` then `s` | Navigate to skills |
| `g` then `m` | Navigate to My Forge |
| `g` then `k` | Navigate to skills (legacy alias) |

The `g`-prefix chords use a 900ms timeout window.

---

## 10. Milestone Toasts

Track user milestones in localStorage. Show a celebratory toast on first occurrence:

| Milestone | Toast Message |
|-----------|---------------|
| `first_install` | "You installed your first app! Open it from the sidebar." |
| `first_star` | "Starred! Find it in My Forge → Saved." |
| `first_submission` | "App submitted! It's in the review queue." |
| `first_approval` | "Your app was approved and is live." |

---

## 11. API Proxy Configuration

### next.config.ts

```typescript
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8090/api/:path*',
      },
      {
        source: '/apps/:path*',
        destination: 'http://localhost:8090/apps/:path*',
      },
    ];
  },
};
```

Both `/api/*` and `/apps/*` (for iframe content) proxy to Flask.

---

## 12. Production Deploy

### nginx.conf changes

Add upstream for Next.js:

```nginx
upstream nextjs {
    server 127.0.0.1:3000;
}

# /api and /apps route to Flask (existing)
location /api/ {
    proxy_pass http://flask;
}
location /apps/ {
    proxy_pass http://flask;
}

# Everything else routes to Next.js (new)
location / {
    proxy_pass http://nextjs;
}
```

### docker-compose.yml changes

Add a `web` service:

```yaml
web:
  build:
    context: ./web
    dockerfile: Dockerfile
  ports:
    - "3000:3000"
  environment:
    - NEXT_PUBLIC_API_URL=/api
  depends_on:
    - flask
```

---

## 13. Migration Strategy

1. Build the Next.js app in `web/` while the old `frontend/` continues to serve
2. Test each page against the live Flask API
3. Switch nginx to route to Next.js
4. Delete `frontend/` directory
5. Remove old vanilla JS references from Flask's static file serving

No feature flags needed — this is a clean cutover. The old and new frontends can run simultaneously on different ports during development.

---

## 14. Out of Scope

These are explicitly deferred to future work:

- **Authentication / SSO** — current anonymous UUID model stays
- **Backend rewrite** — Flask stays as-is
- **Real-time features** — no WebSocket push, polling only
- **Internationalization** — English only
- **Accessibility audit** — use shadcn/ui defaults (which are good), but no dedicated ARIA audit
- **E2E tests** — not part of this rewrite; add in a follow-up
- **Dark/light mode toggle** — dark mode only (matches current design)
