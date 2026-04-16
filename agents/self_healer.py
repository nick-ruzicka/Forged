"""
Self Healer — scheduled job (Celery Beat / cron) that identifies
underperforming approved tools and proposes improved prompts.

Writes a new tool_versions row when improvement is accepted. Never
auto-promotes — a human has to approve from the admin panel.
"""
import logging
import traceback
from datetime import datetime
from pathlib import Path

from agents.prompt_hardener import PromptHardenerAgent
from agents.qa_tester import QATesterAgent

try:
    from api import db
except ImportError:
    db = None


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
HEALER_LOG = LOG_DIR / "self_healer.log"

_logger = logging.getLogger("forge.self_healer")
if not any(isinstance(h, logging.FileHandler) for h in _logger.handlers):
    fh = logging.FileHandler(HEALER_LOG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _logger.addHandler(fh)
_logger.setLevel(logging.INFO)


def _log(msg: str, level: str = "info"):
    getattr(_logger, level, _logger.info)(msg)
    try:
        with open(HEALER_LOG, "a") as fh:
            fh.write(f"[{datetime.utcnow().isoformat()}] {msg}\n")
    except Exception:
        pass


class SelfHealerAgent:
    """Finds underperforming tools and produces improved prompts."""

    def __init__(self, min_flags: int = 2, max_rating: float = 3.0,
                 accept_threshold: float = 0.8):
        self.min_flags = min_flags
        self.max_rating = max_rating
        self.accept_threshold = accept_threshold

    def heal_underperforming_tools(self) -> dict:
        if db is None:
            raise RuntimeError("api.db not importable — cannot run self healer")

        start = datetime.utcnow()
        _log(f"self-healer start at {start.isoformat()}")

        try:
            tools = db.get_underperforming_tools(
                min_flags=self.min_flags, max_rating=self.max_rating,
            )
        except Exception as exc:
            _log(f"query error: {exc!r}", "error")
            return {"ok": False, "error": str(exc), "healed": 0, "skipped": 0}

        _log(f"found {len(tools)} candidate tool(s)")

        healed = []
        skipped = []
        errors = []

        for tool in tools:
            tool_id = tool.get("id")
            try:
                outcome = self._heal_one(tool)
                if outcome["status"] == "healed":
                    healed.append(outcome)
                else:
                    skipped.append(outcome)
                _log(
                    f"tool_id={tool_id} status={outcome['status']} "
                    f"pass_rate={outcome.get('qa_pass_rate')} "
                    f"reason={outcome.get('reason', '')}"
                )
            except Exception as exc:
                trace = traceback.format_exc()
                _log(f"tool_id={tool_id} exception: {exc!r}\n{trace}", "error")
                errors.append({"tool_id": tool_id, "error": str(exc)})

        summary = {
            "ok": True,
            "started_at": start.isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "candidates": len(tools),
            "healed": len(healed),
            "skipped": len(skipped),
            "errors": len(errors),
            "details": {
                "healed": healed,
                "skipped": skipped,
                "errors": errors,
            },
        }
        _log(
            f"self-healer done healed={len(healed)} "
            f"skipped={len(skipped)} errors={len(errors)}"
        )
        return summary

    def _heal_one(self, tool: dict) -> dict:
        tool_id = tool.get("id")
        flagged = []
        try:
            flagged = db.get_recent_flagged_runs(tool_id, limit=10)
        except Exception as exc:
            _log(f"tool_id={tool_id} flagged runs fetch error: {exc!r}", "warning")

        flag_reasons = [r.get("flag_reason") for r in flagged if r.get("flag_reason")]
        security_flags = [{
            "type": "user_flag",
            "severity": "medium",
            "detail": reason,
            "suggestion": "Address root cause in prompt",
        } for reason in flag_reasons[:5]]

        hardener = PromptHardenerAgent()
        hard_res = hardener.run(tool, security_flags=security_flags, red_team=None)
        hardened_prompt = hard_res.get("hardened_prompt") or tool.get("hardened_prompt") or tool.get("system_prompt")

        if not hardened_prompt:
            return {
                "tool_id": tool_id,
                "status": "skipped",
                "reason": "hardener produced no prompt",
            }

        if hardened_prompt.strip() == (tool.get("hardened_prompt") or tool.get("system_prompt") or "").strip():
            return {
                "tool_id": tool_id,
                "status": "skipped",
                "reason": "hardener produced identical prompt",
            }

        qa = QATesterAgent()
        qa_res = qa.run(tool, hardened_prompt=hardened_prompt)
        pass_rate = float(qa_res.get("qa_pass_rate", 0.0) or 0.0)

        if pass_rate <= self.accept_threshold:
            return {
                "tool_id": tool_id,
                "status": "skipped",
                "reason": f"qa pass rate {pass_rate:.2f} <= threshold {self.accept_threshold}",
                "qa_pass_rate": pass_rate,
            }

        new_version = int(tool.get("version") or 1) + 1
        summary = (
            f"Self-healer revision. {hard_res.get('hardening_summary', '')} "
            f"QA pass rate {pass_rate:.0%}."
        )

        try:
            version_id = db.insert_tool_version(
                tool_id=tool_id,
                version=new_version,
                system_prompt=tool.get("system_prompt") or "",
                hardened_prompt=hardened_prompt,
                input_schema=tool.get("input_schema") or "{}",
                change_summary=summary,
                created_by="self-healer",
            )
        except Exception as exc:
            return {
                "tool_id": tool_id,
                "status": "skipped",
                "reason": f"insert_tool_version failed: {exc}",
                "qa_pass_rate": pass_rate,
            }

        return {
            "tool_id": tool_id,
            "status": "healed",
            "version": new_version,
            "version_id": version_id,
            "qa_pass_rate": pass_rate,
            "change_count": hard_res.get("change_count", 0),
            "summary": summary,
        }


def heal_underperforming_tools() -> dict:
    """Module-level convenience wrapper used by Celery / cron."""
    agent = SelfHealerAgent()
    return agent.heal_underperforming_tools()
