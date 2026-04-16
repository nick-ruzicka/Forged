# Forge Slack Deployment Bot

Deploy static-HTML apps to Forge directly from Slack — paste an HTML code block,
upload an `.html` file, or use a slash command modal. The bot runs in **socket
mode**, so no public webhook or inbound firewall rule is required.

## What it does

| Trigger | Behavior |
| --- | --- |
| `@forge-bot deploy` with ` ```html ... ``` ` in the same message | Extracts the code block, posts it to `FORGE_API_URL/api/submit/app`, replies with the live URL. |
| `@forge-bot deploy <github_url>` | Forwards to `forge_bot.deployer.handle_push` (T4-owned GitHub deploy path). Helpful error if that module isn't installed yet. |
| `@forge-bot list` | `GET /api/tools?app_type=app` and replies with the deployed apps. |
| `@forge-bot status` | `GET /api/health` and reports Forge status. |
| `.html` file upload | Bot replies ephemerally asking "deploy it? yes/no" — answer within 5 minutes. |
| `/forge deploy` | Opens a modal with `name`, `description`, `HTML` inputs; deploys on submit. |
| `/forge list` | Ephemeral listing of deployed apps. |
| `/forge help` | Ephemeral usage reference. |

Messages posted in `#forge-releases` (or whatever `FORGE_RELEASES_CHANNEL`
points at) are **ignored**. That channel is outbound-only — responding there
would create loops with Forge's release announcer.

## Setup (one-time, ~10 minutes)

1. **Create a Slack app** at https://api.slack.com/apps → *Create New App* →
   *From scratch*. Pick a name (e.g. "Forge") and your workspace.

2. **Add Bot Token Scopes** under *OAuth & Permissions → Scopes → Bot Token
   Scopes*:

   - `app_mentions:read`
   - `channels:history`
   - `chat:write`
   - `commands`
   - `files:read`
   - `groups:history` (optional, for private channels)
   - `im:history` (optional, for DMs)

3. **Enable Socket Mode** under *Settings → Socket Mode* → toggle on →
   generate an *app-level token* with the `connections:write` scope. Copy the
   `xapp-...` token — this is `SLACK_APP_TOKEN`.

4. **Subscribe to bot events** under *Event Subscriptions* (Socket Mode keeps
   it internal, no Request URL needed):

   - `app_mention`
   - `message.channels`
   - `message.groups` (if you want private channel support)
   - `file_shared` (optional — the bot also reads `files` on `message` events)

5. **Register the `/forge` slash command** under *Slash Commands* → *Create
   New Command*:

   - Command: `/forge`
   - Short description: `Deploy or list Forge apps`
   - Usage hint: `deploy | list | help`

6. **Install the app to your workspace** under *Install App* → *Install to
   Workspace*. Copy the *Bot User OAuth Token* (`xoxb-...`) — this is
   `SLACK_BOT_TOKEN`.

7. **Set environment variables** in `.env` at the repo root:

   ```bash
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   FORGE_API_URL=http://localhost:8090   # or your deployed URL
   FORGE_API_KEY=your-admin-key          # optional; X-Admin-Key for privileged endpoints
   FORGE_RELEASES_CHANNEL=forge-releases # channel name the bot ignores (outbound only)
   ```

8. **Invite the bot** to any channel you want it to listen in:
   `/invite @forge-bot` (replace with your app's display name).

## Running

```bash
./forge_bot/start_slack.sh
```

The script sources `.env`, then execs
`venv/bin/python3 forge_bot/slack_bot.py`, appending stdout/stderr to
`forge_bot/logs/slack.log`. To run in the foreground during debugging:

```bash
venv/bin/python3 forge_bot/slack_bot.py
```

## Smoke test

1. In a channel the bot belongs to, post:

   ````
   @forge-bot deploy
   ```html
   <!DOCTYPE html><html><body><h1>Hello Forge</h1></body></html>
   ```
   ````

2. The bot should reply in thread with `🔨 Deployed! Live at: <url>`.

3. `@forge-bot list` should include the new app.

4. `@forge-bot status` should echo Forge's `/api/health` payload.

## Troubleshooting

- **Bot is silent on mention** — Confirm the bot is invited to the channel
  and that *Event Subscriptions → Subscribe to bot events* includes
  `app_mention`.
- **`Missing SLACK_BOT_TOKEN or SLACK_APP_TOKEN`** — `.env` isn't sourced.
  The start script loads `.env` from the repo root; double-check the path
  and that both tokens are present.
- **`Deploy failed: 404 ...`** — Forge hasn't wired up `POST /api/submit/app`
  yet (T3_forge_cli dependency). The bot code is already pointing at the
  correct URL; deploys will start working as soon as that endpoint lands.
- **GitHub deploys say the deployer module isn't installed** — T4's
  `forge_bot/deployer.py` hasn't shipped yet. HTML-code-block and slash
  command deploys work independently.
- **Duplicate replies in `#forge-releases`** — The bot skips that channel by
  name. If you renamed it, set `FORGE_RELEASES_CHANNEL` in `.env`.

## File ownership

This directory is shared with T4 (GitHub app). T5 owns only:

- `forge_bot/slack_bot.py`
- `forge_bot/start_slack.sh`
- `forge_bot/slack_README.md`

T4 owns everything else in `forge_bot/` (webhook, deployer, forge.yaml example,
setup script, top-level README).
