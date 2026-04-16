"""
BaseAgent — shared functionality for every agent in the Forge pipeline.
Handles Anthropic API calls, JSON parsing, and file-based logging.
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
AGENT_LOG_PATH = LOG_DIR / "agents.log"

_file_handler = logging.FileHandler(AGENT_LOG_PATH)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
_logger = logging.getLogger("forge.agents")
if not any(isinstance(h, logging.FileHandler) for h in _logger.handlers):
    _logger.addHandler(_file_handler)
_logger.setLevel(logging.INFO)


class BaseAgent:
    HAIKU = "claude-haiku-4-5-20251001"
    SONNET = "claude-sonnet-4-6"

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if Anthropic is None:
                raise RuntimeError(
                    "anthropic SDK is not installed. "
                    "pip install anthropic"
                )
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set in environment")
            self._client = Anthropic(api_key=api_key)
        return self._client

    def _call_claude(self, system_prompt: str, user_message: str,
                     max_tokens: int = 2000, temperature: float = 0.2) -> str:
        """Call Claude API and return the flat text of the first content block."""
        start = time.time()
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text_parts = []
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    text_parts.append(block.text)
                elif hasattr(block, "text"):
                    text_parts.append(block.text)
            text = "".join(text_parts).strip()
            elapsed = int((time.time() - start) * 1000)
            self.log(f"call ok model={self.model} tokens={getattr(response.usage, 'output_tokens', '?')} elapsed_ms={elapsed}")
            return text
        except Exception as exc:
            self.log(f"call error model={self.model} error={exc!r}")
            raise

    def _parse_json(self, text: str):
        """Safely parse JSON from Claude output, stripping markdown code fences."""
        if text is None:
            return None
        cleaned = text.strip()
        fence = re.match(r"^```(?:json)?\s*(.*?)```\s*$", cleaned, re.DOTALL)
        if fence:
            cleaned = fence.group(1).strip()
        else:
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```", 2)[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            self.log(f"json parse failed: {cleaned[:200]!r}")
            return None

    def log(self, message: str, level: str = "info"):
        ts = datetime.utcnow().isoformat()
        line = f"[{ts}] [{self.name}] {message}"
        getattr(_logger, level, _logger.info)(line)
        try:
            with open(AGENT_LOG_PATH, "a") as fh:
                fh.write(line + "\n")
        except Exception:
            pass

    def run(self, *args, **kwargs):
        raise NotImplementedError
