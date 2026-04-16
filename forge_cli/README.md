# forge

Deploy any HTML app to Forge in one command.

The Forge CLI is stdlib-only Python (argparse + urllib + webbrowser + zipfile).
No external dependencies. Works on any Python 3.10+ environment.

## Installation

```bash
pip install -e /path/to/forge/forge_cli
```

Verify:

```bash
forge --version   # 0.1.0
```

## Quick start

Point the CLI at your Forge server (defaults to `http://localhost:8090`):

```bash
forge login http://localhost:8090
```

Deploy the current directory:

```bash
forge deploy
```

If the directory contains a single `index.html`, it is uploaded as-is. If it
contains additional assets, the directory is zipped (excluding `node_modules`,
`.git`, `__pycache__`, `dist`, `build`, hidden dirs) and posted as a multipart
upload. The zip is extracted server-side and `index.html` becomes the app.

## Commands

| Command | Description |
| --- | --- |
| `forge deploy [path] [--name N] [--description D] [--category C] [--host H]` | Submit an HTML app for review. `path` defaults to `.`. Name defaults to the directory's title-cased name. |
| `forge status [--host H]` | Hit `/api/health` and print server status. |
| `forge list [--host H]` | List live apps (tools with `app_type=app`). |
| `forge open SLUG [--host H]` | Open `HOST/apps/SLUG` in your default browser. |
| `forge login [HOST]` | Save default host to `~/.forge/config.json`. |
| `forge --version` | Print CLI version. |

`--host` precedence: explicit flag → `~/.forge/config.json` → `FORGE_HOST` env
var → `http://localhost:8090`.

## Examples

Deploy a single file:

```bash
forge deploy ./my-dashboard.html --name "Sales Dashboard"
```

Deploy a directory with assets:

```bash
forge deploy ./my-app --name "Pipeline Velocity" --category Reporting
```

List live apps:

```bash
forge list
```

Open one:

```bash
forge open pipeline-velocity
```

## With Claude Code

The Forge CLI is designed for AI-assisted workflows. From any project directory,
you can tell Claude Code:

> "Run `forge deploy` to publish this app to Forge."

Claude will execute the command, surface the live URL, and you have a reviewed
and tracked deployment in one shot — no server config, no Dockerfile, no
manual upload.

For multi-file projects, just point Claude at the project root and let it run
`forge deploy --name "..." --description "..."`. The CLI handles zipping,
exclusions, and the Celery-backed review pipeline kicks off automatically.

## What happens after `forge deploy`

1. CLI POSTs the HTML (or zip) to `/api/submit/app`.
2. Server creates a tool row with `app_type='app'` and `status='pending_review'`.
3. The 6-agent review pipeline is dispatched to a Celery worker
   (`agents.tasks.run_pipeline_task`). Flask never blocks.
4. Once approved, the app is live at `/apps/<slug>`.

The CLI returns the live URL immediately so you can poll/share it.
