"""
Runtime DLP masking engine.

Detects PII in string inputs, masks it with deterministic tokens before the
Claude API call, and restores original values in the output if the tokens
survived the round-trip. Operates independently of the agent pipeline's
security review (see SPEC "RUNTIME DLP LAYER").
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

PII_PATTERNS: Dict[str, re.Pattern] = {
    # Order matters — credit card is checked before phone so 16-digit sequences
    # with spaces/dashes don't get mis-matched as a phone number.
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
}

TOKEN_PREFIX = {
    "email": "EMAIL",
    "phone": "PHONE",
    "ssn": "SSN",
    "credit_card": "CC",
}


class DLPEngine:
    """Detect, mask, and unmask PII in text.

    Usage:
        engine = DLPEngine()
        masked = engine.mask_text("email me at a@b.com")
        # engine.get_token_map() -> {"[EMAIL_1]": "a@b.com"}
        restored = engine.unmask_text(claude_output, engine.get_token_map())
    """

    def __init__(self) -> None:
        self._token_map: Dict[str, str] = {}
        self._reverse: Dict[str, str] = {}
        self._counters: Dict[str, int] = {t: 0 for t in PII_PATTERNS}

    # -------- detection --------

    @staticmethod
    def detect_pii(text: str) -> List[Dict[str, Any]]:
        """Return a list of {type, value, start, end} matches in ``text``.

        Overlapping matches are resolved by the order in ``PII_PATTERNS``
        (credit_card > ssn > email > phone).
        """
        if not isinstance(text, str) or not text:
            return []

        matches: List[Dict[str, Any]] = []
        claimed: List[Tuple[int, int]] = []
        for pii_type, pattern in PII_PATTERNS.items():
            for m in pattern.finditer(text):
                start, end = m.start(), m.end()
                if any(not (end <= s or start >= e) for s, e in claimed):
                    continue
                claimed.append((start, end))
                matches.append({
                    "type": pii_type,
                    "value": m.group(0),
                    "start": start,
                    "end": end,
                })
        matches.sort(key=lambda m: m["start"])
        return matches

    # -------- masking --------

    def _token_for(self, pii_type: str, value: str) -> str:
        if value in self._reverse:
            return self._reverse[value]
        self._counters[pii_type] = self._counters.get(pii_type, 0) + 1
        token = f"[{TOKEN_PREFIX[pii_type]}_{self._counters[pii_type]}]"
        self._token_map[token] = value
        self._reverse[value] = token
        return token

    def mask_text(self, text: str) -> str:
        """Replace every PII match in ``text`` with a deterministic token.

        Tokens look like ``[EMAIL_1]``, ``[PHONE_2]`` and are reused if the
        same raw value appears multiple times.
        """
        if not isinstance(text, str) or not text:
            return text

        matches = self.detect_pii(text)
        if not matches:
            return text

        # Rebuild left-to-right so positions stay valid.
        out: List[str] = []
        cursor = 0
        for m in matches:
            out.append(text[cursor:m["start"]])
            out.append(self._token_for(m["type"], m["value"]))
            cursor = m["end"]
        out.append(text[cursor:])
        return "".join(out)

    def mask_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Apply ``mask_text`` to every string value in ``inputs``."""
        if not isinstance(inputs, dict):
            return inputs
        cleaned: Dict[str, Any] = {}
        for k, v in inputs.items():
            cleaned[k] = self.mask_text(v) if isinstance(v, str) else v
        return cleaned

    def unmask_text(self, masked_text: str, token_map: Dict[str, str] | None = None) -> str:
        """Restore original values for any tokens that appear in ``masked_text``.

        ``token_map`` defaults to the engine's own map so this works inline;
        callers who persist the map across processes should pass it explicitly.
        """
        if not isinstance(masked_text, str) or not masked_text:
            return masked_text
        mapping = token_map if token_map is not None else self._token_map
        if not mapping:
            return masked_text
        # Replace the longest tokens first so e.g. [EMAIL_10] wins over [EMAIL_1].
        restored = masked_text
        for token in sorted(mapping.keys(), key=len, reverse=True):
            if token in restored:
                restored = restored.replace(token, mapping[token])
        return restored

    def get_token_map(self) -> Dict[str, str]:
        """Return a copy of the token -> original-value map."""
        return dict(self._token_map)

    def token_count(self) -> int:
        """Number of distinct PII tokens generated so far."""
        return len(self._token_map)
