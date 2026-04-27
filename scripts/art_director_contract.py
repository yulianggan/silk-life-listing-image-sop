#!/usr/bin/env python3
"""Build an ArtDirectorContract before sending prompts to Codex.

Usage:
  python3 scripts/art_director_contract.py standard_sku.json \
    --slot-plan slot_plan.json \
    --out art_director_contract.json

This script is intentionally deterministic. It gives Claude/Codex a stable
contract shape: buyer question -> design paradigm -> visual plate prompt ->
text overlay plan. It does not call any external API.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

CANVAS = {"w": 1024, "h": 1536}
CONTRACT_VERSION = "2026-04-27-v1"

# Safety gate: these categories should not receive automated marketing image prompts.
RESTRICTED_KEYWORDS = [
    "刀", "刀具", "锋利", "刀刃", "weapon", "knife", "blade", "cutter",
    "оруж", "нож", "лезв", "самообор", "pepper spray", "mace",
    "adult", "sex", "drug", "supplement", "alcohol", "tobacco", "gambling",
    "химикат", "яд", "наркот", "алког", "табак", "азарт",
]

METRIC_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(мм|см|м|мл|л|г|кг|шт|штук|месяц(?:ев|а)?|дней|час(?:а|ов)?|°|w|вт|v|в)\b",
    re.IGNORECASE,
)

DEFAULT_SLOT_IDS = [
    "hero-product",
    "product-callouts",
    "steps-123",
    "scene-grid-4",
    "before-after",
    "material-tech",
    "quantity-pack",
    "trust-badge",
]

SLOT_TO_PARADIGM = {
    # v5 slot_catalog ids
    "hero-product": "hero_spec_badge",
    "scene-grid-4": "scene_grid_4",
    "scene-list-text": "scene_list_text",
    "angle-feature": "one_second_benefit",
    "dimension-spec": "product_callouts",
    "ergo-handhold": "lifestyle_human_scene",
    "material-tech": "material_macro",
    "before-after": "before_after_result",
    "product-callouts": "product_callouts",
    "install-steps": "steps_123",
    "steps-123": "steps_123",
    "structure-steps": "material_macro",
    "lifestyle-female": "lifestyle_human_scene",
    "lifestyle-female-b": "lifestyle_human_scene",
    "audience-fit": "scene_grid_4",
    "trust-badge": "trust_quality",
    "quantity-pack": "pack_quantity",
    "vs-competitor": "problem_solution_split",
    "icon-feature-grid": "one_second_benefit",
    "mechanism-cycle": "mechanism_cycle",
    # legacy 8 slots
    "main": "hero_spec_badge",
    "detail-size": "product_callouts",
    "detail-compare": "problem_solution_split",
    "material": "material_macro",
    "use-scene": "scene_grid_4",
    "hand-demo": "lifestyle_human_scene",
    "package": "pack_quantity",
    "cert-review": "trust_quality",
}

BUYER_QUESTION = {
    "hero_spec_badge": "这是什么，为什么值得点开？",
    "one_second_benefit": "这个商品给我最直接的好处是什么？",
    "product_callouts": "它有哪些真实可见的结构/细节优势？",
    "steps_123": "我会不会用，操作麻烦吗？",
    "scene_grid_4": "它能用在哪些场景？",
    "scene_list_text": "它覆盖哪些对象或场景？",
    "before_after_result": "使用前后差别是否看得见？",
    "material_macro": "材质/做工是否可靠？",
    "pack_quantity": "数量/套装是否划算？",
    "trust_quality": "这个商品是否靠谱、放心？",
    "lifestyle_human_scene": "真实生活里怎么用，尺度是否清楚？",
    "mechanism_cycle": "它的持续/循环工作逻辑是什么？",
    "problem_solution_split": "普通替代品和这个商品差在哪里？",
}

PARADIGM_COMPOSITION = {
    "hero_spec_badge": {
        "focal_object": "product",
        "product_scale": "55-65%",
        "camera_angle": "front or 3/4 product hero angle",
        "text_safe_zones": ["top_title", "side_badge", "bottom_pill"],
        "background_mood": "clean warm commercial studio with green accent shapes",
    },
    "one_second_benefit": {
        "focal_object": "product plus one simple visual metaphor",
        "product_scale": "45-60%",
        "camera_angle": "clear hero angle",
        "text_safe_zones": ["top_title", "bottom_caption"],
        "background_mood": "minimal, bright, optimistic",
    },
    "product_callouts": {
        "focal_object": "product with blank callout label zones",
        "product_scale": "55-65%",
        "camera_angle": "slightly angled to show structure",
        "text_safe_zones": ["top_title", "left_callouts", "right_callouts"],
        "background_mood": "clean infographic product studio",
    },
    "steps_123": {
        "focal_object": "safe hand action with product",
        "product_scale": "visible in every step",
        "camera_angle": "top-down or close 3/4 action angle",
        "text_safe_zones": ["top_title", "step_numbers", "step_captions"],
        "background_mood": "realistic bright usage surface",
    },
    "scene_grid_4": {
        "focal_object": "four use-case cells with consistent product",
        "product_scale": "visible in each cell",
        "camera_angle": "consistent use-case framing",
        "text_safe_zones": ["top_title", "cell_labels"],
        "background_mood": "clean rounded 2x2 grid",
    },
    "scene_list_text": {
        "focal_object": "product plus side list panel",
        "product_scale": "50-60%",
        "camera_angle": "hero product angle",
        "text_safe_zones": ["top_title", "side_list"],
        "background_mood": "minimal commercial layout",
    },
    "before_after_result": {
        "focal_object": "same subject before and after",
        "product_scale": "visible but not blocking result",
        "camera_angle": "matched before/after angle",
        "text_safe_zones": ["top_title", "before_label", "after_label"],
        "background_mood": "clean split comparison",
    },
    "material_macro": {
        "focal_object": "macro detail plus product anchor",
        "product_scale": "large detail crop, small full-product anchor",
        "camera_angle": "macro close-up with soft highlight",
        "text_safe_zones": ["top_title", "small_caption"],
        "background_mood": "premium material photography",
    },
    "pack_quantity": {
        "focal_object": "multiple units arranged neatly",
        "product_scale": "abundant but not chaotic",
        "camera_angle": "front/angled pack arrangement",
        "text_safe_zones": ["large_quantity", "top_title"],
        "background_mood": "clean value-pack composition",
    },
    "trust_quality": {
        "focal_object": "premium product hero",
        "product_scale": "50-60%",
        "camera_angle": "dramatic but clean product angle",
        "text_safe_zones": ["top_trust", "bottom_caption"],
        "background_mood": "simple premium trust statement, no fake seals",
    },
    "lifestyle_human_scene": {
        "focal_object": "person or hand naturally using product",
        "product_scale": "clearly visible, not hidden",
        "camera_angle": "candid lifestyle close-up",
        "text_safe_zones": ["top_title", "corner_badge"],
        "background_mood": "warm real-life scene with clean crop",
    },
    "mechanism_cycle": {
        "focal_object": "cycle infographic and product anchor",
        "product_scale": "25-35%",
        "camera_angle": "flat infographic plus product photo",
        "text_safe_zones": ["top_title", "cycle_labels"],
        "background_mood": "clean mechanism diagram style",
    },
    "problem_solution_split": {
        "focal_object": "left ordinary state vs right improved product state",
        "product_scale": "actual product dominant on right",
        "camera_angle": "matched angle for fair comparison",
        "text_safe_zones": ["top_title", "left_caption", "right_caption", "bullet_panels"],
        "background_mood": "clean split comparison, no competitor brand identifiers",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(data: Any, path: Path | None) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text


def combined_text(sku: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("category", "product_name_ru", "product_subtitle_ru", "title_ru", "search_terms_ru", "product_desc_en"):
        value = sku.get(key)
        if value:
            parts.append(str(value))
    for key in ("features_ru", "benefits_ru", "materials_ru"):
        value = sku.get(key) or []
        if isinstance(value, list):
            parts.extend(map(str, value))
    return " ".join(parts).lower()


def restricted_reason(sku: Dict[str, Any]) -> str | None:
    text = combined_text(sku)
    for kw in RESTRICTED_KEYWORDS:
        if kw.lower() in text:
            return f"restricted product category keyword: {kw}"
    return None


def get_slot_ids(slot_plan: Any | None) -> List[str]:
    if not slot_plan:
        return DEFAULT_SLOT_IDS[:]

    # slot_planner_v5.py output: {"slots": [{"slot_id": ...}]}
    if isinstance(slot_plan, dict) and isinstance(slot_plan.get("slots"), list):
        out = []
        for item in slot_plan["slots"]:
            if isinstance(item, dict):
                sid = item.get("slot_id") or item.get("id")
                if sid:
                    out.append(str(sid))
        return out or DEFAULT_SLOT_IDS[:]

    # legacy plan: [{"slot_id": ...}]
    if isinstance(slot_plan, list):
        out = []
        for item in slot_plan:
            if isinstance(item, dict):
                sid = item.get("slot_id") or item.get("id")
                if sid:
                    out.append(str(sid))
        return out or DEFAULT_SLOT_IDS[:]

    return DEFAULT_SLOT_IDS[:]


def short_text(text: str, max_chars: int = 48) -> str:
    text = re.sub(r"\s+", " ", text or "").strip(" .。,:;；，")
    if len(text) <= max_chars:
        return text
    cut = text.rfind(" ", 0, max_chars)
    return text[: cut if cut > 10 else max_chars].strip(" .。,:;；，")


def product_title(sku: Dict[str, Any]) -> str:
    for key in ("product_name_ru", "title_ru", "product_subtitle_ru", "category"):
        if sku.get(key):
            return str(sku[key]).strip()
    return "ТОВАР ДЛЯ ДОМА"


def first_feature(sku: Dict[str, Any]) -> str:
    for key in ("features_ru", "benefits_ru"):
        items = sku.get(key) or []
        if isinstance(items, list):
            for item in items:
                if str(item).strip():
                    return short_text(str(item), 56)
    return "УДОБНО КАЖДЫЙ ДЕНЬ"


def extract_metric(sku: Dict[str, Any]) -> str:
    text = " ".join(
        [product_title(sku)]
        + [str(x) for x in (sku.get("features_ru") or [])]
        + [str(x) for x in (sku.get("benefits_ru") or [])]
    )
    m = METRIC_RE.search(text)
    if not m:
        return ""
    value = m.group(1).replace(",", ".")
    unit = m.group(2)
    return f"{value} {unit}"


def promise_for_paradigm(sku: Dict[str, Any], paradigm: str) -> str:
    title = product_title(sku).upper()
    title_words = title.split()
    compact_title = " ".join(title_words[:5]) if title_words else "ТОВАР ДЛЯ ДОМА"
    metric = extract_metric(sku)
    feature = first_feature(sku).upper()

    if paradigm == "hero_spec_badge":
        return compact_title
    if paradigm == "pack_quantity" and metric:
        return f"{metric.upper()} В НАБОРЕ"
    if paradigm == "steps_123":
        return "ПРОСТО И УДОБНО"
    if paradigm == "scene_grid_4":
        return "ДЛЯ РАЗНЫХ СЦЕНАРИЕВ"
    if paradigm == "before_after_result":
        return "ВИДИМЫЙ РЕЗУЛЬТАТ"
    if paradigm == "material_macro":
        return "КАЧЕСТВЕННЫЙ МАТЕРИАЛ"
    if paradigm == "trust_quality":
        return "НАДЁЖНОЕ КАЧЕСТВО"
    if paradigm == "problem_solution_split":
        return "ЛУЧШЕ ОБЫЧНОГО"
    if paradigm == "lifestyle_human_scene":
        return "УДОБНО КАЖДЫЙ ДЕНЬ"
    if paradigm == "mechanism_cycle":
        return "ПРИНЦИП РАБОТЫ"
    return short_text(feature, 42) or compact_title


def overlay_plan_for(slot_id: str, paradigm: str, sku: Dict[str, Any]) -> Dict[str, Any]:
    title = promise_for_paradigm(sku, paradigm)
    metric = extract_metric(sku)
    feature = first_feature(sku)

    overlays: List[Dict[str, Any]] = [
        {
            "kind": "title",
            "text": title,
            "box": [0.08, 0.045, 0.84, 0.13],
            "font_size": 58,
            "weight": "bold",
            "align": "center",
            "max_lines": 2,
        }
    ]

    if paradigm in {"hero_spec_badge", "pack_quantity"}:
        badge_text = metric.upper() if metric else short_text(feature, 24).upper()
        overlays.append(
            {
                "kind": "badge",
                "text": badge_text or "ХИТ",
                "box": [0.07, 0.24, 0.24, 0.12],
                "font_size": 34,
                "weight": "bold",
                "align": "center",
                "max_lines": 2,
            }
        )

    if paradigm in {"product_callouts", "scene_list_text", "steps_123", "problem_solution_split"}:
        source = sku.get("features_ru") or sku.get("benefits_ru") or [feature]
        bullets = [short_text(str(x), 38) for x in source[:3] if str(x).strip()]
        overlays.append(
            {
                "kind": "bullets",
                "items": bullets,
                "box": [0.08, 0.73, 0.84, 0.17],
                "font_size": 30,
                "weight": "regular",
                "align": "left",
                "max_lines": 3,
            }
        )

    if paradigm == "before_after_result":
        overlays.extend(
            [
                {"kind": "label", "text": "ДО", "box": [0.10, 0.28, 0.18, 0.06], "font_size": 36, "weight": "bold", "align": "center", "max_lines": 1},
                {"kind": "label", "text": "ПОСЛЕ", "box": [0.10, 0.62, 0.24, 0.06], "font_size": 36, "weight": "bold", "align": "center", "max_lines": 1},
            ]
        )

    if paradigm == "trust_quality":
        overlays.append(
            {
                "kind": "caption",
                "text": "ПРОВЕРЕНО ДЛЯ ЕЖЕДНЕВНОГО ИСПОЛЬЗОВАНИЯ",
                "box": [0.11, 0.82, 0.78, 0.08],
                "font_size": 30,
                "weight": "regular",
                "align": "center",
                "max_lines": 2,
            }
        )

    return {
        "do_not_ask_codex_to_render_final_text": True,
        "canvas": CANVAS,
        "slot_id": slot_id,
        "overlays": overlays,
    }


def palette_intent(sku: Dict[str, Any]) -> str:
    text = combined_text(sku)
    if any(k in text for k in ["металл", "metal", "chrome", "сталь", "steel"]):
        return "clean technical premium, restrained contrast, green accent badge"
    if any(k in text for k in ["уход", "крас", "beauty", "care"]):
        return "soft clean minimal, warm cream or blush, gentle green accents"
    if any(k in text for k in ["запах", "fresh", "clean", "fridge", "холод"]):
        return "fresh clean home mood, mint green and warm white, airy background"
    return "warm clean Silk Life commercial style with green accent shapes"


def build_codex_prompt(
    sku: Dict[str, Any],
    slot_id: str,
    paradigm: str,
    composition: Dict[str, Any],
    buyer_question: str,
) -> str:
    keep = ", ".join(default_product_lock(sku)["must_keep"])
    zones = ", ".join(composition.get("text_safe_zones", []))
    visual_answer = visual_answer_for(paradigm)
    return (
        "Create a photorealistic e-commerce visual plate for a Russian Ozon product listing.\n"
        "Canvas: vertical 3:4, 1024x1536px.\n\n"
        "REFERENCE LOCK:\n"
        f"Use the supplied product reference as the source of truth. Keep exactly: {keep}. "
        "Do not add extra accessories, do not change the product into a different item, and keep the product fully visible.\n\n"
        f"SLOT: {slot_id}\n"
        f"DESIGN PARADIGM: {paradigm}\n"
        f"BUYER QUESTION: {buyer_question}\n"
        f"VISUAL ANSWER: {visual_answer}\n\n"
        "COMPOSITION:\n"
        f"Focal object: {composition.get('focal_object')}. Product scale: {composition.get('product_scale')}. "
        f"Camera angle: {composition.get('camera_angle')}. Background mood: {composition.get('background_mood')}.\n\n"
        "TEXT SAFE ZONES:\n"
        f"Reserve clean blank areas for later text overlay at: {zones}. Use blank rounded panels, badge shapes, or subtle empty areas only. "
        "Do NOT render readable Cyrillic or Latin text. Do NOT render fake logos, fake certification seals, or fake review stars.\n\n"
        "STYLE:\n"
        "Silk Life listing style: clean commercial product photography, clear hierarchy, soft but high-contrast lighting, green accent badge shapes, generous negative space, professional Ozon thumbnail readability. "
        f"Palette intent: {palette_intent(sku)}.\n\n"
        "AVOID:\n"
        f"{negative_prompt_for(paradigm)}"
    )


def visual_answer_for(paradigm: str) -> str:
    return {
        "hero_spec_badge": "A large truthful product hero plus one strong blank badge area for the core metric/benefit.",
        "one_second_benefit": "A simple visual metaphor that makes the main benefit obvious without clutter.",
        "product_callouts": "The product remains centered with clean blank callout zones around real visible details.",
        "steps_123": "Three clear usage moments with hands/action visible and simple blank caption zones.",
        "scene_grid_4": "Four clean usage cells showing where the product fits, with consistent product identity.",
        "scene_list_text": "A strong product hero plus a clean side panel reserved for scenario bullets.",
        "before_after_result": "A matched before/after split showing the result logic clearly and honestly.",
        "material_macro": "A premium macro/detail view that makes material and build quality feel tangible.",
        "pack_quantity": "Neatly arranged multiple units with a large blank quantity badge zone.",
        "trust_quality": "A quiet premium product statement with no fake seals or unsupported certification marks.",
        "lifestyle_human_scene": "A realistic human/hand scene where the product action and scale are easy to understand.",
        "mechanism_cycle": "A simple cycle diagram structure with the real product as an anchor.",
        "problem_solution_split": "A fair split layout showing ordinary/problem state versus the actual product advantage.",
    }.get(paradigm, "A clean product-focused visual answer with strong hierarchy.")


def negative_prompt_for(paradigm: str) -> str:
    base = [
        "unreadable text",
        "random Cyrillic letters",
        "fake logos",
        "fake certification seals",
        "unsupported awards or review stars",
        "extra product parts",
        "wrong material or color",
        "distorted hands",
        "cluttered collage",
        "tiny paragraphs",
        "dirty colors",
        "low-budget poster look",
        "cropped or hidden product",
        "inconsistent product scale",
    ]
    if paradigm == "scene_grid_4":
        base.append("product looking different across grid cells")
    if paradigm == "before_after_result":
        base.append("different subject angle between before and after")
    if paradigm == "pack_quantity":
        base.append("inventing a larger pack count than provided")
    if paradigm == "trust_quality":
        base.append("official certification marks unless provided by user")
    return "; ".join(base) + "."


def default_product_lock(sku: Dict[str, Any]) -> Dict[str, Any]:
    desc = sku.get("product_desc_en") or "the exact product shown in the reference image"
    title = product_title(sku)
    return {
        "must_keep": [
            "same product silhouette",
            "same color and material",
            "same quantity/count as reference or SKU",
            "same visible structure and proportions",
            f"product identity described as: {short_text(str(desc), 120)}",
        ],
        "must_not_invent": [
            "extra accessories or variants",
            "unsupported certifications, awards, or review stars",
            "brand logos not present in the input",
            "claims not supported by SKU benefits",
            "different product type",
        ],
        "reference_priority": [
            "main/body product reference image",
            "structure/detail reference image",
            "usage/scene reference image",
            f"SKU title: {title}",
        ],
    }


def build_slot_contract(sku: Dict[str, Any], slot_id: str) -> Dict[str, Any]:
    paradigm = SLOT_TO_PARADIGM.get(slot_id, "one_second_benefit")
    buyer_question = BUYER_QUESTION.get(paradigm, "买家为什么要相信这张图？")
    composition = PARADIGM_COMPOSITION.get(paradigm, PARADIGM_COMPOSITION["one_second_benefit"])
    return {
        "slot_id": slot_id,
        "buyer_question": buyer_question,
        "design_paradigm": paradigm,
        "one_sentence_promise_ru": promise_for_paradigm(sku, paradigm),
        "visual_answer": visual_answer_for(paradigm),
        "composition": composition,
        "codex_plate_prompt": build_codex_prompt(sku, slot_id, paradigm, composition, buyer_question),
        "negative_prompt": negative_prompt_for(paradigm),
        "text_overlay_plan": overlay_plan_for(slot_id, paradigm, sku),
        "critic_checklist": [
            "Product is the same as reference: shape, color, material, count, key structure.",
            "The image answers the buyer_question in one second.",
            "All final Russian text comes from overlay_text.py, not image generation.",
            "Title/badge/bullets are readable at thumbnail size.",
            "No fake certification, fake logo, fake review, or unsupported claim.",
            "Composition uses one clear focal idea, not a cluttered collage.",
        ],
    }


def build_contract(sku: Dict[str, Any], slot_plan: Any | None) -> Dict[str, Any]:
    blocked = restricted_reason(sku)
    category = str(sku.get("category") or sku.get("category_kind") or "")

    contract: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "status": "needs_human_review" if blocked else "ok",
        "category": category,
        "product_identity_lock": default_product_lock(sku),
        "buyer_read": {
            "core_buyer_question": "买家第一眼是否能确认商品、用途和核心好处？",
            "core_selling_axis": infer_core_axis(sku),
            "one_sentence_strategy": "每张图只回答一个买家问题；Codex 生成无文字视觉底图，最终俄文由脚本叠加。",
        },
        "designer_delta": {
            "available": False,
            "pair_observations": [],
            "note": "If paired communication/artist images are available, run prompts/art_director_system.md to fill reusable pattern_bank.",
        },
        "style_memory": {
            "brand_tokens": [
                "Russian bold title rendered by overlay script",
                "green badge or pill accent",
                "clean product-centered composition",
                "warm commercial photography",
                "generous negative space",
                "real hand/lifestyle scene only when it clarifies scale or usage",
            ],
            "palette_intent": palette_intent(sku),
            "pattern_bank": [
                {
                    "pattern": "One image, one buyer question, one visual answer",
                    "when_to_use": "all slots",
                    "visual_move": "choose one focal product/comparison/step/scene and remove weak duplicate details",
                    "avoid": "trying to show every Excel benefit in one image",
                },
                {
                    "pattern": "Text is overlay, not generated pixels",
                    "when_to_use": "all slots with Russian copy",
                    "visual_move": "Codex creates blank title/badge zones; overlay_text.py renders exact Cyrillic",
                    "avoid": "asking image model to render long Cyrillic paragraphs",
                },
                {
                    "pattern": "Green badge carries the strongest metric",
                    "when_to_use": "duration, quantity, dimension, or simple high-value claim exists",
                    "visual_move": "put one metric in a round/pill badge near product but not covering it",
                    "avoid": "multiple competing badges",
                },
            ],
        },
        "slot_contracts": [],
    }

    if blocked:
        contract["blocked_reason"] = blocked
        return contract

    slot_ids = get_slot_ids(slot_plan)
    contract["slot_contracts"] = [build_slot_contract(sku, sid) for sid in slot_ids]
    return contract


def infer_core_axis(sku: Dict[str, Any]) -> str:
    text = combined_text(sku)
    if METRIC_RE.search(text):
        return "metric_or_quantity"
    if any(k in text for k in ["удоб", "прост", "легк", "быстр"]):
        return "convenience"
    if any(k in text for k in ["прочн", "надёж", "износ", "quality", "durable"]):
        return "durability_or_quality"
    if any(k in text for k in ["запах", "эффект", "результ", "clean", "fresh"]):
        return "effect_or_freshness"
    return "clear_daily_use"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Silk Life ArtDirectorContract JSON")
    parser.add_argument("standard_sku_json", type=Path)
    parser.add_argument("--slot-plan", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    sku = load_json(args.standard_sku_json)
    slot_plan = load_json(args.slot_plan) if args.slot_plan and args.slot_plan.exists() else None
    contract = build_contract(sku, slot_plan)
    print(dump_json(contract, args.out))


if __name__ == "__main__":
    main()
