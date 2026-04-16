# forge_bot — GitHub auto-deploy

Push to `main` in any repo that contains a `forge.yaml` and the app auto-deploys
to Forge. The commit gets a `forge/deploy` status back on GitHub with a link to
the live tool.

```
GitHub push -> forge_bot/webhook.py (port 8093) -> deployer.handle_push ->
    git clone -> read forge.yaml -> POST /api/submit/app  (new tool)
                                 -> POST /api/admin/tools/<id>/update-html  (in-place)
-> POST /repos/:owner/:repo/statuses/:sha  (commit status)
```

## 1. Create a GitHub App

1. Go to https://github.com/settings/apps and click **New GitHub App**.
2. Fill in:
   - **Homepage URL:** `https://your-forge-host/`
   - **Webhook URL:** `https://your-forge-host:8093/webhook`
     (port is `8093` — `8091` is taken by the test dashboard)
   - **Webhook secret:** generate a random string and save it (you will put it
     in `.env` as `GITHUB_WEBHOOK_SECRET`)
3. Permissions (under "Repository permissions"):
   - **Contents:** Read-only
   - **Commit statuses:** Read & write
   - **Metadata:** Read-only
4. Subscribe to events: check **Push**.
5. Create the app, then under **Install App** install it on the repos you want
   to auto-deploy.
6. Generate a private key or an installation access token (the tokens are what
   the deployer uses). Put the token in `.env` as `GITHUB_TOKEN`.

## 2. Configure `.env`

Add to `.env` (see `.env.example`):

```
GITHUB_WEBHOOK_SECRET=<the secret you set on the app>
GITHUB_TOKEN=<installation token or fine-grained PAT>
FORGE_API_URL=http://localhost:8090        # change for prod
FORGE_API_KEY=<same as ADMIN_KEY>
FORGE_WEBHOOK_PORT=8093
```

## 3. Start the webhook

```
venv/bin/python3 -m forge_bot.webhook
```

Or install as a service (systemd on Linux, launchd on macOS):

```
forge_bot/setup.sh
```

The setup script installs `git` if missing, writes a service unit, and starts
it. It also prints the GitHub App setup instructions.

### Local dev with ngrok

GitHub can't reach `localhost`. Use ngrok:

```
ngrok http 8093
```

Use the printed `https://*.ngrok.io/webhook` URL as the GitHub App webhook URL.

## 4. Add `forge.yaml` to a repo

Copy `forge_bot/forge.yaml.example` to the repo root as `forge.yaml`:

```yaml
name: My App
tagline: What my app does in one sentence
category: other
entry: index.html
type: app
# Optional
# schedule: "0 8 * * 1-5"
# slack_channel: "#sales-team"
```

If there's no `forge.yaml` but `index.html` exists, the deployer auto-generates
one using the repo name. This makes the common case (one-file HTML apps) zero
config.

## 5. Push

```
git push origin main
```

Webhook log: `forge_bot/logs/webhook.log`
Deployer log: `forge_bot/logs/deploy.log`

Within a few seconds you should see:
1. `push accepted` in `webhook.log`
2. `handle_push start` in `deploy.log`
3. A `forge/deploy` status on the commit at
   `https://github.com/<owner>/<repo>/commit/<sha>`
4. The app live at `https://your-forge-host/apps/<slug>`

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `401 invalid_signature` in `webhook.log` | `GITHUB_WEBHOOK_SECRET` in `.env` does not match the secret on the GitHub App. Rotate the secret on the app and re-set `.env`, then restart the service. |
| `500 webhook_secret_not_configured` | `.env` not loaded by the service — make sure `.env` exists at the project root and the systemd unit has `EnvironmentFile=`. |
| `git clone failed` | Either the repo is private and `GITHUB_TOKEN` is missing/expired, or the token lacks `contents:read`. |
| `repo has neither forge.yaml nor index.html` | Add one of them and re-push. |
| `update-html` returns `not_approved` | The tool with that slug exists but isn't approved yet — wait for the agent pipeline / admin review on the original submission. |
| Webhook never fires | In the GitHub App page -> **Advanced**, inspect the **Recent Deliveries**. Redeliver to debug. Check that port 8093 is reachable (firewall, security group, ngrok URL still valid). |
| `8091 already in use` | You started the webhook on the wrong port. The webhook MUST run on **8093**; 8091 is the test dashboard. Unset `FORGE_WEBHOOK_PORT` or set it to `8093`. |

## Files

- `webhook.py` — Flask app on port 8093, validates `X-Hub-Signature-256` with
  `hmac.compare_digest`, returns 202 fast, dispatches `handle_push` in a
  background thread.
- `deployer.py` — Clones repo, parses `forge.yaml`, POSTs to Forge, posts a
  GitHub commit status. Handles slug collisions by calling
  `/api/admin/tools/<id>/update-html` for in-place redeploys.
- `forge.yaml.example` — Template for app repos.
- `setup.sh` — One-shot installer (systemd on Linux, launchd on macOS).
- `logs/` — `webhook.log` + `deploy.log` (rotated, 1 MB each x 3).
