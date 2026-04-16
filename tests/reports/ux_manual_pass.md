# Manual UX Pass — 2026-04-16

Done by reading the rendered pages at desktop 1440×900 and mobile 375×812.
Findings grouped by severity, with page + element + recommendation.

## 🔴 High impact (user-blocking or trust-damaging)

### 1. Creator and Workflow pages have no header/nav
- `frontend/creator.html`, `frontend/workflow.html` render without the global header bar. Only a tiny "← Back to catalog" link.
- Breaks visual consistency — feels like a different product. Users who navigate here via direct link can't cross-navigate to Catalog / Skills / My Tools / Submit without going back.
- **Fix:** include the shared `<header>` markup in both pages (same as index.html / tool.html). 10-line change each.

### 2. Mobile navigation is unreachable
- Every page on mobile (375px) shows "FORGE ?" in the header and nothing else. No hamburger, no nav links, no Skills/My Tools/Submit access.
- The help `?` is present but the actual nav disappears at the breakpoint.
- **Fix:** add a hamburger menu that opens a nav drawer, or switch to a bottom tab bar on mobile. The nav items should never become unreachable.

### 3. Two `?` icons in the header, side by side
- Catalog header has a plain gray `?` immediately followed by a blue-filled `?` in a circle.
- Looks like a bug — user will wonder which to click.
- **Fix:** keep only one. Probably the blue "help" button; delete the plain `?`.

### 4. Apps cards in catalog use inconsistent badge conventions
- Prompt tools show category badge (top-left) + trust tier badge (top-right).
- The spec says app_type='app' cards should show an "APP" badge in place of the category. Current rendering: "OTHER" + "Trusted" for the Job Search Pipeline — but no visible APP badge.
- Either the branch is missing or being overridden. **Fix:** verify `renderToolCard` branch on `tool.app_type === 'app'` actually renders the APP badge and not the category.

## 🟡 Medium impact (friction or polish)

### 5. "Continue" button on submit step 0 gives no hint it's disabled
- `/submit.html` shows the format-selector screen. The "Continue →" button is ghosted (disabled) until a card is picked, but there's no label saying "Pick one to continue" and the cards have no visible selected state.
- **Fix:** add `<small>Pick a format to continue</small>` next to the button and give the selectable cards an obvious hover + selected outline.

### 6. Dual "All" pills are ambiguous
- Catalog filter bar has two "All" pills both showing active (one for category, one for trust tier). Without the labels above them, users can't tell which "All" they just clicked.
- **Fix:** either remove the "All" chip and make the row represent "no filter" by default, or prefix each row with a quiet label ("Category:", "Trust:").

### 7. "Create with AI" button competes with search input
- Sits immediately to the right of the full-width search bar and is the only brightly-colored CTA in that row.
- Visually outweighs the search itself. Users wanting to *find* a tool may feel pushed toward *creating* one.
- **Fix:** make the "Create with AI" button secondary-tinted (outlined), or move it down into the filter bar next to the sort dropdown.

### 8. Run / runs triangle icon is ambiguous
- `▶ 512` in card metadata means "run count" but `▶` usually means "start/play".
- **Fix:** use a different icon (e.g., `↻ 512 runs` or `⚡ 512`) or add the word "runs".

### 9. Output-type label formatting is inconsistent
- `= Consistent` (equals sign prefix) for deterministic, `⚡ Variable` for probabilistic, `~ Mixed` for mixed — but the third is shown as `- Mixed` (hyphen) in several cards.
- **Fix:** pick one symbol set and apply consistently. Suggest emoji/icon prefix, not ASCII punctuation.

### 10. "0 users" when runs > 0 is a broken signal
- Tool detail page shows `254 runs | 4.0 rating | 0 users | Last run: just now`.
- Seed data inserts runs without populating unique users. Either drop the "0 users" display when the number is zero, or fix the seed to seed users too.
- **Fix:** hide `users` when count is 0.

### 11. Skills page cards dominated by install command
- Each skill card has a full-width code block with `mkdir -p ... && curl -L -o ...` — it's 2/3 of the card's visual weight. The actual skill prompt is collapsed smaller than the install snippet.
- **Fix:** put the install command behind a "Copy install command" button or inside a disclosure. Show the prompt as the primary content.

### 12. Seed skills are duplicated (3 unique × 2 cards)
- Catalog skills page shows each seed skill twice. Seed script probably ran twice.
- **Fix:** clean seed data or add `ON CONFLICT DO NOTHING` to the seed insert.

## 🟢 Low impact (nice-to-have)

### 13. Footer links don't look like links
- `#forge-help · status` in the footer are blue but no underline — easy to miss as clickable. A hover state can't be seen in screenshots but visually they read as secondary text.
- **Fix:** subtle dotted underline or a tiny icon.

### 14. Creator example cards wrap titles badly
- "Cold outreach email" wraps to "Cold / outreach / email" on three lines because the left column is too narrow.
- **Fix:** give the title column more room (min-width 140px) or use `white-space: nowrap` with truncation.

### 15. Apps have no "exit" affordance
- Once you open `/apps/job-search-pipeline` (or any app), there's no header, no breadcrumb, no way to get back to Forge catalog short of the browser back button.
- **Fix:** inject a slim "← Forge catalog" strip at the top of the injected FORGE_APP script-tag shell (added by api/apps.py).

### 16. Admin 0-badge is visible even when logged out
- The "0" pending-review counter chip shows in the header before admin auth happens. Cosmetically off.
- **Fix:** hide the badge until the admin key has been validated.

## Scorecard

| Area | Grade | Notes |
|------|-------|-------|
| Visual design | A- | Dark theme is clean, typography solid (DM Sans), accent color confident |
| Information hierarchy | B+ | Cards are scannable; trust tiers communicate risk well |
| Mobile | C | Nav disappears; otherwise layouts adapt correctly |
| Consistency | B- | Creator + Workflow pages break the global header contract |
| Empty states | B | Apps and kanban show the empty state with hints; other pages don't all |
| Accessibility | not assessed | Need a dedicated ARIA / keyboard / contrast audit |
