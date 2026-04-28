#!/usr/bin/env python3
"""Build ArtDirectorContract for Silk Life Russian ecommerce listing images.

v3 adds reference-locked generation:
  SKU facts + communication reference_manifest -> category archetype -> design slots
  -> Codex no-text plate prompts with reference_images
  -> overlay_text.py owns all text cards and final Russian text.

The image model must not guess the SKU from text. It must use selected product
reference images as the immutable product anchor.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

CONTRACT_VERSION = "2026-04-28-v3-reference-lock-no-category-gate"
DEFAULT_CANVAS = {
    "ratio": "3:4",
    "preferred": "1200x1600",
    "fit": "full_bleed_cover",
    "no_side_margins": True,
}

METRIC_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(мм|см|м|мл|л|г|кг|шт|штук|дней|дня|месяц(?:ев|а)?|час(?:а|ов)?|°)\b",
    re.IGNORECASE,
)
# Dimensions are extracted from METRIC_RE with local context windows.
# Do not use a greedy context regex because adjacent values such as
# "9 мм / лезвие, 130 мм / длина, 13 мм / ширина" must remain separate.

# Category gating is intentionally disabled for this internal ecommerce image workflow.
# The pipeline focuses on SKU truth, reference locking, copy correctness, and layout quality.

ARCHETYPES = {
    "yellow_deodorant_sticker": {
        "keywords": ["стикер", "эколог", "обув", "запах", "дезодо", "odor", "deodor", "鞋垫贴纸", "除味", "柠檬", "消臭"],
        "palette": "sunny yellow / lemon green / clean white",
        "visual_mood": "fresh, natural, deodorizing, clean",
        "must_preserve": ["yellow sticker shape", "package color and pack count", "actual adhesive patch geometry"],
        "sequence": ["hero-product", "natural-composition", "size-spec", "steps-123", "mechanism-ingredients", "shoe-fit-grid", "quantity-pack", "duration-effect"],
    },
    "transparent_heel_gel": {
        "keywords": ["вкладыш", "пят", "heel", "gel", "силикон", "后跟", "鞋跟", "硅胶", "防磨脚"],
        "palette": "white / warm grey / muted green",
        "visual_mood": "clean, protective, comfort care",
        "must_preserve": ["transparent gel material", "curved heel-pad silhouette", "raised dot texture", "pair/count"],
        "sequence": ["hero-product", "heel-protection", "size-spec", "steps-123", "reusable-waterproof", "comfort-material", "before-after-result", "shoe-fit-grid"],
    },
    "warm_needle_set": {
        "keywords": ["игл", "швей", "нит", "needle", "thread", "sewing", "针", "穿线", "缝纫", "木盒"],
        "palette": "cream / wood / gold / soft brown",
        "visual_mood": "warm craft, convenient, home sewing",
        "must_preserve": ["wooden case", "gold needle head", "needle count", "needle lengths and self-threading eye"],
        "sequence": ["hero-product", "size-spec", "comfort-benefit", "easy-threading", "storage-travel", "quantity-pack", "material-macro", "lifestyle-human-scene"],
    },
    "beauty_manicure_scissors": {
        "keywords": ["маникюр", "ножниц", "scissors", "кутикул", "nail", "美甲剪", "指甲剪", "修眉"],
        "palette": "pastel pink / pastel blue / clean white / soft grey",
        "visual_mood": "delicate beauty, salon result, controlled precision",
        "must_preserve": ["metal body shape", "ring handle geometry", "screw position", "tip shape"],
        "sequence": ["hero-product", "task-cards", "size-spec", "beauty-result", "before-after-result", "material-macro", "application-grid", "product-callouts"],
    },
    "auto_industrial_part": {
        "keywords": ["шина", "насос", "компрессор", "ниппель", "tire", "tyre", "air chuck", "adapter", "авто", "轮胎", "充气", "接头", "气嘴"],
        "palette": "dark steel / black / orange industrial accent / white spec page",
        "visual_mood": "durable, industrial, airtight, reliable",
        "must_preserve": ["brass/gold body", "silver clip", "thread opening", "connector geometry"],
        "sequence": ["hero-product", "compatibility", "airtight-seal", "size-spec", "material-quality", "steps-123", "fit-grid", "trust-closure"],
    },
    "office_craft_cutting_tool": {
        "keywords": ["канцеляр", "канцелярский нож", "лезв", "cutter", "utility knife", "craft knife", "office knife", "美工刀", "裁纸刀", "切割", "刀片", "刀刃"],
        "palette": "dark graphite / black / red or green technical accent / light spec page",
        "visual_mood": "precise, compact, office craft, technical",
        "must_preserve": ["long narrow black handle", "segmented steel blade", "slider ribs", "end cap notch", "9mm blade width", "130mm body length", "13mm body width"],
        "sequence": ["hero-product", "material-macro", "product-callouts", "quantity-pack", "scene-grid", "size-spec", "steps-123", "trust-closure"],
    },
    "generic_household": {
        "keywords": [],
        "palette": "clean white / category accent color / soft commercial gradient",
        "visual_mood": "clean, useful, trustworthy",
        "must_preserve": ["product shape", "product color", "package", "count and size facts"],
        "sequence": ["hero-product", "size-spec", "product-callouts", "steps-123", "scene-grid", "material-macro", "quantity-pack", "trust-closure"],
    },
}

SLOT_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "hero-product": {
        "paradigm": "hero_spec_badge",
        "buyer_question": "第一眼这是什么，核心规格/数量是什么？",
        "commercial_intent": "提升首图点击并确认商品身份。",
        "visual_answer": "真实产品或包装大图 + 类目色背景 + 一个数字/规格角标。",
        "title": None,
        "badge": None,
    },
    "natural-composition": {
        "paradigm": "material_macro",
        "buyer_question": "成分/来源是否让人安心？",
        "commercial_intent": "用天然氛围增强信任。",
        "visual_answer": "产品 + 柠檬/精油/植物/干净光感等成分视觉证据。",
        "title": "ЭКОЛОГИЧНЫЙ СОСТАВ",
    },
    "heel-protection": {
        "paradigm": "product_callouts",
        "buyer_question": "它能保护哪里，解决什么不适？",
        "commercial_intent": "把脚后跟保护卖点变成直观看点。",
        "visual_answer": "产品组合 + 脚后跟局部圆形图 + 简短保护标题。",
        "title": "ЗАЩИТА ВАШИХ ПЯТОК",
    },
    "size-spec": {
        "paradigm": "size_spec",
        "buyer_question": "尺寸是否合适？",
        "commercial_intent": "降低因尺寸不确定导致的犹豫。",
        "visual_answer": "浅底产品居中，2-4 个由 overlay 绘制的尺寸箭头/数字卡片。",
        "title": "ОПТИМАЛЬНЫЙ РАЗМЕР",
    },
    "steps-123": {
        "paradigm": "steps_123",
        "buyer_question": "怎么使用，是否简单？",
        "commercial_intent": "降低使用门槛。",
        "visual_answer": "三步真实动作卡片，每步一个动作。",
        "title": "ПРОСТОЕ ИСПОЛЬЗОВАНИЕ",
    },
    "mechanism-ingredients": {
        "paradigm": "material_macro",
        "buyer_question": "它为什么有效？",
        "commercial_intent": "用成分机制建立合理性。",
        "visual_answer": "产品 + 2-3 个成分/吸附元素，用轻量箭头连接。",
        "title": "НАТУРАЛЬНЫЙ СОСТАВ",
    },
    "shoe-fit-grid": {
        "paradigm": "scene_grid",
        "buyer_question": "适合哪些鞋/对象？",
        "commercial_intent": "扩大适配感。",
        "visual_answer": "多鞋型/多对象卡片网格，每格短标签。",
        "title": "ПОДХОДИТ ДЛЯ РАЗНОЙ ОБУВИ",
    },
    "quantity-pack": {
        "paradigm": "quantity_pack",
        "buyer_question": "一套有多少，值不值？",
        "commercial_intent": "突出数量和包装。",
        "visual_answer": "包装 + 多件铺陈 + 大数字角标。",
        "title": "В НАБОРЕ",
    },
    "duration-effect": {
        "paradigm": "before_after_result",
        "buyer_question": "效果能持续多久/适合哪里？",
        "commercial_intent": "温和展示效果，不夸大。",
        "visual_answer": "产品 + 应用对象/效果卡片 + 时长角标。",
        "title": "ЭФФЕКТ ДО 7 ДНЕЙ",
    },
    "reusable-waterproof": {
        "paradigm": "material_macro",
        "buyer_question": "能不能重复使用/清洗？",
        "commercial_intent": "突出耐用和实惠。",
        "visual_answer": "产品在水面/清洗场景中的材质证明。",
        "title": "МНОГОРАЗОВОЕ ИСПОЛЬЗОВАНИЕ",
    },
    "comfort-material": {
        "paradigm": "product_callouts",
        "buyer_question": "材质是否舒适、隐形、不滑？",
        "commercial_intent": "强化佩戴舒适感。",
        "visual_answer": "产品大特写 + 3-4 个短勾选标签。",
        "title": "КОМФОРТНЫЙ МАТЕРИАЛ",
    },
    "before-after-result": {
        "paradigm": "before_after_result",
        "buyer_question": "使用前后有什么改善？",
        "commercial_intent": "用对比建立效果感。",
        "visual_answer": "同角度前后对比卡片。",
        "title": "ДО И ПОСЛЕ",
    },
    "comfort-benefit": {
        "paradigm": "product_callouts",
        "buyer_question": "使用时是否舒适方便？",
        "commercial_intent": "解决使用焦虑。",
        "visual_answer": "手持产品 + 2-3 个短利益卡片。",
        "title": "КОМФОРТНОЕ И УДОБНОЕ",
    },
    "easy-threading": {
        "paradigm": "material_macro",
        "buyer_question": "穿线是否容易？",
        "commercial_intent": "直击核心痛点。",
        "visual_answer": "针眼微距 + 穿线动作/人物情绪。",
        "title": "ЛЕГКОЕ ВДЕВАНИЕ НИТИ",
    },
    "storage-travel": {
        "paradigm": "lifestyle_human_scene",
        "buyer_question": "收纳和携带是否方便？",
        "commercial_intent": "展示木盒/收纳价值。",
        "visual_answer": "手部收纳场景 + 木盒。",
        "title": "УДОБНО ХРАНИТЬ",
    },
    "material-macro": {
        "paradigm": "material_macro",
        "buyer_question": "材质/工艺是否可靠？",
        "commercial_intent": "建立品质感。",
        "visual_answer": "产品材质微距 + 一句话材质说明。",
        "title": "КАЧЕСТВЕННЫЙ МАТЕРИАЛ",
    },
    "lifestyle-human-scene": {
        "paradigm": "lifestyle_human_scene",
        "buyer_question": "日常使用是否自然？",
        "commercial_intent": "建立真实生活信任。",
        "visual_answer": "人物在家居/手工/护理场景中自然使用产品。",
        "title": "ЛЕГКО В КАЖДЫЙ ДЕНЬ",
    },
    "task-cards": {
        "paradigm": "scene_grid",
        "buyer_question": "它能做哪些具体任务？",
        "commercial_intent": "拓展用途但保持克制。",
        "visual_answer": "3 个任务卡片，每个一张局部图。",
        "title": "ДЛЯ РАЗНЫХ ЗАДАЧ",
    },
    "beauty-result": {
        "paradigm": "lifestyle_human_scene",
        "buyer_question": "能否带来精致护理结果？",
        "commercial_intent": "用美容场景建立期待。",
        "visual_answer": "干净美容人物场景，产品可见。",
        "title": "ИДЕАЛЬНЫЙ РЕЗУЛЬТАТ",
    },
    "application-grid": {
        "paradigm": "scene_grid",
        "buyer_question": "适用于哪些护理对象？",
        "commercial_intent": "展示多用途但不拥挤。",
        "visual_answer": "头发/眉毛/睫毛/精细护理网格。",
        "title": "УНИВЕРСАЛЬНОЕ ПРИМЕНЕНИЕ",
    },
    "compatibility": {
        "paradigm": "scene_grid",
        "buyer_question": "适配哪些设备/车辆？",
        "commercial_intent": "降低适配疑虑。",
        "visual_answer": "汽车/自行车/摩托/气泵等对象图。",
        "title": "ПОДХОДИТ ДЛЯ",
    },
    "airtight-seal": {
        "paradigm": "trust_closure",
        "buyer_question": "是否密封可靠？",
        "commercial_intent": "强化核心性能。",
        "visual_answer": "产品英雄图 + 密封主题背景。",
        "title": "ГЕРМЕТИЧНОСТЬ",
    },
    "material-quality": {
        "paradigm": "material_macro",
        "buyer_question": "材质是否耐用？",
        "commercial_intent": "建立工业品质感。",
        "visual_answer": "金属质感特写 + 使用场景。",
        "title": "ВЫСОКОЕ КАЧЕСТВО",
    },
    "fit-grid": {
        "paradigm": "scene_grid",
        "buyer_question": "是否适用于多类对象？",
        "commercial_intent": "扩展购买场景。",
        "visual_answer": "四象限适配对象，中间产品锚点。",
        "title": "ДЛЯ БОЛЬШИНСТВА ВИДОВ",
    },
    "trust-closure": {
        "paradigm": "trust_closure",
        "buyer_question": "为什么可信？",
        "commercial_intent": "最后收口品质信任。",
        "visual_answer": "产品稳定居中 + 一句品质标题。",
        "title": "НАДЁЖНОЕ КАЧЕСТВО",
    },
    "product-callouts": {
        "paradigm": "product_callouts",
        "buyer_question": "有哪些关键结构/卖点？",
        "commercial_intent": "把结构转成购买理由。",
        "visual_answer": "真实产品居中，周围由 overlay 绘制短标签圈注。",
        "title": "ОСНОВНЫЕ ПРЕИМУЩЕСТВА",
    },
    "scene-grid": {
        "paradigm": "scene_grid",
        "buyer_question": "适用场景有哪些？",
        "commercial_intent": "扩大适用想象。",
        "visual_answer": "2x2 场景卡片。",
        "title": "УНИВЕРСАЛЬНОЕ ПРИМЕНЕНИЕ",
    },
}


def load_json(path: Optional[Path]) -> Dict[str, Any]:
    if not path:
        return {}
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_text(obj: Any) -> str:
    chunks: List[str] = []
    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif x is not None:
            s = str(x).strip()
            if s:
                chunks.append(s)
    walk(obj)
    return "\n".join(chunks)



def classify_archetype(text: str) -> str:
    low = text.lower()
    best = ("generic_household", 0)
    for name, cfg in ARCHETYPES.items():
        score = sum(1 for kw in cfg.get("keywords", []) if kw.lower() in low)
        if score > best[1]:
            best = (name, score)
    return best[0]


def extract_metrics(text: str) -> List[str]:
    found = []
    for m in METRIC_RE.finditer(text):
        item = f"{m.group(1).replace(',', '.')} {m.group(2)}"
        if item not in found:
            found.append(item)
    return found[:10]


def _to_mm(value: float, unit: str) -> Optional[float]:
    unit = unit.lower()
    if unit == "мм":
        return value
    if unit == "см":
        return value * 10
    if unit == "м":
        return value * 1000
    return None


def _dim_kind(context: str) -> str:
    c = context.lower()
    groups = [
        ("length", ["длина", "length", "long", "长", "长度"]),
        ("width", ["ширина", "width", "wide", "宽", "宽度"]),
        ("height", ["высота", "height", "高", "高度"]),
        ("blade_width", ["лезв", "blade", "刀刃", "刀片"]),
    ]
    hits = []
    for kind, keys in groups:
        positions = [c.find(k) for k in keys if c.find(k) >= 0]
        if positions:
            hits.append((min(positions), kind))
    if hits:
        hits.sort(key=lambda x: x[0])
        return hits[0][1]
    return "dimension"


def extract_dimensional_facts(text: str) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    seen = set()
    for m in METRIC_RE.finditer(text):
        raw = f"{m.group(1).replace(',', '.')} {m.group(2)}"
        unit = m.group(2)
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        value_mm = _to_mm(value, unit)

        # Prefer labels immediately after the metric: "130 мм / длина".
        after = text[m.end(): m.end() + 22]
        before = text[max(0, m.start() - 14): m.start()]
        kind = _dim_kind(after)
        if kind == "dimension":
            kind = _dim_kind(before)
        if kind == "dimension" and value_mm is None:
            kind = "metric"

        rec = {
            "raw": raw,
            "value": value,
            "unit": unit,
            "value_mm": round(value_mm, 3) if value_mm is not None else None,
            "kind": kind,
            "context": " ".join(f"{before} {after}".split())[:80],
        }
        key = (rec["raw"], rec["kind"], rec.get("context", ""))
        if key not in seen:
            facts.append(rec)
            seen.add(key)
    return facts[:12]


def infer_geometry_lock(dim_facts: List[Dict[str, Any]], reference_manifest: Dict[str, Any]) -> Dict[str, Any]:
    length_mm = next((f["value_mm"] for f in dim_facts if f.get("kind") == "length" and f.get("value_mm")), None)
    width_mm = next((f["value_mm"] for f in dim_facts if f.get("kind") == "width" and f.get("value_mm")), None)
    ratio = None
    if length_mm and width_mm and width_mm > 0:
        ratio = round(float(length_mm) / float(width_mm), 3)
    else:
        vals = sorted({float(f["value_mm"]) for f in dim_facts if f.get("value_mm") and float(f["value_mm"]) > 0})
        if len(vals) >= 2:
            # Prefer the largest physical length divided by a plausible body width.
            largest = vals[-1]
            plausible_widths = [v for v in vals[:-1] if v >= largest * 0.06]
            if plausible_widths:
                ratio = round(largest / plausible_widths[0], 3)

    rules = [
        "Use the selected/attached real product image as the immutable product anchor.",
        "Do not redraw the product from text memory.",
        "Preserve the exact silhouette, length, width, thickness, color, material, package, count and key structural details.",
        "Do not shorten, fatten, thicken, bend, recolor, simplify, or replace the SKU with a similar product.",
    ]
    if ratio and ratio >= 4:
        rules.append(f"Preserve the slender long-body geometry; target length-to-width ratio is about {ratio}:1.")
    return {
        "mode": "strict_reference_lock",
        "physical_length_to_width_ratio_estimate": ratio,
        "dimensional_facts": dim_facts,
        "primary_product_refs": reference_manifest.get("primary_product_refs", []),
        "primary_product_abs_refs": reference_manifest.get("primary_product_abs_refs", []),
        "rules": rules,
    }


def pick_value(sku: Dict[str, Any], keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        cur: Any = sku
        ok = True
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur:
            return str(cur).strip()
    return default


def infer_product_name_ru(sku: Dict[str, Any], archetype: str) -> str:
    direct = pick_value(sku, [
        "product_name_ru", "title_ru", "name_ru", "ru_title",
        "listing.title_ru", "ozon_title_ru", "title"
    ])
    if direct:
        return direct[:80]
    defaults = {
        "yellow_deodorant_sticker": "СТИКЕРЫ ДЛЯ ОБУВИ",
        "transparent_heel_gel": "ВКЛАДЫШИ ДЛЯ ОБУВИ",
        "warm_needle_set": "НАБОР ИГЛ",
        "beauty_manicure_scissors": "МАНИКЮРНЫЕ НОЖНИЦЫ",
        "auto_industrial_part": "БЫСТРОСЪЕМНЫЙ НАКОНЕЧНИК",
        "office_craft_cutting_tool": "КАНЦЕЛЯРСКИЙ НОЖ",
        "generic_household": "ПОЛЕЗНЫЙ ТОВАР",
    }
    return defaults.get(archetype, "ПОЛЕЗНЫЙ ТОВАР")


def infer_badge(metrics: List[str], text: str, archetype: str) -> str:
    for m in metrics:
        if any(unit in m.lower() for unit in ["шт", "штук"]):
            return m
    for m in metrics:
        if any(unit in m.lower() for unit in ["дней", "дня", "месяц"]):
            return m
    if archetype == "yellow_deodorant_sticker":
        return "12 шт"
    if archetype == "transparent_heel_gel":
        return "2 шт"
    if archetype == "warm_needle_set":
        return "12 шт"
    if archetype == "beauty_manicure_scissors":
        return "9 см"
    if archetype == "office_craft_cutting_tool":
        for m in metrics:
            if "мм" in m.lower():
                return m
        return "9 мм"
    return metrics[0] if metrics else ""


def slot_plan_ids(slot_plan: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    if not slot_plan:
        return ids
    raw = slot_plan.get("slots") or slot_plan.get("slot_specs") or slot_plan.get("plan") or []
    if isinstance(raw, dict):
        raw = list(raw.values())
    for item in raw:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict):
            sid = item.get("id") or item.get("slot_id") or item.get("name")
            if sid:
                ids.append(str(sid))
    return ids


def normalize_sequence(archetype: str, slot_plan: Dict[str, Any], max_slots: int) -> List[str]:
    from_plan = slot_plan_ids(slot_plan)
    seq = from_plan if from_plan else ARCHETYPES[archetype]["sequence"]
    result: List[str] = []
    for sid in seq:
        if sid not in result:
            result.append(sid)
    return result[:max_slots]


def _box(x: float, y: float, w: float, h: float, style: str) -> Dict[str, Any]:
    return {"xywh": [round(x, 4), round(y, 4), round(w, 4), round(h, 4)], "style": style}


def _dimension_text(fact: Dict[str, Any]) -> str:
    raw = fact.get("raw", "")
    kind = fact.get("kind")
    suffix = {
        "length": "длина",
        "width": "ширина",
        "height": "высота",
        "blade_width": "лезвие",
    }.get(kind)
    return f"{raw} / {suffix}" if suffix else raw


def extract_bullets_ru(sku: Dict[str, Any]) -> List[str]:
    keys = ["bullets_ru", "benefits_ru", "features_ru", "selling_points_ru"]
    for key in keys:
        cur = sku.get(key)
        if isinstance(cur, list):
            return [str(x).strip() for x in cur if str(x).strip()][:4]
        if isinstance(cur, str) and cur.strip():
            parts = re.split(r"[\n;；|]+", cur)
            return [p.strip() for p in parts if p.strip()][:4]
    return []


def overlay_plan_for_slot(
    slot_id: str,
    title: str,
    badge: str,
    metrics: List[str],
    dim_facts: List[Dict[str, Any]],
    sku: Dict[str, Any],
) -> Dict[str, Any]:
    spec = SLOT_DEFAULTS.get(slot_id, SLOT_DEFAULTS["product-callouts"])
    slot_title = spec.get("title") or title
    if slot_id == "hero-product":
        slot_title = title

    plan: Dict[str, Any] = {
        "title": slot_title,
        "title_box": _box(0.06, 0.04, 0.88, 0.125, "white_pill"),
        "subtitle": "",
        "subtitle_box": _box(0.08, 0.84, 0.84, 0.075, "white_pill"),
        "badges": [],
        "labels": [],
        "dimensions": [],
        "steps": [],
        "style": {
            "font_family": "DejaVu Sans or Arial with Cyrillic support",
            "title_weight": "bold",
            "title_case": "upper or title",
            "cards_owned_by": "overlay_text.py",
        }
    }

    if badge and slot_id in ["hero-product", "quantity-pack", "duration-effect"]:
        plan["badges"].append({"text": badge, "box": _box(0.06, 0.18, 0.25, 0.10, "green_badge")})

    if slot_id == "size-spec":
        facts = [f for f in dim_facts if f.get("unit") in ["мм", "см", "м"]]
        preferred = [f for f in facts if f.get("kind") in ["length", "width", "height", "blade_width"]]
        use_facts = (preferred or facts)[:4]
        default_boxes = [
            _box(0.66, 0.28, 0.28, 0.06, "white_card"),
            _box(0.66, 0.36, 0.28, 0.06, "white_card"),
            _box(0.66, 0.44, 0.28, 0.06, "white_card"),
            _box(0.66, 0.52, 0.28, 0.06, "white_card"),
        ]
        if use_facts:
            plan["dimensions"] = [{"text": _dimension_text(f), "box": default_boxes[i]} for i, f in enumerate(use_facts[:4])]
        elif metrics:
            plan["dimensions"] = [{"text": m, "box": default_boxes[i]} for i, m in enumerate(metrics[:4])]

    if slot_id == "steps-123":
        plan["steps"] = [
            {"n": 1, "caption": "ШАГ 1", "box": _box(0.08, 0.82, 0.21, 0.065, "green_badge")},
            {"n": 2, "caption": "ШАГ 2", "box": _box(0.395, 0.82, 0.21, 0.065, "green_badge")},
            {"n": 3, "caption": "ШАГ 3", "box": _box(0.71, 0.82, 0.21, 0.065, "green_badge")},
        ]

    if slot_id == "product-callouts":
        bullets = extract_bullets_ru(sku)
        label_boxes = [
            _box(0.06, 0.30, 0.28, 0.055, "white_card"),
            _box(0.66, 0.30, 0.28, 0.055, "white_card"),
            _box(0.06, 0.58, 0.28, 0.055, "white_card"),
            _box(0.66, 0.58, 0.28, 0.055, "white_card"),
        ]
        for i, txt in enumerate(bullets[:4]):
            plan["labels"].append({"text": txt, "box": label_boxes[i]})

    if slot_id in ["material-macro", "material-quality"] and not plan["labels"]:
        bullets = extract_bullets_ru(sku)
        if bullets:
            plan["labels"].append({"text": bullets[0], "box": _box(0.08, 0.82, 0.84, 0.075, "white_pill")})

    return plan


def build_plate_prompt(archetype: str, slot_id: str, slot: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    geometry = slot.get("layout_plan", {}).get("product_geometry_lock", {})
    ratio = geometry.get("physical_length_to_width_ratio_estimate")
    ratio_sentence = f" Preserve the product's slender length-to-width ratio around {ratio}:1." if ratio else ""
    return (
        "Create a vertical 3:4 full-bleed Russian ecommerce product visual plate. "
        "Use the attached/selected real product reference image(s) as the immutable product anchor. "
        "Do not generate or redraw the product from text memory. "
        "Preserve the same silhouette, length, width, thickness, color, material, package, count, and key structural details."
        f"{ratio_sentence} "
        "Do NOT render final readable Russian or Cyrillic text. "
        "Do NOT draw placeholder text cards, empty rounded boxes, UI frames, random label outlines, or fake glyphs. "
        "Only leave smooth clean background in overlay safe zones; overlay_text.py will draw all cards and text later. "
        "Fill the entire 3:4 canvas edge-to-edge with commercial background: no side white borders, no gutters, no empty left/right margins. "
        f"Category archetype: {archetype}. Palette and mood: {cfg['palette']} / {cfg['visual_mood']}. "
        f"Design paradigm: {slot['selected_paradigm']}. "
        f"Buyer question: {slot['buyer_question']}. "
        f"Visual answer: {slot['visual_answer']}. "
        "Use clean commercial lighting and high perceived quality while keeping factual product fidelity above all."
    )


def build_contract(
    sku: Dict[str, Any],
    slot_plan: Optional[Dict[str, Any]] = None,
    max_slots: int = 8,
    reference_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    slot_plan = slot_plan or {}
    reference_manifest = reference_manifest or {}
    text = flatten_text({"sku": sku, "slot_plan": slot_plan})
    archetype = classify_archetype(text)

    dim_facts = extract_dimensional_facts(text)
    metrics = extract_metrics(text)
    geometry_lock = infer_geometry_lock(dim_facts, reference_manifest)
    reference_images = reference_manifest.get("primary_product_abs_refs") or reference_manifest.get("primary_product_refs") or []


    cfg = ARCHETYPES[archetype]
    title_ru = infer_product_name_ru(sku, archetype)
    badge = infer_badge(metrics, text, archetype)
    seq = normalize_sequence(archetype, slot_plan, max_slots)

    sku_facts = {
        "product_name_ru": title_ru,
        "metrics_detected": metrics,
        "dimensional_facts": dim_facts,
        "must_preserve": cfg["must_preserve"] + [
            "selected real product reference image identity",
            "length-to-width ratio and silhouette",
        ],
        "forbidden_changes": [
            "do not change product shape",
            "do not change product color",
            "do not shorten, fatten, thicken, bend, recolor, simplify, or replace the product",
            "do not invent package or count",
            "do not alter material appearance",
            "do not render final readable Cyrillic text in the image model",
            "do not draw placeholder text cards or empty rounded boxes in Codex plate",
            "do not leave side white borders or large left/right gutters",
        ],
    }

    contracts = []
    for idx, slot_id in enumerate(seq, start=1):
        base = SLOT_DEFAULTS.get(slot_id, SLOT_DEFAULTS["product-callouts"])
        slot = {
            "slot_index": idx,
            "slot_id": slot_id,
            "buyer_question": base["buyer_question"],
            "commercial_intent": base["commercial_intent"],
            "selected_paradigm": base["paradigm"],
            "visual_answer": base["visual_answer"],
            "layout_plan": {
                "canvas": DEFAULT_CANVAS,
                "palette": cfg["palette"],
                "product_rendering_mode": "locked_reference_composite",
                "reference_images": reference_images,
                "product_geometry_lock": geometry_lock,
                "background": "full-bleed edge-to-edge commercial background; no side margins",
                "text_policy": "no final text/cards/placeholders in Codex plate; overlay_text.py draws all cards and text",
            },
            "overlay_text_plan": overlay_plan_for_slot(slot_id, title_ru, badge, metrics, dim_facts, sku),
            "negative_prompt": [
                "no final readable Cyrillic text",
                "no fake glyphs or garbled letters",
                "no placeholder text boxes",
                "no empty rounded label cards",
                "no random UI frames",
                "no side white borders",
                "no left/right empty gutters",
                "do not alter product shape",
                "do not alter product length-to-width ratio",
                "do not make the product shorter, fatter, thicker, or simplified",
                "do not alter product color",
                "do not invent extra items",
                "do not change package or count",
                "no cluttered low-quality collage",
            ],
            "critic_checks": [
                "primary product body matches selected reference image",
                "length-to-width ratio and silhouette preserved",
                "quantity/size/material facts are preserved",
                "one buyer question is answered clearly",
                "no model-generated placeholder cards or fake Cyrillic",
                "overlay text boxes align with the final design",
                "canvas is full-bleed 3:4 without side gutters",
                "set palette matches category archetype",
            ],
        }
        slot["codex_plate_prompt"] = build_plate_prompt(archetype, slot_id, slot, cfg)
        contracts.append(slot)

    return {
        "contract_version": CONTRACT_VERSION,
        "status": "ready",
        "auto_generate_allowed": True,
        "category_archetype": archetype,
        "reference_images": reference_images,
        "reference_manifest": {
            "primary_product_refs": reference_manifest.get("primary_product_refs", []),
            "needs_visual_confirmation": reference_manifest.get("needs_visual_confirmation", False),
            "vision_instruction": reference_manifest.get("vision_instruction", ""),
        },
        "product_geometry_lock": geometry_lock,
        "set_style": {
            "canvas": DEFAULT_CANVAS,
            "palette": cfg["palette"],
            "visual_mood": cfg["visual_mood"],
            "typography": "programmatic Cyrillic overlay only; overlay script owns cards",
        },
        "sku_facts": sku_facts,
        "slot_contracts": contracts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("standard_sku", type=Path, help="Path to standard_sku.json")
    parser.add_argument("--slot-plan", type=Path, default=None, help="Optional slot_plan.json")
    parser.add_argument("--reference-manifest", type=Path, default=None, help="Optional reference_manifest.json from reference_selector.py")
    parser.add_argument("--comm-dir", type=Path, default=None, help="Optional 沟通图片 folder; creates reference manifest next to output")
    parser.add_argument("--out", type=Path, default=Path("art_director_contract.json"))
    parser.add_argument("--max-slots", type=int, default=8)
    args = parser.parse_args()

    sku = load_json(args.standard_sku)
    slot_plan = load_json(args.slot_plan) if args.slot_plan else {}
    reference_manifest: Dict[str, Any] = {}
    if args.reference_manifest:
        reference_manifest = load_json(args.reference_manifest)
    elif args.comm_dir:
        from reference_selector import build_reference_manifest
        reference_manifest = build_reference_manifest(args.comm_dir)
        ref_out = args.out.parent / "reference_manifest.json"
        ref_out.parent.mkdir(parents=True, exist_ok=True)
        ref_out.write_text(json.dumps(reference_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    contract = build_contract(sku, slot_plan, max_slots=args.max_slots, reference_manifest=reference_manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out} status={contract.get('status')} slots={len(contract.get('slot_contracts', []))}")


if __name__ == "__main__":
    main()
