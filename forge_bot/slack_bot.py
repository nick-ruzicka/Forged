"""Forge Slack Deployment Bot.

Socket-mode Slack bot that lets the RevOps team deploy static-HTML apps to
Forge from Slack: paste an HTML code block after @forge-bot deploy, drop an
attached .html file into a channel, or use the /forge slash command.
"""
import os
import re
import sys
import json
import time
import logging

import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

try:
    from forge_bot.deployer import handle_push  # T4-owned GitHub deploy path
except ImportError:
    handle_push = None

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("forge-slack")

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
FORGE_API_URL = os.environ.get("FORGE_API_URL", "http://localhost:8090").rstrip("/")
FORGE_API_KEY = os.environ.get("FORGE_API_KEY", "")
RELEASES_CHANNEL = os.environ.get("FORGE_RELEASES_CHANNEL", "forge-releases")

UPLOAD_PROMPT_TTL_SECONDS = 5 * 60
HTML_CODE_BLOCK_RE = re.compile(r"```(?:html)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
GITHUB_URL_RE = re.compile(r"https?://github\.com/[^\s>|]+", re.IGNORECASE)

app = App(token=SLACK_BOT_TOKEN)

pending_uploads: dict = {}


def forge_headers() -> dict:
    h = {"Content-Type": "application/json"}
    if FORGE_API_KEY:
        h["X-Admin-Key"] = FORGE_API_KEY
    return h


def is_releases_channel(channel_name: str) -> bool:
    if not channel_name:
        return False
    return channel_name.lstrip("#") == RELEASES_CHANNEL.lstrip("#")


def extract_html(text: str) -> str:
    if not text:
        return ""
    for match in HTML_CODE_BLOCK_RE.finditer(text):
        candidate = (match.group(1) or "").strip()
        if candidate:
            return candidate
    return ""


def looks_like_html(content: str) -> bool:
    if not content:
        return False
    lowered = content.lower().lstrip()
    return lowered.startswith("<!doctype") or "<html" in lowered


def deploy_html(html: str, name: str, description: str, author: str) -> dict:
    payload = {
        "app_html": html,
        "name": name or "Slack Deployed App",
        "description": description or "Deployed from Slack",
        "author_name": author or "slack-bot",
        "author_email": f"{author or 'slack-bot'}@slack",
        "app_type": "app",
    }
    url = f"{FORGE_API_URL}/api/submit/app"
    log.info("POST %s (html_len=%d)", url, len(html))
    resp = requests.post(url, json=payload, headers=forge_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def format_deploy_success(result: dict) -> str:
    url = result.get("url") or result.get("app_url") or result.get("endpoint_url") or ""
    slug = result.get("slug") or ""
    if not url and slug:
        url = f"{FORGE_API_URL}/apps/{slug}"
    return (
        f"🔨 Deployed! Live at: {url}\n"
        "• Share that link with your team — anyone can open it in a browser.\n"
        "• Tweak the HTML and re-run `@forge-bot deploy` to ship a new version.\n"
        "• Run `@forge-bot list` to see every app you've shipped."
    )


def fetch_tools_list() -> list:
    resp = requests.get(
        f"{FORGE_API_URL}/api/tools",
        params={"app_type": "app"},
        headers=forge_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        return data.get("tools") or data.get("items") or []
    return data or []


def format_tools_list(tools: list) -> str:
    if not tools:
        return "No apps deployed yet. Run `@forge-bot deploy` with an HTML snippet to ship your first one."
    lines = ["*Forge apps:*"]
    for tool in tools[:25]:
        name = tool.get("name") or tool.get("slug") or "unknown"
        slug = tool.get("slug") or ""
        tier = tool.get("trust_tier") or tool.get("tier") or ""
        url = tool.get("endpoint_url") or (f"{FORGE_API_URL}/apps/{slug}" if slug else "")
        line = f"• *{name}*"
        if tier:
            line += f" — `{tier}`"
        if url:
            line += f" — {url}"
        lines.append(line)
    return "\n".join(lines)


def fetch_health() -> dict:
    resp = requests.get(f"{FORGE_API_URL}/api/health", headers=forge_headers(), timeout=10)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {"status": resp.text.strip() or "ok"}


def channel_name_from_event(client, event) -> str:
    channel_id = event.get("channel") or ""
    if not channel_id:
        return ""
    try:
        info = client.conversations_info(channel=channel_id)
        return (info.get("channel") or {}).get("name", "")
    except Exception as exc:
        log.warning("conversations_info failed for %s: %s", channel_id, exc)
        return ""


@app.event("app_mention")
def handle_mention(body, event, say, client, logger):
    channel_name = channel_name_from_event(client, event)
    if is_releases_channel(channel_name):
        log.info("ignoring mention in releases channel %s", channel_name)
        return

    text = event.get("text", "") or ""
    user = event.get("user") or "someone"
    thread_ts = event.get("thread_ts") or event.get("ts")
    lowered = text.lower()

    if "deploy" in lowered:
        github_match = GITHUB_URL_RE.search(text)
        if github_match:
            if handle_push is None:
                say(
                    channel=event["channel"],
                    thread_ts=thread_ts,
                    text=(
                        "GitHub deploys need the `forge_bot.deployer` module, which isn't installed "
                        "on this bot yet. Ask the Forge admin to finish T4's setup (see forge_bot/README.md)."
                    ),
                )
                return
            try:
                result = handle_push(github_match.group(0))
                url = (result or {}).get("url") or ""
                say(
                    channel=event["channel"],
                    thread_ts=thread_ts,
                    text=f"🔨 Deployed from GitHub! Live at: {url}".strip(),
                )
            except Exception as exc:
                log.exception("github deploy failed")
                say(channel=event["channel"], thread_ts=thread_ts, text=f"GitHub deploy failed: {exc}")
            return

        html = extract_html(text)
        if not html or not looks_like_html(html):
            say(
                channel=event["channel"],
                thread_ts=thread_ts,
                text=(
                    "Paste an HTML snippet inside a triple-backtick code block, like:\n"
                    "```html\n<!DOCTYPE html>...```"
                ),
            )
            return
        try:
            result = deploy_html(html, name=f"Slack deploy by {user}", description=f"Deployed by <@{user}> from Slack", author=user)
            say(channel=event["channel"], thread_ts=thread_ts, text=format_deploy_success(result))
        except requests.HTTPError as exc:
            body_text = getattr(exc.response, "text", "") or str(exc)
            log.error("deploy HTTPError: %s", body_text)
            say(channel=event["channel"], thread_ts=thread_ts, text=f"Deploy failed: {body_text[:500]}")
        except Exception as exc:
            log.exception("deploy failed")
            say(channel=event["channel"], thread_ts=thread_ts, text=f"Deploy failed: {exc}")
        return

    if "list" in lowered:
        try:
            tools = fetch_tools_list()
            say(channel=event["channel"], thread_ts=thread_ts, text=format_tools_list(tools))
        except Exception as exc:
            log.exception("list failed")
            say(channel=event["channel"], thread_ts=thread_ts, text=f"Could not fetch tools: {exc}")
        return

    if "status" in lowered:
        try:
            health = fetch_health()
            say(
                channel=event["channel"],
                thread_ts=thread_ts,
                text=f"Forge status: `{json.dumps(health, sort_keys=True)}`",
            )
        except Exception as exc:
            log.exception("status failed")
            say(channel=event["channel"], thread_ts=thread_ts, text=f"Could not reach Forge: {exc}")
        return

    say(
        channel=event["channel"],
        thread_ts=thread_ts,
        text=(
            "Hi! Try one of these:\n"
            "• `@forge-bot deploy` with an HTML code block\n"
            "• `@forge-bot deploy <github_url>`\n"
            "• `@forge-bot list`\n"
            "• `@forge-bot status`\n"
            "Or use `/forge help` for slash commands."
        ),
    )


def download_slack_file(url: str) -> str:
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.text


@app.event("message")
def handle_message_events(body, event, client, say, logger):
    if event.get("subtype") and event.get("subtype") != "file_share":
        return
    user = event.get("user")
    if not user:
        return

    channel_name = channel_name_from_event(client, event)
    if is_releases_channel(channel_name):
        return

    files = event.get("files") or []
    html_files = [f for f in files if (f.get("filetype") == "html" or (f.get("name") or "").lower().endswith(".html"))]
    if html_files:
        first = html_files[0]
        pending_uploads[(event.get("channel"), user)] = {
            "file": first,
            "ts": time.time(),
        }
        try:
            client.chat_postEphemeral(
                channel=event["channel"],
                user=user,
                text=(
                    f"I see you uploaded `{first.get('name', 'an HTML file')}`! "
                    "Want me to deploy it to Forge? Reply `yes` to deploy or `no` to skip."
                ),
            )
        except Exception as exc:
            log.warning("ephemeral prompt failed: %s", exc)
        return

    text = (event.get("text") or "").strip().lower()
    if text not in {"yes", "y", "no", "n"}:
        return
    pending = pending_uploads.get((event.get("channel"), user))
    if not pending:
        return
    if time.time() - pending["ts"] > UPLOAD_PROMPT_TTL_SECONDS:
        pending_uploads.pop((event.get("channel"), user), None)
        return
    pending_uploads.pop((event.get("channel"), user), None)
    if text in {"no", "n"}:
        try:
            client.chat_postEphemeral(channel=event["channel"], user=user, text="Skipped. Ping me again if you change your mind.")
        except Exception:
            pass
        return

    file_info = pending["file"]
    download_url = file_info.get("url_private_download") or file_info.get("url_private")
    if not download_url:
        say(channel=event["channel"], text="I couldn't read that file — try pasting the HTML in a code block instead.")
        return
    try:
        html = download_slack_file(download_url)
        if not looks_like_html(html):
            say(channel=event["channel"], text="That file didn't look like HTML (no <!DOCTYPE or <html> tag). Skipping.")
            return
        result = deploy_html(html, name=file_info.get("title") or file_info.get("name") or f"Slack upload by {user}", description=f"Uploaded by <@{user}>", author=user)
        say(channel=event["channel"], text=format_deploy_success(result))
    except Exception as exc:
        log.exception("upload deploy failed")
        say(channel=event["channel"], text=f"Deploy failed: {exc}")


@app.command("/forge")
def handle_forge_command(ack, body, client, respond, logger):
    ack()
    text = (body.get("text") or "").strip().lower()
    channel_id = body.get("channel_id")
    trigger_id = body.get("trigger_id")
    user_id = body.get("user_id") or "slack-user"

    if text.startswith("deploy"):
        try:
            client.views_open(
                trigger_id=trigger_id,
                view={
                    "type": "modal",
                    "callback_id": "forge_deploy_modal",
                    "private_metadata": channel_id or "",
                    "title": {"type": "plain_text", "text": "Deploy to Forge"},
                    "submit": {"type": "plain_text", "text": "Deploy"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "name_block",
                            "label": {"type": "plain_text", "text": "App name"},
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "name_input",
                                "placeholder": {"type": "plain_text", "text": "e.g. Pipeline Dashboard"},
                            },
                        },
                        {
                            "type": "input",
                            "block_id": "desc_block",
                            "label": {"type": "plain_text", "text": "Description"},
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "desc_input",
                                "multiline": False,
                            },
                            "optional": True,
                        },
                        {
                            "type": "input",
                            "block_id": "html_block",
                            "label": {"type": "plain_text", "text": "HTML"},
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "html_input",
                                "multiline": True,
                                "placeholder": {"type": "plain_text", "text": "<!DOCTYPE html>..."},
                            },
                        },
                    ],
                },
            )
        except Exception as exc:
            log.exception("views_open failed")
            respond(response_type="ephemeral", text=f"Could not open modal: {exc}")
        return

    if text.startswith("list") or text == "":
        try:
            tools = fetch_tools_list()
            respond(response_type="ephemeral", text=format_tools_list(tools))
        except Exception as exc:
            log.exception("list failed")
            respond(response_type="ephemeral", text=f"Could not fetch tools: {exc}")
        return

    if text.startswith("help"):
        respond(
            response_type="ephemeral",
            text=(
                "*Forge slash commands*\n"
                "• `/forge deploy` — paste HTML in a modal and deploy\n"
                "• `/forge list` — list deployed apps\n"
                "• `/forge help` — this message\n\n"
                "You can also `@forge-bot deploy` with an HTML code block, upload an `.html` file, "
                "or `@forge-bot deploy <github_url>`."
            ),
        )
        return

    respond(response_type="ephemeral", text="Unknown subcommand. Try `/forge help`.")


@app.view("forge_deploy_modal")
def handle_modal_submit(ack, body, client, view, logger):
    values = view["state"]["values"]
    name = values["name_block"]["name_input"]["value"] or ""
    description = (values.get("desc_block", {}).get("desc_input", {}).get("value") or "")
    html = values["html_block"]["html_input"]["value"] or ""
    channel_id = view.get("private_metadata") or ""
    user_id = (body.get("user") or {}).get("id") or "slack-user"

    if not looks_like_html(html):
        ack(
            response_action="errors",
            errors={"html_block": "Needs a <!DOCTYPE html> or <html> tag."},
        )
        return
    ack()

    try:
        result = deploy_html(html, name=name, description=description, author=user_id)
        text = format_deploy_success(result)
    except Exception as exc:
        log.exception("modal deploy failed")
        text = f"Deploy failed: {exc}"

    if channel_id:
        try:
            client.chat_postMessage(channel=channel_id, text=text)
        except Exception as exc:
            log.warning("chat_postMessage failed: %s", exc)
            try:
                client.chat_postMessage(channel=user_id, text=text)
            except Exception:
                pass
    else:
        try:
            client.chat_postMessage(channel=user_id, text=text)
        except Exception:
            pass


def main():
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        print("Missing SLACK_BOT_TOKEN or SLACK_APP_TOKEN in environment.", file=sys.stderr)
        sys.exit(1)
    log.info("Starting Forge Slack bot in socket mode (api=%s)", FORGE_API_URL)
    SocketModeHandler(app, SLACK_APP_TOKEN).start()


if __name__ == "__main__":
    main()
