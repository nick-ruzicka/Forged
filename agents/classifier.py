"""
Classifier Agent — scores a submitted tool across the Forge governance
dimensions and returns a structured dict.
"""
import json

from agents.base import BaseAgent


SYSTEM_PROMPT = """You are a governance classifier for an internal AI tool platform.
Analyze the submitted tool and return a JSON classification.

You must classify:
1. output_type: "deterministic" | "probabilistic" | "mixed"
   - deterministic: always same output for same input (data lookups, calculations)
   - probabilistic: varies by design (email drafts, summaries, scoring)
   - mixed: deterministic structure, probabilistic content

2. reliability_score: 0-100
   - 90-100 fully deterministic, 70-89 highly reliable, 50-69 mostly reliable,
     30-49 variable, 10-29 highly variable, 0-9 unpredictable

3. safety_score: 0-100
   - 90-100 safe (informational only), 70-89 low risk (human reviews),
     50-69 medium risk, 30-49 high risk, 0-29 critical (triggers actions)

4. data_sensitivity: "public" | "internal" | "confidential" | "pii"

5. complexity_score: 0-100 (higher = simpler to use)
   - 80-100 simple, 60-79 moderate, 40-59 complex, 0-39 expert only

6. detected_category: best-fit short string (e.g. "Account Research",
   "Email Generation", "Contact Scoring", "Data Lookup", "Reporting",
   "Onboarding", "Forecasting", "Other")

Signals to weigh: temperature, presence of structured output constraints,
"send/update/delete/post" verbs in prompt (drop safety), PII field names
(email/phone/ssn/dob/address), number of input fields (raises complexity),
presence of verified data sources (raises reliability).

Return ONLY valid JSON. No preamble, no markdown.

Format:
{"output_type": "...", "reliability_score": N, "safety_score": N,
 "data_sensitivity": "...", "complexity_score": N,
 "detected_category": "...", "reasoning": "...", "confidence": 0.0-1.0}
"""


class ClassifierAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="classifier", model=BaseAgent.HAIKU)

    def run(self, tool: dict) -> dict:
        self.log(f"start tool_id={tool.get('id')}")
        user_message = self._format_tool(tool)
        try:
            text = self._call_claude(SYSTEM_PROMPT, user_message, max_tokens=1000)
            parsed = self._parse_json(text)
            if not parsed:
                return self._fallback("parse_failed", text)
            result = {
                "output_type": parsed.get("output_type", "probabilistic"),
                "reliability_score": int(parsed.get("reliability_score", 50)),
                "safety_score": int(parsed.get("safety_score", 50)),
                "data_sensitivity": parsed.get("data_sensitivity", "internal"),
                "complexity_score": int(parsed.get("complexity_score", 50)),
                "detected_category": parsed.get("detected_category", tool.get("category", "Other")),
                "reasoning": parsed.get("reasoning", ""),
                "confidence": float(parsed.get("confidence", 0.7)),
                "raw_output": text,
            }
            self.log(f"done tool_id={tool.get('id')} type={result['output_type']}")
            return result
        except Exception as exc:
            self.log(f"error tool_id={tool.get('id')} error={exc!r}")
            return self._fallback(f"exception: {exc}", None)

    def _format_tool(self, tool: dict) -> str:
        return (
            f"Tool name: {tool.get('name')}\n"
            f"Tagline: {tool.get('tagline')}\n"
            f"Description: {tool.get('description')}\n"
            f"Category (author-declared): {tool.get('category')}\n"
            f"Tags: {tool.get('tags')}\n"
            f"Model: {tool.get('model')} | Temperature: {tool.get('temperature')} | "
            f"Max tokens: {tool.get('max_tokens')}\n"
            f"Input schema: {tool.get('input_schema')}\n"
            f"System prompt:\n{tool.get('system_prompt')}\n"
        )

    def _fallback(self, reason: str, raw) -> dict:
        return {
            "output_type": "probabilistic",
            "reliability_score": 40,
            "safety_score": 50,
            "data_sensitivity": "internal",
            "complexity_score": 50,
            "detected_category": "Other",
            "reasoning": f"fallback: {reason}",
            "confidence": 0.0,
            "raw_output": raw or "",
            "error": reason,
        }
