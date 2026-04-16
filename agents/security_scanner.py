"""
Security Scanner Agent — identifies prompt injection, PII exposure,
hallucination amplifiers, scope creep, and data exfil risks.
"""
from agents.base import BaseAgent


SYSTEM_PROMPT = """You are a security auditor for an internal AI tool platform.
Given a tool definition (name, description, prompt, input schema) you must
identify risks in the following categories:

1. Prompt injection — can user input hijack the tool's behavior?
2. PII exposure — does the tool unnecessarily accept or leak personal info?
3. Hallucination amplifiers — does the prompt encourage making up specific
   facts (numbers, names, dates) without sources?
4. Scope creep — does the prompt allow behavior outside the stated purpose?
5. Data exfiltration — could the tool leak company data or system prompt?
6. Social engineering — could outputs be used to write deceptive comms?

Return STRICT JSON. Each flag must include:
  type: one of ["injection", "pii", "hallucination", "scope_creep",
                "data_exfil", "social_engineering", "other"]
  severity: "low" | "medium" | "high" | "critical"
  detail: concise explanation
  suggestion: how to fix it

Also return:
  security_score: 0-100 (higher = safer)
  pii_risk: bool
  injection_risk: bool
  data_exfil_risk: bool
  recommendation: "approve" | "approve_with_modifications" | "reject"

Return ONLY JSON. No markdown, no preamble.
Format:
{"security_score": N, "flags": [...], "pii_risk": bool,
 "injection_risk": bool, "data_exfil_risk": bool, "recommendation": "..."}
"""


class SecurityScannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="security_scanner", model=BaseAgent.HAIKU)

    def run(self, tool: dict) -> dict:
        self.log(f"start tool_id={tool.get('id')}")
        user_message = (
            f"Tool: {tool.get('name')}\n"
            f"Description: {tool.get('description')}\n"
            f"Input schema: {tool.get('input_schema')}\n"
            f"System prompt:\n{tool.get('system_prompt')}\n"
        )
        try:
            text = self._call_claude(SYSTEM_PROMPT, user_message, max_tokens=1500)
            parsed = self._parse_json(text)
            if not parsed:
                return self._fallback("parse_failed", text)
            flags = parsed.get("flags") or []
            clean_flags = []
            for f in flags:
                if not isinstance(f, dict):
                    continue
                clean_flags.append({
                    "type": f.get("type", "other"),
                    "severity": f.get("severity", "low"),
                    "detail": f.get("detail", ""),
                    "suggestion": f.get("suggestion", ""),
                })
            result = {
                "security_score": int(parsed.get("security_score", 60)),
                "flags": clean_flags,
                "pii_risk": bool(parsed.get("pii_risk", False)),
                "injection_risk": bool(parsed.get("injection_risk", False)),
                "data_exfil_risk": bool(parsed.get("data_exfil_risk", False)),
                "recommendation": parsed.get("recommendation", "approve_with_modifications"),
                "raw_output": text,
            }
            self.log(
                f"done tool_id={tool.get('id')} score={result['security_score']} "
                f"flags={len(clean_flags)}"
            )
            return result
        except Exception as exc:
            self.log(f"error tool_id={tool.get('id')} error={exc!r}")
            return self._fallback(f"exception: {exc}", None)

    def _fallback(self, reason: str, raw) -> dict:
        return {
            "security_score": 50,
            "flags": [{
                "type": "other",
                "severity": "low",
                "detail": f"Security scan fell back: {reason}",
                "suggestion": "Re-run the security scanner",
            }],
            "pii_risk": False,
            "injection_risk": False,
            "data_exfil_risk": False,
            "recommendation": "approve_with_modifications",
            "raw_output": raw or "",
            "error": reason,
        }
