"""
QA Tester agent — invocation precision + output consistency.

The most complex agent. Three parallel workstreams:
1. Invocation precision: 4 batches of 5 test prompts
2. Output consistency: 5 identical prompts + 1 judge call
3. Adversarial variant generation: 1 call (stored for async sweep)

Uses ThreadPoolExecutor(max_workers=8) for internal parallelism.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base import SONNET, get_client, parse_json_response, timed
from api import db

PRECISION_PROMPT = """You are evaluating whether a Claude Code skill would be correctly invoked for each prompt.

Skill description: {skill_desc}

For each prompt below, judge: would this skill be the RIGHT one to invoke?

Respond with ONLY valid JSON:
{{
  "results": [
    {{"prompt": "...", "should_trigger": true/false, "would_trigger": true/false}}
  ],
  "precision": 0.0-1.0,
  "false_fire_rate": 0.0-1.0
}}"""

CONSISTENCY_JUDGE_PROMPT = """You are judging output consistency for a Claude Code skill.

Compare these outputs generated from the SAME prompt. Score each pair:
5 = semantically equivalent (same content, structure, conclusions)
4 = different phrasing/ordering but same conclusions
3 = minor detail differences
2 = significant detail differences
1 = contradictory

Respond with ONLY valid JSON:
{
  "pairs": [{"output_a": 0, "output_b": 1, "score": 5}],
  "avg_score": 0.0,
  "pct_above_4": 0.0
}"""

VARIANT_GEN_PROMPT = """Generate 10 adversarial test prompts for this skill.

Skill description: {skill_desc}

Create prompts that are:
- Edge cases (boundary between should/shouldn't trigger)
- Ambiguous (could go either way)
- Tricky (seem like they should trigger but shouldn't, or vice versa)

Respond with ONLY valid JSON:
{
  "variants": ["prompt1", "prompt2", ...]
}"""


def _run_precision_batch(skill_desc: str, prompts: list, batch_idx: int) -> dict:
    """Evaluate one batch of test prompts for invocation precision."""
    client = get_client()
    prompt_list = "\n".join(f"{i+1}. [{p['kind']}] {p['prompt']}" for i, p in enumerate(prompts))
    user_msg = f"Test prompts (batch {batch_idx + 1}):\n\n{prompt_list}"

    resp = client.messages.create(
        model=SONNET,
        max_tokens=1000,
        messages=[{"role": "user", "content": user_msg}],
        system=PRECISION_PROMPT.format(skill_desc=skill_desc),
    )
    return parse_json_response(resp.content[0].text)


def _run_consistency_output(skill_text: str, prompt: str, run_idx: int) -> str:
    """Generate one output for consistency testing."""
    client = get_client()
    resp = client.messages.create(
        model=SONNET,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
        system=f"You are following this skill:\n\n{skill_text}",
    )
    return resp.content[0].text


@timed("qa_tester")
def run(skill_id: int, review_id: int, *, skill_text: str) -> dict:
    client = get_client()

    # Load test cases
    test_cases = db.get_skill_test_cases(skill_id)
    if not test_cases:
        # Generate from description if author didn't supply
        resp = client.messages.create(
            model=SONNET,
            max_tokens=2000,
            messages=[{"role": "user", "content": f"Skill text:\n\n{skill_text}"}],
            system="Generate 10 prompts that should trigger this skill and 10 that should not. Respond with JSON: {\"positive\": [...], \"negative\": [...]}",
        )
        generated = parse_json_response(resp.content[0].text)
        test_cases = (
            [{"kind": "positive", "prompt": p} for p in generated.get("positive", [])] +
            [{"kind": "negative", "prompt": p} for p in generated.get("negative", [])]
        )

    skill_desc = skill_text[:500]

    with ThreadPoolExecutor(max_workers=8) as executor:
        # Workstream 1: Invocation precision (4 batches of 5)
        batches = [test_cases[i:i+5] for i in range(0, min(len(test_cases), 20), 5)]
        precision_futures = [
            executor.submit(_run_precision_batch, skill_desc, batch, idx)
            for idx, batch in enumerate(batches)
        ]

        # Workstream 2: Output consistency (5 parallel output generations)
        consistency_prompt = next(
            (tc["prompt"] for tc in test_cases if tc["kind"] == "positive"),
            "Help me with this task",
        )
        consistency_futures = [
            executor.submit(_run_consistency_output, skill_text, consistency_prompt, i)
            for i in range(5)
        ]

        # Workstream 3: Adversarial variant generation
        variant_future = executor.submit(
            lambda: parse_json_response(client.messages.create(
                model=SONNET,
                max_tokens=1500,
                messages=[{"role": "user", "content": f"Skill text:\n\n{skill_text}"}],
                system=VARIANT_GEN_PROMPT.format(skill_desc=skill_desc),
            ).content[0].text)
        )

        # Collect precision results
        precision_results = []
        for f in precision_futures:
            try:
                precision_results.append(f.result(timeout=120))
            except Exception as e:
                precision_results.append({"error": str(e), "precision": 0.5})

        # Collect consistency outputs
        consistency_outputs = []
        for f in consistency_futures:
            try:
                consistency_outputs.append(f.result(timeout=60))
            except Exception as e:
                consistency_outputs.append(f"[error: {e}]")

        # Collect variants
        try:
            variants = variant_future.result(timeout=60)
        except Exception:
            variants = {"variants": []}

    # Judge consistency
    if len(consistency_outputs) >= 2:
        outputs_text = "\n\n---\n\n".join(
            f"Output {i+1}:\n{o}" for i, o in enumerate(consistency_outputs)
        )
        judge_resp = client.messages.create(
            model=SONNET,
            max_tokens=1000,
            messages=[{"role": "user", "content": f"Outputs to compare:\n\n{outputs_text}"}],
            system=CONSISTENCY_JUDGE_PROMPT,
        )
        consistency_result = parse_json_response(judge_resp.content[0].text)
    else:
        consistency_result = {"avg_score": 0, "pct_above_4": 0}

    # Aggregate
    avg_precision = sum(
        r.get("precision", 0.5) for r in precision_results
    ) / max(len(precision_results), 1)
    avg_false_fire = sum(
        r.get("false_fire_rate", 0.5) for r in precision_results
    ) / max(len(precision_results), 1)
    consistency_pct = consistency_result.get("pct_above_4", 0)

    qa_pass_rate = (avg_precision + consistency_pct) / 2

    qa_issues = []
    if avg_precision < 0.7:
        qa_issues.append({"metric": "invocation_precision", "observed": avg_precision})
    if avg_false_fire > 0.3:
        qa_issues.append({"metric": "false_fire_rate", "observed": avg_false_fire})
    if consistency_pct < 0.6:
        qa_issues.append({"metric": "output_consistency", "observed": consistency_pct})

    result = {
        "invocation_precision": avg_precision,
        "false_fire_rate": avg_false_fire,
        "output_consistency": consistency_pct,
        "consistency_avg_score": consistency_result.get("avg_score", 0),
        "precision": avg_precision,
        "consistency": consistency_pct,
        "qa_pass_rate": qa_pass_rate,
        "qa_issues": qa_issues,
        "adversarial_variants": variants.get("variants", []),
    }

    db.update_agent_review(review_id,
        qa_output=json.dumps(result),
        test_cases=json.dumps([{"kind": tc["kind"], "prompt": tc["prompt"]} for tc in test_cases[:20]]),
        qa_pass_rate=qa_pass_rate,
        qa_issues=json.dumps(qa_issues),
    )
    return result
