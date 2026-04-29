#!/usr/bin/env python3
"""GPT-5.4-mini Vision 反向校验：给生成图打 4 维分数。

接收 (生成图, 产品参考图, slot_spec)，返回：
{
    "scores": {
        "product_consistency": 0-10,    # 与参考图比，产品本体一致吗（权重 0.4）
        "cyrillic_render": 0-10,         # 俄语渲染清晰吗（权重 0.25）
        "visual_hierarchy": 0-10,        # 主标题/角标/副文层级清晰吗（权重 0.2）
        "ctr_risk": 0-10,                # CTR 风险（劣质字体/拥挤/脏色，10=无风险，权重 0.15）
    },
    "weighted": float,                   # 加权总分
    "passed": bool,                      # 加权 ≥ 7.5 且 product_consistency ≥ 8
    "issues": [str],                     # 具体问题（用于注入下一轮 negative hint）
}
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CHAT_API_URL = "https://api.jiekou.ai/openai/chat/completions"
DEFAULT_KEY_FILE = Path.home() / ".config" / "jiekou_api_key"
CRITIC_MODEL = "gpt-5.4-mini"

WEIGHTS = {
    "product_consistency": 0.4,
    "cyrillic_render": 0.25,
    "visual_hierarchy": 0.2,
    "ctr_risk": 0.15,
}
PASS_THRESHOLD = 7.5
HARD_PRODUCT_CONSISTENCY = 8.0
HARD_SLOT_COMPLIANCE = 8.0

# Slots where hands/fingers/human body parts in frame are an automatic violation.
# Per silk-life user hard-requirements (v3_spec/b2_v4_pipeline_gap.md, b3_slot_question_map.yaml):
# only unboxing-scene is allowed to depict a hand interacting with the product.
HANDS_FORBIDDEN_SLOTS = {
    "size-spec",
    "material-macro",
    "product-callouts",
    "steps-123",
    "structure-steps",
    "hero-product",
    "angle-feature",
    "scene-grid",
    "before-after-result",
    "quantity-pack",
    "trust-closure",
}

BASE_SYSTEM_PROMPT = """You are a senior Russian e-commerce art director reviewing AI-generated product listing images for the Ozon marketplace.

You will receive 2 images:
  Image 1: REFERENCE — the actual product photo (the AI was supposed to keep this product's body intact).
  Image 2: GENERATED — what the AI produced.

Score the GENERATED image on 5 dimensions (each 0-10 integer):
  product_consistency: Is the product body in the generated image the SAME product as the reference (same shape, color, material, key features)? Different background/text overlay/composition is fine, but the product itself must match. 10 = identical product. 0 = completely different product.
  cyrillic_render: Is the Russian/Cyrillic text rendered clearly with no missing letters, no Latin substitutions, no garbled characters? 10 = perfect. 0 = unreadable.
  visual_hierarchy: Are the title / number badge / sub-text in clear 3-tier hierarchy? Can a buyer scan and understand the offer in 1 second? 10 = excellent. 0 = chaotic.
  ctr_risk: How likely is this image to FAIL on Ozon CTR (bad fonts, cluttered layout, dirty colors, off-brand)? Score INVERSE: 10 = no risk (looks professional). 0 = will tank.
  slot_compliance: Does the image obey the slot-specific hard rules listed below? Read them carefully. 10 = full obedience. 0 = clear violation. Be strict — borderline cases score ≤6.

List specific issues that the next regeneration should AVOID (1-line each, max 5 issues).

Reply ONLY in valid JSON, no markdown:
{
  "product_consistency": <int>,
  "cyrillic_render": <int>,
  "visual_hierarchy": <int>,
  "ctr_risk": <int>,
  "slot_compliance": <int>,
  "issues": ["issue 1", "issue 2", ...]
}"""


def slot_compliance_addendum(slot_id: str) -> str:
    """Slot-specific hard rules appended to the base system prompt.

    These mirror the per-slot HARD constraints in art_director_contract.py
    (office_craft_slot_generation_requirements) so the critic and the
    generator agree on what counts as a violation.
    """
    rules: List[str] = []
    if slot_id in HANDS_FORBIDDEN_SLOTS:
        rules.append(
            "HANDS GATE: Any visible hand, finger, fingernail, wrist, arm, or other human body "
            "part in this slot is a hard violation. Score slot_compliance ≤4 if even a partial "
            "fingertip is visible."
        )
    if slot_id == "size-spec":
        rules.append(
            "SIZE-SPEC GATE: Background must be clean (white / light grey / subtle ruler or "
            "plain cutting mat only). Lifestyle props, hands, decorative scenes are violations."
        )
    if slot_id in {"material-macro", "material-quality"}:
        rules.append(
            "MATERIAL GATE: A blade macro close-up showing segmented blade edge or metal grain "
            "must dominate the frame. A wide handheld scene with the knife as a small subject "
            "is a violation regardless of how pretty it looks."
        )
    if slot_id in {"product-callouts", "structure-steps"}:
        rules.append(
            "STRUCTURE GATE: The complete product must be visible without occlusion or cropping, "
            "so callout arrows can attach to structural points (slider ribs, blade segments, "
            "end cap, body)."
        )
    if not rules:
        return ""
    bullets = "\n".join(f"  • {r}" for r in rules)
    return f"\n\nSLOT-SPECIFIC HARD RULES for slot='{slot_id}':\n{bullets}"


def load_api_key(key_file: Path = DEFAULT_KEY_FILE) -> str:
    env = os.environ.get("JIEKOU_API_KEY")
    if env:
        return env.strip()
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    raise SystemExit(f"❌ API key 未找到")


def _img_to_data_url(p: Path) -> str:
    raw = p.read_bytes()
    suffix = p.suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix, "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def review(api_key: str, generated_png: Path, reference_img: Path, slot_id: str) -> dict:
    """调 Vision 评分."""
    user_text = (
        f"Slot type: {slot_id}\n\n"
        "Image 1 = REFERENCE product photo. Image 2 = GENERATED listing image. Score per system prompt."
    )

    system_prompt = BASE_SYSTEM_PROMPT + slot_compliance_addendum(slot_id)
    body = {
        "model": CRITIC_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": _img_to_data_url(reference_img)}},
                    {"type": "image_url", "image_url": {"url": _img_to_data_url(generated_png)}},
                ],
            },
        ],
        "max_completion_tokens": 3000,
        "response_format": {"type": "json_object"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False)
        body_path = f.name

    try:
        r = subprocess.run(
            [
                "curl", "-sS", "--http1.1", "--max-time", "180",
                CHAT_API_URL,
                "-H", "Content-Type: application/json",
                "-H", f"Authorization: Bearer {api_key}",
                "--data-binary", f"@{body_path}",
            ],
            capture_output=True, text=True, timeout=200,
        )
    finally:
        try:
            os.unlink(body_path)
        except OSError:
            pass

    if r.returncode != 0:
        raise SystemExit(f"❌ Critic 调用失败: {r.stderr[:300]}")

    try:
        resp = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"❌ Critic 响应解析失败: {r.stdout[:300]}")

    if "choices" not in resp or not resp["choices"]:
        raise SystemExit(f"❌ Critic 无返回: {json.dumps(resp)[:300]}")

    content = resp["choices"][0]["message"]["content"].strip()
    try:
        scored = json.loads(content)
    except json.JSONDecodeError:
        # 兜底：从 markdown code block 抽
        if "```" in content:
            content = content.split("```")[1].lstrip("json").strip()
            scored = json.loads(content)
        else:
            raise SystemExit(f"❌ Critic 输出非 JSON: {content[:300]}")

    scores = {k: int(scored.get(k, 0)) for k in WEIGHTS}
    # slot_compliance is an additional hard gate, not part of the weighted score.
    slot_compliance = int(scored.get("slot_compliance", 10))
    weighted = sum(scores[k] * w for k, w in WEIGHTS.items())
    passed = (
        weighted >= PASS_THRESHOLD
        and scores["product_consistency"] >= HARD_PRODUCT_CONSISTENCY
        and slot_compliance >= HARD_SLOT_COMPLIANCE
    )
    scores["slot_compliance"] = slot_compliance
    return {
        "scores": scores,
        "weighted": round(weighted, 2),
        "passed": passed,
        "issues": scored.get("issues", []),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="GPT-5.4-mini Vision 反向校验")
    p.add_argument("generated_png")
    p.add_argument("reference_img")
    p.add_argument("--slot", default="main")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    api_key = load_api_key()
    result = review(api_key, Path(args.generated_png), Path(args.reference_img), args.slot)

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    print(out)
    sc = result["scores"].get("slot_compliance", 10)
    print(f"\n→ {'✅ PASSED' if result['passed'] else '❌ FAILED'} (weighted={result['weighted']}, pc={result['scores']['product_consistency']}, slot_compliance={sc})")


if __name__ == "__main__":
    main()
