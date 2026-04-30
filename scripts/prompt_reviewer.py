#!/usr/bin/env python3
"""V7 prompt pre-generation reviewer (gpt-5.5 high reasoning).

Workflow:
  raw_prompt → prompt_reviewer (gpt-5.5 high) → improved_prompt → image_gen

Catches issues BEFORE burning image-gen API budget:
  - Length > 800 chars (gpt-image-2 safe-mode trigger)
  - Stacked DO NOT / FORBIDDEN clauses (safe-mode trigger)
  - Vague spec like "no luxury feel" without product fidelity grounding
  - Cross-topic leakage (e.g. size-spec slot describing material)
  - Missing required text-overlay components
  - Russian spelling / declension issues in inline strings
  - Number/unit mismatch with sku_truth

Returns: improved prompt + structured rationale (JSON).

Env overrides:
  PROMPT_REVIEWER_MODEL (default gpt-5.5)
  PROMPT_REVIEWER_REASONING (default high)
  PROMPT_REVIEWER_BASE_URL / PROMPT_REVIEWER_KEY_FILE (default same as image-gen endpoint)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_BASE = "http://193.122.147.249:8317/v1"
DEFAULT_KEY_FILE = Path.home() / ".config" / "gpt_image_api_key"
MODEL = os.environ.get("PROMPT_REVIEWER_MODEL", "gpt-5.5")
REASONING = os.environ.get("PROMPT_REVIEWER_REASONING", "high")
URL = os.environ.get("PROMPT_REVIEWER_BASE_URL", DEFAULT_BASE).rstrip("/") + "/chat/completions"


SYSTEM_PROMPT = """You are a strict prompt engineer reviewing image-generation prompts for a Russian Ozon e-commerce product listing.

Your job: review a candidate prompt that will be sent to gpt-image-2 (image edit mode) and return an IMPROVED version plus structured rationale.

The prompt drives gpt-image-2 to generate one slot of an 8-image product set. The image MUST:
  - Faithfully preserve the product from the reference (no quality upgrade, no shape distortion)
  - Render Russian text on the image with perfect Cyrillic spelling
  - Comply with v7 hard rules (one product per image, slot-specific hands policy, no fake packaging, factual dimensions)
  - Stay within ~800 characters (longer prompts trigger gpt-image-2 "safe mode" — model ignores prompt and just copies the reference)
  - Use ≤2 negative ("DO NOT" / "FORBIDDEN") clauses; prefer positive descriptions

Issues to detect and fix:
  1. LENGTH: prompt over 800 chars → tighten ruthlessly, kill ceremony, keep core scene + text overlay
  2. NEGATION OVERLOAD: more than 2 DO NOT/FORBIDDEN/ABSOLUTELY → rewrite as positive descriptions
  3. CROSS-TOPIC LEAK: slot answers ONE buyer question, do not describe other slots' content
  4. RUSSIAN ISSUES: misspelling, wrong gender/case, missing comma decimals (Russian uses "8,5 см" not "8.5 cm")
  5. PRODUCT INFIDELITY: prompt asks for shape/posture different from reference (e.g. "open scissors" when ref is closed)
  6. MISSING OVERLAYS: slot requires text but prompt doesn't list it; or text overlay rules missing color/position
  7. FACT FABRICATION: prompt invents dimensions / steel grade / use cases not given in sku_truth context
  8. AMBIGUOUS LIGHTING/STYLE: missing "soft studio lighting / clean background" when needed
  9. SAFE-MODE TRIGGERS: stacked CRITICAL/MUST/ABSOLUTELY emphasizers, very long single sentences

Reply ONLY in valid JSON, no markdown:
{
  "improved_prompt": "<the rewritten prompt, ready to send to gpt-image-2>",
  "char_count_before": <int>,
  "char_count_after": <int>,
  "issues_found": ["<issue 1>", "<issue 2>", ...],
  "changes_made": ["<change 1>", "<change 2>", ...],
  "verdict": "approved" | "rewrote" | "rejected",
  "verdict_reason": "<one sentence>"
}

If the prompt is already good (≤800 chars, ≤2 negations, no fact fabrication, valid Russian), set verdict="approved" and return improved_prompt = original verbatim.
If you must rewrite, verdict="rewrote".
If the prompt is fundamentally broken (asks model to violate physics, missing ALL required slot info, etc), verdict="rejected" and improved_prompt should be a corrected version anyway."""


def _load_key() -> str:
    env = os.environ.get("CRITIC_API_KEY") or os.environ.get("GPT_IMAGE_API_KEY") or os.environ.get("PROMPT_REVIEWER_KEY")
    if env:
        return env.strip()
    custom_kf = os.environ.get("PROMPT_REVIEWER_KEY_FILE")
    if custom_kf and Path(custom_kf).exists():
        return Path(custom_kf).read_text(encoding="utf-8").strip()
    if DEFAULT_KEY_FILE.exists():
        return DEFAULT_KEY_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit(f"❌ API key not found (env or {DEFAULT_KEY_FILE})")


def review(raw_prompt: str, slot_id: str = "", sku_truth_summary: str = "") -> dict:
    """Submit raw prompt to gpt-5.5 for pre-generation review.

    Returns dict with improved_prompt + rationale fields.
    """
    user_msg_parts = [f"Slot: {slot_id}" if slot_id else ""]
    if sku_truth_summary:
        user_msg_parts.append(f"\nSKU truth context (verified facts):\n{sku_truth_summary}")
    user_msg_parts.append(f"\nCandidate prompt to review:\n---\n{raw_prompt}\n---")
    user_text = "\n".join(p for p in user_msg_parts if p)

    body = {
        "model": MODEL,
        "reasoning_effort": REASONING,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_completion_tokens": 4000,
        "response_format": {"type": "json_object"},
    }

    api_key = _load_key()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False)
        body_path = f.name

    try:
        r = subprocess.run(
            ["curl", "-sS", "--http1.1", "--max-time", "240",
             URL,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {api_key}",
             "--data-binary", f"@{body_path}"],
            capture_output=True, text=True, timeout=260,
        )
    finally:
        try:
            os.unlink(body_path)
        except OSError:
            pass

    if r.returncode != 0:
        raise SystemExit(f"❌ prompt_reviewer call failed: {r.stderr[:300]}")

    try:
        resp = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"❌ response not JSON: {r.stdout[:300]}")
    if "choices" not in resp or not resp["choices"]:
        raise SystemExit(f"❌ no choices in response: {json.dumps(resp)[:300]}")

    content = resp["choices"][0]["message"]["content"].strip()
    try:
        out = json.loads(content)
    except json.JSONDecodeError:
        if "```" in content:
            content = content.split("```")[1].lstrip("json").strip()
            out = json.loads(content)
        else:
            raise SystemExit(f"❌ reviewer output not JSON: {content[:300]}")

    out["raw_prompt"] = raw_prompt
    out["model"] = MODEL
    out["reasoning_effort"] = REASONING
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Pre-generation prompt reviewer (gpt-5.5 high reasoning)")
    p.add_argument("--prompt", help="Raw prompt text (or use --prompt-file)")
    p.add_argument("--prompt-file", help="Path to file containing the raw prompt")
    p.add_argument("--slot", default="", help="Slot id for context")
    p.add_argument("--sku-truth", default="", help="Inline SKU truth summary text")
    p.add_argument("--sku-truth-file", help="Path to file with SKU truth summary")
    p.add_argument("--out", help="Write JSON result to this path")
    p.add_argument("--print-improved", action="store_true", help="Also print just the improved_prompt to stdout (useful for piping)")
    args = p.parse_args()

    if args.prompt_file:
        raw = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    elif args.prompt:
        raw = args.prompt
    else:
        raise SystemExit("❌ must provide --prompt or --prompt-file")

    sku_truth = ""
    if args.sku_truth_file:
        sku_truth = Path(args.sku_truth_file).read_text(encoding="utf-8")
    elif args.sku_truth:
        sku_truth = args.sku_truth

    result = review(raw, slot_id=args.slot, sku_truth_summary=sku_truth)
    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")

    if args.print_improved:
        print(result.get("improved_prompt", ""))
    else:
        print(output)
        verdict = result.get("verdict", "?")
        cb = result.get("char_count_before", "?")
        ca = result.get("char_count_after", "?")
        sys.stderr.write(f"\n→ verdict={verdict}  chars: {cb} → {ca}  issues={len(result.get('issues_found', []))}  changes={len(result.get('changes_made', []))}\n")


if __name__ == "__main__":
    main()
