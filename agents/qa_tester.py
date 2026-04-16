"""
QA Tester Agent — generates 3 test cases (normal/edge/minimal) from a tool's
input_schema, runs them against the hardened prompt via Claude, then has a
stronger model evaluate each output.
"""
import json

from agents.base import BaseAgent


TEST_GEN_SYSTEM = """You are a QA engineer generating synthetic test cases
for an internal AI tool. Given a tool description and input_schema, produce
THREE test cases:

1. Typical — realistic everyday inputs
2. Edge — unusual but valid inputs (long strings, unusual characters, edge values)
3. Minimal — only required fields, everything else omitted

Return STRICT JSON:
{"test_cases": [
   {"label": "typical", "inputs": {<field>: <value>, ...}},
   {"label": "edge", "inputs": {...}},
   {"label": "minimal", "inputs": {...}}
]}
No markdown. No preamble.
"""


EVAL_SYSTEM = """You are an AI quality evaluator. You will be given:
- A tool's description and purpose
- The exact input that was used
- The raw output the tool produced

Evaluate the output across four dimensions and return STRICT JSON:
{"format_correct": bool,
 "scope_maintained": bool,
 "hallucination_detected": bool,
 "useful": bool,
 "score": 0-5 (float, overall quality),
 "notes": "<one sentence>"}

Be strict but fair. A hallucination means the output asserted specific
facts (numbers, names, dates) that could not be derived from the input.
"""


class QATesterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="qa_tester", model=BaseAgent.HAIKU)
        self._runner = BaseAgent(name="qa_runner", model=BaseAgent.HAIKU)
        self._evaluator = BaseAgent(name="qa_evaluator", model=BaseAgent.SONNET)

    def run(self, tool: dict, hardened_prompt: str = None) -> dict:
        self.log(f"start tool_id={tool.get('id')}")
        hardened_prompt = hardened_prompt or tool.get("hardened_prompt") or tool.get("system_prompt") or ""

        cases = self._generate_test_cases(tool)
        if not cases:
            return self._fallback("no test cases")

        results = []
        scores = []
        issues = []
        passes = 0
        for case in cases:
            try:
                rendered = self._render(hardened_prompt, case["inputs"])
                output = self._runner._call_claude(
                    hardened_prompt,
                    json.dumps(case["inputs"]),
                    max_tokens=int(tool.get("max_tokens") or 1000),
                )
                evaluation = self._evaluate(tool, case["inputs"], output)
                results.append({
                    "label": case.get("label"),
                    "inputs": case["inputs"],
                    "rendered_prompt": rendered,
                    "output": output,
                    "evaluation": evaluation,
                })
                score = float(evaluation.get("score", 0.0))
                scores.append(score)
                if evaluation.get("format_correct") and evaluation.get("scope_maintained") \
                        and not evaluation.get("hallucination_detected") \
                        and evaluation.get("useful") and score >= 3.0:
                    passes += 1
                else:
                    note = evaluation.get("notes") or "issue detected"
                    issues.append(f"{case.get('label')}: {note}")
            except Exception as exc:
                self.log(f"test case {case.get('label')} error: {exc!r}")
                results.append({
                    "label": case.get("label"),
                    "inputs": case["inputs"],
                    "output": "",
                    "evaluation": {
                        "format_correct": False,
                        "scope_maintained": False,
                        "hallucination_detected": False,
                        "useful": False,
                        "score": 0.0,
                        "notes": f"exception: {exc}",
                    },
                })
                issues.append(f"{case.get('label')}: exception {exc}")

        total = max(1, len(results))
        pass_rate = passes / total
        avg_score = sum(scores) / len(scores) if scores else 0.0
        recommendation = "approve" if pass_rate >= 0.8 and avg_score >= 3.5 else (
            "approve_with_modifications" if pass_rate >= 0.5 else "reject"
        )

        result = {
            "test_cases": results,
            "qa_pass_rate": round(pass_rate, 3),
            "avg_score": round(avg_score, 2),
            "issues": issues,
            "recommendation": recommendation,
        }
        self.log(
            f"done tool_id={tool.get('id')} pass_rate={pass_rate:.2f} "
            f"avg_score={avg_score:.2f}"
        )
        return result

    def _generate_test_cases(self, tool):
        user_message = (
            f"Tool: {tool.get('name')}\n"
            f"Description: {tool.get('description')}\n"
            f"Input schema (JSON): {tool.get('input_schema')}\n"
        )
        try:
            text = self._call_claude(TEST_GEN_SYSTEM, user_message, max_tokens=1200)
            parsed = self._parse_json(text)
            if not parsed:
                return []
            cases = parsed.get("test_cases") or []
            clean = []
            for c in cases:
                if isinstance(c, dict) and isinstance(c.get("inputs"), dict):
                    clean.append({
                        "label": c.get("label", "case"),
                        "inputs": c["inputs"],
                    })
            return clean[:3]
        except Exception as exc:
            self.log(f"generate cases error: {exc!r}")
            return []

    def _render(self, prompt: str, inputs: dict) -> str:
        rendered = prompt or ""
        for k, v in inputs.items():
            rendered = rendered.replace("{{" + str(k) + "}}", str(v))
        return rendered

    def _evaluate(self, tool, inputs, output) -> dict:
        user_message = (
            f"Tool purpose: {tool.get('description')}\n"
            f"Inputs: {json.dumps(inputs)}\n"
            f"Output:\n{output}\n"
        )
        try:
            text = self._evaluator._call_claude(EVAL_SYSTEM, user_message, max_tokens=600)
            parsed = self._evaluator._parse_json(text)
            if not parsed:
                return self._default_eval()
            return {
                "format_correct": bool(parsed.get("format_correct", False)),
                "scope_maintained": bool(parsed.get("scope_maintained", False)),
                "hallucination_detected": bool(parsed.get("hallucination_detected", False)),
                "useful": bool(parsed.get("useful", False)),
                "score": float(parsed.get("score", 0.0)),
                "notes": parsed.get("notes", ""),
            }
        except Exception as exc:
            self.log(f"evaluate error: {exc!r}")
            return self._default_eval()

    def _default_eval(self):
        return {
            "format_correct": False,
            "scope_maintained": False,
            "hallucination_detected": False,
            "useful": False,
            "score": 0.0,
            "notes": "evaluation failed",
        }

    def _fallback(self, reason: str) -> dict:
        return {
            "test_cases": [],
            "qa_pass_rate": 0.0,
            "avg_score": 0.0,
            "issues": [reason],
            "recommendation": "reject",
            "error": reason,
        }
