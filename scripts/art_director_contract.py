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

CONTRACT_VERSION = "2026-04-28-v4-reference-lock-overlay-runner"
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
    "fridge_odor_absorber": {
        "keywords": ["холодильник", "поглотитель запаха", "нейтрализатор запахов", "осушитель", "активированн", "уголь", "шкаф", "кухн", "冰箱", "除味剂", "活性炭", "吸湿", "除臭"],
        "palette": "clean white / fresh green / warm kitchen wood / sunlight",
        "visual_mood": "fresh kitchen, odor neutralizing, natural household care, clean storage",
        "must_preserve": ["white vented rectangular case", "rounded corners", "black absorbent layer visible through vents", "compact box proportions"],
        "sequence": ["hero-product", "size-spec", "before-after-result", "scene-grid", "material-macro", "mechanism-ingredients", "recharge-cycle", "lifestyle-human-scene"],
    },
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
        "palette": "office-tool: clean white / deep navy / soft sage green / grey cutting mat / metal ruler / kraft box",
        "visual_mood": "precise office tool, packaging cutter, controlled sharpness, less decorative stationery",
        "must_preserve": ["long narrow black handle", "segmented steel blade", "slider ribs", "end cap notch", "9mm blade width", "130mm body length", "13mm body width"],
        "sequence": ["hero-product", "size-spec", "angle-feature", "material-macro", "product-callouts", "steps-123", "scene-grid", "unboxing-scene"],
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
    "recharge-cycle": {
        "paradigm": "material_macro",
        "buyer_question": "能否重复使用，怎么恢复吸附能力？",
        "commercial_intent": "用阳光再生周期说明长期使用价值。",
        "visual_answer": "阳光窗台/木桌上的产品 + 2 个绿色周期信息卡。",
        "title": "ДО 2 ЛЕТ ИСПОЛЬЗОВАНИЯ",
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
        "visual_answer": "2x2 独立场景卡片；每格都要有产品参与该用途，标题区压缩，场景面积优先。",
        "title": "ДЛЯ РАЗНЫХ ЗАДАЧ",
    },
    "angle-feature": {
        "paradigm": "angle_feature",
        "buyer_question": "刀尖角度为什么适合精细切割？",
        "commercial_intent": "把 30° 刀尖转成精确、干净、可控的购买理由。",
        "visual_answer": "刀尖贴近纸张，30° 角度标注必须靠近刀尖，避免孤立标签。",
        "title": "30° ДЛЯ ТОЧНОГО РЕЗА",
    },
    "ergo-handhold": {
        "paradigm": "lifestyle_human_scene",
        "buyer_question": "握持是否舒服、是否好控制？",
        "commercial_intent": "证明细长轻巧和防滑纹理带来日常可控感。",
        "visual_answer": "真实手部握持裁切纸张，产品清楚可见，背景为柔和办公/手工桌面。",
        "title": "УДОБСТВО ИСПОЛЬЗОВАНИЯ",
    },
    "unboxing-scene": {
        "paradigm": "lifestyle_human_scene",
        "buyer_question": "开箱/拆包时是否顺手？",
        "commercial_intent": "用日常拆包动作建立实用场景，而不是夸张锋利卖点。",
        "visual_answer": "刀尖必须落在纸箱封口胶带/缝隙上，产品主体露出 60% 以上。",
        "title": "ДЛЯ РАСПАКОВКИ",
    },
    "repair-home-scene": {
        "paradigm": "lifestyle_human_scene",
        "buyer_question": "除了办公，还能用于家用修整吗？",
        "commercial_intent": "扩展到修理、手工、家用小任务的购买场景。",
        "visual_answer": "明亮家居维修/手工场景，产品用于纸张或薄材料修整，不出现危险动作。",
        "title": "НЕЗАМЕНИМ В РЕМОНТЕ И БЫТУ",
    },
    "structure-steps": {
        "paradigm": "structure_steps",
        "buyer_question": "刀片替换和结构是否清楚可靠？",
        "commercial_intent": "展示滑块、尾盖、分段刀片等结构，降低使用疑虑。",
        "visual_answer": "三段结构演示：整刀、拆下尾盖/滑块、替换分段刀片。",
        "title": "ПРОСТАЯ ЗАМЕНА ЛЕЗВИЙ",
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


def infer_style_profile(sku: Dict[str, Any], archetype: str) -> str:
    direct = pick_value(sku, ["style_profile", "visual_style", "listing_style"])
    if direct:
        return direct
    if archetype == "office_craft_cutting_tool":
        return "office-craft"
    return ""


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
        "fridge_odor_absorber": "ПОГЛОТИТЕЛЬ ЗАПАХА",
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
    if archetype == "fridge_odor_absorber":
        for m in metrics:
            if any(unit in m.lower() for unit in ["месяц", "см", "г"]):
                return m
        return "без отдушки"
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


def office_craft_overlay_plan(slot_id: str, title: str, badge: str, metrics: List[str], dim_facts: List[Dict[str, Any]], sku: Dict[str, Any]) -> Dict[str, Any]:
    """美工刀电商证据链 overlay：少字、统一层级，避免横线/大字盖住产品。"""
    base_title = {
        "hero-product": "КАНЦЕЛЯРСКИЙ НОЖ",
        "size-spec": "РАЗМЕР И ЛЕЗВИЕ",
        "angle-feature": "30° ДЛЯ ТОЧНОГО РЕЗА",
        "material-macro": "СТАЛЬ SK2",
        "product-callouts": "ОСНОВНЫЕ ОСОБЕННОСТИ",
        "steps-123": "ПРОСТОЕ ИСПОЛЬЗОВАНИЕ",
        "scene-grid": "ДЛЯ РАЗНЫХ ЗАДАЧ",
        "unboxing-scene": "ДЛЯ РАСПАКОВКИ",
        "ergo-handhold": "УДОБНЫЙ ХВАТ",
        "repair-home-scene": "Незаменим в\nремонте и быту",
        "structure-steps": "ПРОСТАЯ ЗАМЕНА ЛЕЗВИЙ",
    }.get(slot_id, title)

    plan: Dict[str, Any] = {
        "title": base_title,
        "title_box": _box(0.060, 0.050, 0.74, 0.130, "transparent_navy"),
        "subtitle": "",
        "subtitle_box": _box(0.08, 0.84, 0.84, 0.075, "soft_green_pill"),
        "badges": [],
        "labels": [],
        "dimensions": [],
        "steps": [],
        "arrows": [],
        "icons": [],
        "style": {
            "font_family": "DejaVu Sans or Arial with Cyrillic support",
            "title_weight": "bold",
            "title_case": "mixed upper/title, designer-style underline",
            "cards_owned_by": "overlay_text.py",
            "style_profile": "office-craft",
        },
    }
    plan["title_box"]["align"] = "left"
    plan["title_box"]["start_size"] = 58
    plan["title_box"]["max_lines"] = 2

    if slot_id == "hero-product":
        plan["badges"].append({"text": "9 мм", "box": _box(0.06, 0.245, 0.20, 0.080, "soft_green_pill"), "start_size": 52})
        plan["subtitle"] = "ДЛЯ БУМАГИ И УПАКОВКИ"
        plan["subtitle_box"] = _box(0.40, 0.835, 0.52, 0.085, "soft_green_pill")
        plan["subtitle_box"]["start_size"] = 34
        plan["subtitle_box"]["max_lines"] = 2
    elif slot_id == "size-spec":
        plan["title_box"] = _box(0.060, 0.045, 0.62, 0.080, "dark_navy_pill")
        plan["title_box"]["start_size"] = 32
        plan["dimensions"] = [
            {"text": "130 мм длина", "box": _box(0.12, 0.70, 0.34, 0.060, "soft_green_pill"), "start_size": 26},
            {"text": "13 мм ширина", "box": _box(0.56, 0.30, 0.34, 0.060, "soft_green_pill"), "start_size": 26},
            {"text": "9 мм лезвие", "box": _box(0.08, 0.26, 0.30, 0.060, "soft_green_pill"), "start_size": 26},
        ]
        plan["arrows"] = [
            {"from": [0.20, 0.68], "to": [0.73, 0.24], "color": [31, 45, 74, 225], "width": 3},
            {"from": [0.64, 0.36], "to": [0.72, 0.38], "color": [31, 45, 74, 225], "width": 3},
            {"from": [0.20, 0.32], "to": [0.16, 0.72], "color": [31, 45, 74, 225], "width": 3},
        ]
    elif slot_id == "scene-grid":
        plan["title_box"] = _box(0.06, 0.030, 0.72, 0.095, "transparent_navy")
        plan["title_box"]["align"] = "left"
        plan["title_box"]["start_size"] = 48
        plan["labels"] = [
            {"text": "ОБОИ", "box": _box(0.09, 0.455, 0.28, 0.052, "dark_navy_pill"), "start_size": 28},
            {"text": "БУМАГА", "box": _box(0.61, 0.455, 0.28, 0.052, "dark_navy_pill"), "start_size": 28},
            {"text": "ТВОРЧЕСТВО", "box": _box(0.075, 0.795, 0.35, 0.052, "dark_navy_pill"), "start_size": 24},
            {"text": "УПАКОВКА", "box": _box(0.58, 0.795, 0.34, 0.052, "dark_navy_pill"), "start_size": 26},
        ]
    elif slot_id == "angle-feature":
        plan["title_box"] = _box(0.060, 0.045, 0.74, 0.120, "transparent_navy")
        plan["title_box"]["start_size"] = 50
        plan["badges"].append({"text": "30°", "box": _box(0.14, 0.58, 0.15, 0.070, "soft_green_pill"), "start_size": 38})
        plan["labels"] = [
            {"text": "ТОЧНЫЙ РЕЗ", "box": _box(0.54, 0.80, 0.30, 0.055, "dark_navy_pill"), "start_size": 22},
        ]
        plan["arrows"] = [
            {"from": [0.20, 0.63], "to": [0.14, 0.75], "color": [31, 45, 74, 230], "width": 3},
        ]
    elif slot_id == "ergo-handhold":
        plan["title_box"] = _box(0.08, 0.06, 0.58, 0.105, "dark_navy_pill")
        plan["title_box"]["start_size"] = 34
        plan["labels"] = [
            {"text": "Лёгкость и контроль", "box": _box(0.56, 0.80, 0.36, 0.065, "soft_green_pill"), "start_size": 26},
        ]
    elif slot_id == "material-macro":
        plan["title_box"] = _box(0.06, 0.055, 0.34, 0.080, "dark_navy_pill")
        plan["title_box"]["start_size"] = 34
        plan["labels"] = [
            {"text": "ЧИСТЫЙ И РОВНЫЙ РЕЗ", "box": _box(0.07, 0.155, 0.48, 0.060, "soft_green_pill"), "start_size": 22, "max_lines": 2}
        ]
    elif slot_id == "product-callouts":
        plan["title_box"] = _box(0.055, 0.045, 0.72, 0.080, "dark_navy_pill")
        plan["title_box"]["start_size"] = 30
        plan["labels"] = [
            {"text": "9 мм лезвие", "box": _box(0.06, 0.30, 0.28, 0.058, "soft_green_pill"), "start_size": 22},
            {"text": "удобный бегунок", "box": _box(0.61, 0.40, 0.31, 0.058, "soft_green_pill"), "start_size": 20},
            {"text": "сменное лезвие", "box": _box(0.06, 0.71, 0.31, 0.058, "soft_green_pill"), "start_size": 20},
            {"text": "компактный корпус", "box": _box(0.58, 0.74, 0.33, 0.058, "soft_green_pill"), "start_size": 20},
        ]
        plan["arrows"] = [
            {"from": [0.25, 0.36], "to": [0.20, 0.79], "color": [31, 45, 74, 210], "width": 2},
            {"from": [0.64, 0.46], "to": [0.53, 0.52], "color": [31, 45, 74, 210], "width": 2},
            {"from": [0.26, 0.73], "to": [0.30, 0.82], "color": [31, 45, 74, 210], "width": 2},
            {"from": [0.61, 0.75], "to": [0.53, 0.66], "color": [31, 45, 74, 210], "width": 2},
        ]
    elif slot_id == "steps-123":
        plan["title_box"] = _box(0.055, 0.045, 0.62, 0.080, "dark_navy_pill")
        plan["title_box"]["start_size"] = 28
        plan["steps"] = [
            {"caption": "1", "box": _box(0.08, 0.30, 0.10, 0.065, "green_square"), "start_size": 42},
            {"caption": "2", "box": _box(0.08, 0.53, 0.10, 0.065, "green_square"), "start_size": 42},
            {"caption": "3", "box": _box(0.08, 0.76, 0.10, 0.065, "green_square"), "start_size": 42},
        ]
        plan["labels"] = [
            {"text": "выдвиньте лезвие", "box": _box(0.20, 0.30, 0.30, 0.050, "dark_navy_pill"), "start_size": 18},
            {"text": "режьте по линии", "box": _box(0.20, 0.53, 0.30, 0.050, "dark_navy_pill"), "start_size": 18},
            {"text": "уберите лезвие", "box": _box(0.20, 0.76, 0.30, 0.050, "dark_navy_pill"), "start_size": 18},
        ]
    elif slot_id in {"unboxing-scene", "repair-home-scene"}:
        plan["title_box"] = _box(0.07, 0.055, 0.56, 0.090, "dark_navy_pill")
        plan["title_box"]["start_size"] = 36
        plan["title_box"]["max_lines"] = 2
        if slot_id == "unboxing-scene":
            plan["subtitle"] = ""
    elif slot_id == "structure-steps":
        plan["title_box"] = _box(0.06, 0.055, 0.86, 0.085, "dark_navy_pill")
        plan["title_box"]["start_size"] = 34
        plan["steps"] = [
            {"caption": "1", "box": _box(0.70, 0.13, 0.11, 0.075, "green_square"), "start_size": 54},
            {"caption": "2", "box": _box(0.58, 0.35, 0.11, 0.075, "green_square"), "start_size": 54},
            {"caption": "3", "box": _box(0.80, 0.62, 0.11, 0.075, "green_square"), "start_size": 54},
        ]
        plan["subtitle"] = ""
        plan["arrows"].append({"from": [0.55, 0.28], "to": [0.46, 0.33], "color": [105, 160, 70, 230], "width": 3})

    if isinstance(plan.get("title_box"), dict):
        plan["title_box"].setdefault("align", "left")
    return plan


def overlay_plan_for_slot(
    slot_id: str,
    title: str,
    badge: str,
    metrics: List[str],
    dim_facts: List[Dict[str, Any]],
    sku: Dict[str, Any],
    style_profile: str = "",
) -> Dict[str, Any]:
    if style_profile == "office-craft":
        return office_craft_overlay_plan(slot_id, title, badge, metrics, dim_facts, sku)

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

    if slot_id == "recharge-cycle":
        plan["badges"] = [
            {"text": "2-3 месяца", "box": _box(0.05, 0.42, 0.34, 0.09, "green_badge")},
            {"text": "3-5 часов под солнцем", "box": _box(0.60, 0.32, 0.34, 0.10, "green_badge")},
        ]

    return plan


def office_craft_slot_generation_requirements(slot_id: str) -> str:
    if slot_id == "scene-grid":
        return (
            "Scene-grid hard requirement: create a clean 2x2 grid made of four independent mini-scenes. "
            "Reserve only the top 10-12% as a smooth light title safe zone; do not waste a large blank header. "
            "The 2x2 grid must start below that compact header safe zone and occupy most of the canvas. "
            "The same black 9 mm utility knife must appear clearly once inside EACH quadrant, four visible knife instances total. "
            "Each quadrant must show a different safe stationery use: top-left trimming wallpaper, top-right cutting paper sheets, "
            "bottom-left craft paper/detail work, bottom-right opening a taped parcel or cutting packing tape. "
            "Do not place one oversized knife across the whole grid. Do not make a single background collage sliced by grid lines. "
            "Keep each knife fully inside its own quadrant with enough blank space near the lower label areas for programmatic Russian labels. "
        )
    if slot_id == "size-spec":
        return (
            "Size-spec HARD requirement: clean light technical product image. "
            "ABSOLUTELY NO HANDS, NO FINGERS, NO HUMAN BODY PARTS. ABSOLUTELY NO LIFESTYLE PROPS. "
            "Allowed accessories: only a subtle ruler or plain cutting mat as dimensional reference. "
            "Show the full black utility knife clearly with enough white space for programmatic dimension labels: 9 mm blade, 130 mm length, 13 mm width. "
            "Do not draw measurement text, arrows, rulers with fake labels, or Cyrillic in the image model; overlay_text.py will draw all dimensions. "
        )
    if slot_id == "hero-product":
        return (
            "Hero-product requirement: one large clear product instance, about 65-75% of canvas height, "
            "sharp black body detail and blade geometry visible, with props secondary. The visual promise is office cutting for paper and packaging, not a soft journaling flat lay. "
        )
    if slot_id == "angle-feature":
        return (
            "Angle-feature requirement: show the blade tip close to paper with a clean 30 degree precision-cutting setup; "
            "leave clear room around the tip for an overlay angle badge and arrow. "
            "Do not draw dashed measurement lines, angle arcs, labels, text, or diagram graphics in the plate; overlay_text.py will add the simple marker. "
        )
    if slot_id == "material-macro":
        return (
            "Material-macro HARD requirement: blade macro close-up is mandatory — show segmented blade edge and metal grain at extreme close range. "
            "ABSOLUTELY NO HANDS, NO FINGERS, NO HUMAN BODY PARTS in frame. "
            "The blade and steel are the subject, not the holding context. "
            "A smaller full product identity view may appear in a corner inset, but the macro must dominate. "
        )
    if slot_id == "product-callouts":
        return (
            "Product-callouts HARD requirement: large clean front/diagonal product on a light technical background. The whole product must be fully visible — no cropping, no occlusion. "
            "ABSOLUTELY NO HANDS, NO FINGERS, NO HUMAN BODY PARTS, NO BUSY PROPS. "
            "Keep slider ribs, segmented blade, end cap notch, and slim black body clearly visible — these structural points anchor 3-4 callout arrows that overlay_text.py will draw. "
            "Leave clear background space around the product perimeter for callout label boxes. "
        )
    if slot_id == "steps-123":
        return (
            "Steps HARD requirement: three simple panels showing the knife's own action sequence: blade extending out of the body, blade meeting paper for a cut, blade retracting back. "
            "Each panel shows the SAME knife from a clean angle — no hand, no fingers, no human body parts. The product itself is the protagonist of each step. "
            "Keep the sequence obvious through the knife's mechanism, not through a person performing the action. "
        )
    if slot_id in {"ergo-handhold", "unboxing-scene", "repair-home-scene"}:
        if slot_id == "unboxing-scene":
            return (
                "Unboxing requirement: the blade tip must touch the parcel seam or transparent tape line exactly where the box should be opened. "
                "Show at least 60% of the black utility knife body, including slider ribs and blade structure. "
                "Keep the hand natural but secondary to product recognition. "
            )
        return (
            "Human-scene requirement: show a natural safe hand/tool interaction for office, craft, unpacking, or home repair use; "
            "the knife body must remain recognizable and not be hidden by fingers or props. "
        )
    if slot_id == "structure-steps":
        return (
            "Structure-steps requirement: show three clear product structure moments with the same knife identity: whole knife, slider/tail cap detail, "
            "and segmented blade replacement detail; leave empty zones for overlay numbers 1, 2, and 3. "
        )
    return ""


def build_plate_prompt(archetype: str, slot_id: str, slot: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    geometry = slot.get("layout_plan", {}).get("product_geometry_lock", {})
    ratio = geometry.get("physical_length_to_width_ratio_estimate")
    ratio_sentence = f" Preserve the product's slender length-to-width ratio around {ratio}:1." if ratio else ""
    style_profile = slot.get("layout_plan", {}).get("style_profile", "")
    office_craft_sentence = ""
    if style_profile == "office-craft":
        office_craft_sentence = (
            "Use the refined office-tool art direction: clean white/light grey background, deep navy safe zones, "
            "soft sage-green accents, grey cutting mat, metal ruler, kraft box, paper and tape as purposeful evidence. "
            "This is an ecommerce detail image, not a decorative lifestyle poster: make the product large, crisp, useful, "
            "and immediately readable; keep plants and soft stationery props minimal. "
            "Avoid dark premium weapon-like styling, five-star review badges, "
            "fake packaging, aggressive sparks, blood, threat, or exaggerated sharpness. "
            f"{office_craft_slot_generation_requirements(slot_id)}"
        )
    return (
        "Create a vertical 3:4 full-bleed Russian ecommerce product visual plate. "
        "Use the attached/selected real product reference image(s) as the immutable product anchor. "
        "Do not generate or redraw the product from text memory. "
        "Preserve the same silhouette, length, width, thickness, color, material, package, count, and key structural details."
        f"{ratio_sentence} "
        f"{office_craft_sentence}"
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
    style_profile = infer_style_profile(sku, archetype)
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
                "style_profile": style_profile,
                "product_rendering_mode": "locked_reference_composite",
                "reference_images": reference_images,
                "product_geometry_lock": geometry_lock,
                "background": "full-bleed edge-to-edge commercial background; no side margins",
                "text_policy": "no final text/cards/placeholders in Codex plate; overlay_text.py draws all cards and text",
            },
            "overlay_text_plan": overlay_plan_for_slot(slot_id, title_ru, badge, metrics, dim_facts, sku, style_profile=style_profile),
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
        if style_profile == "office-craft":
            slot["negative_prompt"].extend([
                "no soft journaling poster look",
                "no excessive plants or decorative paper props",
                "no title underline crossing the product body",
                "no model-generated measurement text, arrows, or Cyrillic",
                "do not hide slider ribs, end cap notch, or segmented blade lines",
                "keep the same utility knife body details across every image",
            ])
        if style_profile == "office-craft" and slot_id == "scene-grid":
            slot["negative_prompt"].extend([
                "no single oversized utility knife crossing multiple quadrants",
                "no one-product-across-grid composition",
                "no decorative background grid without product in every cell",
                "each quadrant must contain one visible utility knife instance",
            ])
            slot["critic_checks"].extend([
                "scene-grid has four independent mini-scenes",
                "the utility knife appears inside every quadrant",
                "no knife instance spans across quadrant borders",
            ])
        if style_profile == "office-craft" and slot_id == "unboxing-scene":
            slot["critic_checks"].extend([
                "blade tip touches the box seam or tape line",
                "at least 60 percent of the product body is visible",
            ])
        if style_profile == "office-craft" and slot_id in {"size-spec", "product-callouts", "material-macro"}:
            slot["critic_checks"].append("visual evidence matches the slot purpose, not a generic hand scene")
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
            "style_profile": style_profile,
            "typography": "programmatic Cyrillic overlay only; overlay script owns cards",
        },
        "sku_facts": sku_facts,
        "slot_contracts": contracts,
    }


# ============================================================================
# V7 prompt builder — fact-driven, native-text, single-product-per-image.
# Operates from sku_truth (see scripts/sku_truth_loader.py) instead of legacy SKU dict.
# All v3-v6 functions above remain unchanged.
# ============================================================================

# Slot → (buyer question, evidence type, default forbidden cross-topics).
V7_SLOT_DEFS: Dict[str, Dict[str, Any]] = {
    "hero-product": {
        "buyer_q_ru": "Что это?",
        "evidence": "identification",
        "forbidden": ["dimension labels", "callout arrows", "usage scenes", "packaging"],
        "hands_allowed": False,
    },
    "size-spec": {
        "buyer_q_ru": "Какого размера?",
        "evidence": "dimensional",
        "forbidden": ["usage scenes", "material close-ups", "structural callouts", "packaging"],
        "hands_allowed": False,
    },
    "thin-blades": {
        "buyer_q_ru": "Почему точный рез?",
        "evidence": "blade_feature",
        "forbidden": ["dimension numbers", "full usage scenes", "packaging"],
        "hands_allowed": False,
    },
    "material-macro": {
        "buyer_q_ru": "Из чего сделан?",
        "evidence": "material_quality",
        "forbidden": ["dimension numbers", "usage scenes", "full body callouts"],
        "hands_allowed": False,
    },
    "product-callouts": {
        "buyer_q_ru": "Какие особенности?",
        "evidence": "structural_callout",
        "forbidden": ["dimension numbers", "lifestyle scenes", "packaging"],
        "hands_allowed": False,
    },
    "steps-123": {
        "buyer_q_ru": "Как использовать?",
        "evidence": "usage_steps",
        "forbidden": ["dimension labels", "material macro", "packaging", "human hands"],
        "hands_allowed": False,
    },
    "usage-demo": {
        "buyer_q_ru": "Как держать и работать?",
        "evidence": "use_proof",
        "forbidden": ["dimension numbers", "material macro", "packaging", "multiple scenes"],
        "hands_allowed": True,
    },
    "home-salon-scene": {
        "buyer_q_ru": "Где использовать?",
        "evidence": "scene_context",
        "forbidden": ["any branded packaging", "gift boxes", "certification marks", "dimension numbers"],
        "hands_allowed": False,
    },
}

V7_DESIGN_HEADER = (
    "Visual design tokens — title pill: dark navy (#1a2b50) bg + white text + rounded; "
    "highlight label: soft green (#c8e8c4) bg + dark navy text + rounded; "
    "scene label: dark navy bg + white text + rounded. "
    "Russian decimal numbers use COMMA (8,5 см). Clean modern sans-serif (Inter / Roboto). "
)

V7_FIDELITY_HEADER = (
    "Preserve the exact product identity from the reference — shape, proportions, finish. "
    "Do not change product grade, do not over-polish or upgrade material feel. "
    "ONE single product instance per image. "
)


def _v7_dimensions_clause(dims: Dict[str, Any]) -> str:
    """Render dimension labels for size-spec slot."""
    hits = dims.get("raw_hits") or []
    if not hits:
        return "(no verified dimensions — show product on a neutral scale reference, no millimeter numbers rendered)"
    parts = [d.get("display_ru", "") for d in hits[:3]]
    return "Render dimension label pills with thin connector lines for these VERIFIED measurements: " + ", ".join(f"\"{p}\"" for p in parts)


def _v7_use_cases_clause(use_cases: List[Dict[str, Any]], n: int = 3) -> str:
    if not use_cases:
        return ""
    sample = [u.get("case_ru", "") for u in use_cases[:n] if u.get("case_ru")]
    short = []
    for s in sample:
        # truncate long use case text — keep first clause
        s = s.split(",")[0].split("/")[0].split(":")[0].strip()
        if 4 <= len(s) <= 60:
            short.append(s)
    if not short:
        return ""
    return "Verified use cases (from listing): " + " / ".join(f"\"{s}\"" for s in short)


def _v7_material_clause(material: Dict[str, Any]) -> str:
    primary = material.get("primary_ru") or "<material unspecified>"
    finish = material.get("finish") or ""
    return f"Material: {primary}" + (f" ({finish})" if finish else "")


def _v7_product_name(sku_truth: Dict[str, Any]) -> str:
    return sku_truth.get("identity", {}).get("product_name_ru") or "the product"


def _v7_archetype_clause(sku_truth: Dict[str, Any]) -> str:
    arch = sku_truth.get("identity", {}).get("archetype", "generic")
    archetype_words = {
        "office_craft": "utility / craft tool",
        "grooming_tool": "personal grooming tool",
        "kitchen_prep": "kitchen prep tool",
        "home_storage": "home storage item",
        "cosmetics": "cosmetic product",
        "small_electronics": "small electronic device",
        "fashion_accessory": "fashion accessory",
        "generic": "consumer product",
    }
    return archetype_words.get(arch, "consumer product")


def build_v7_prompt(sku_truth: Dict[str, Any], slot_id: str) -> str:
    """Compose a v7 native-text edit-mode prompt from sku_truth + slot_id.

    Output target: ≤800 chars, ≤2 negation clauses, all required overlay text,
    fidelity-anchored to reference image, native-Russian text rendering.

    Used by codex_job_runner_v7. Pre-generation, output passes through
    prompt_reviewer.py for safe-mode/fact-fabrication scrubbing.
    """
    if slot_id not in V7_SLOT_DEFS:
        raise ValueError(f"unknown v7 slot: {slot_id}")
    slot = V7_SLOT_DEFS[slot_id]

    canvas = sku_truth.get("canvas", {})
    aspect = canvas.get("aspect_ratio", "3:4")
    size = canvas.get("size_px", "1200x1600")

    product = _v7_product_name(sku_truth)
    archetype = _v7_archetype_clause(sku_truth)
    material_line = _v7_material_clause(sku_truth.get("material", {}))
    dim_line = _v7_dimensions_clause(sku_truth.get("dimensions", {}))
    use_line = _v7_use_cases_clause(sku_truth.get("use_cases", []))

    head = (
        f"Vertical {aspect} ({size}) Russian Ozon listing image of the SAME {product} from the reference "
        f"({archetype}). {V7_FIDELITY_HEADER}"
    )

    if slot_id == "hero-product":
        body = (
            f"Slot: hero-product — first impression, identification. "
            f"Clean light technical background. {material_line}. "
            f"Render text — top-center title pill (navy, white): \"{product}\"; "
            f"below grey subtitle: 1-line short feature line; bottom-right small soft-green badge: 1-line short use line."
        )
    elif slot_id == "size-spec":
        body = (
            f"Slot: size-spec — clean light grey/white technical background, optional subtle metric ruler. "
            f"{dim_line}. "
            f"Render text — top-center title pill (navy, white): \"РАЗМЕР И ЛЕЗВИЕ\"; "
            f"each dimension label as a pill connected by thin line to the corresponding product part."
        )
    elif slot_id == "thin-blades":
        body = (
            f"Slot: thin-blades feature highlight — show blade slim profile from clean side/quarter angle, "
            f"closed posture matching reference. {material_line}. "
            f"Render text — top-center title pill (navy, white): \"ТОНКИЕ ЛЕЗВИЯ\"; "
            f"subtitle grey: \"для точного реза\"; bottom soft-green pill: 1-line claim from listing."
        )
    elif slot_id == "material-macro":
        body = (
            f"Slot: material-macro — extreme close-up of {material_line} surface and texture, fills 70%+ frame. "
            f"Small full-product inset in a corner so SKU identity is preserved. "
            f"Render text — top-left title pill (white, navy): \"{material_line.replace('Material: ', '').upper()}\"; "
            f"top-right small soft-green pill: 1-line trait from listing."
        )
    elif slot_id == "product-callouts":
        body = (
            f"Slot: product-callouts — large clean product on light background, COMPLETE product visible. "
            f"Render text — top-center title banner (navy, white): \"ОСНОВНЫЕ ОСОБЕННОСТИ\"; "
            f"4 soft-green callout pills with thin connector lines to structural points using listing-verified feature names."
        )
    elif slot_id == "steps-123":
        body = (
            f"Slot: steps-123 — three vertical panels showing the SAME ONE {product} in 3 verified usage cases. "
            f"Each panel uses an abstract paper-craft / floating context object (no human body parts). "
            f"All 3 panels show IDENTICAL product proportions and shape. {use_line}. "
            f"Render text — top-center title pill (navy, white): \"ТРИ СПОСОБА ПРИМЕНЕНИЯ\"; "
            f"three large soft-green numbered squares 1/2/3 on the left, each with a navy-pill label per case."
        )
    elif slot_id == "usage-demo":
        body = (
            f"Slot: usage-demo — two-hand collaboration demo. Top-left: hand holds the {product}; bottom-right: "
            f"second hand presents target. Frame stops at wrists. Hands photorealistic, anatomically correct, "
            f"5 fingers each, no extras or fused digits. Product 80% unobstructed. "
            f"Render text — top-center title pill (navy, white): \"ПРАВИЛЬНОЕ ИСПОЛЬЗОВАНИЕ\"; "
            f"subtitle grey: \"две руки для контроля\"; bottom soft-green pill: 1-line trust line."
        )
    elif slot_id == "home-salon-scene":
        pkg = sku_truth.get("packaging", {})
        if pkg.get("has_real_reference_image"):
            body = (
                f"Slot: home-salon-scene — product on a styled tabletop with the verified packaging reference. "
                f"Render text — top-center title pill (navy, white): \"ИДЕАЛЬНЫЙ ВЫБОР\"; "
                f"bottom soft-green pill: 1-line use-context line."
            )
        else:
            body = (
                f"Slot: home-salon-scene — product on a styled tabletop with generic real props (linen towel corner, "
                f"natural greenery, plain ceramic dish). NO branded packaging, NO gift box, NO logo. "
                f"Render text — top-center title pill (navy, white): \"ДОМА И В САЛОНЕ\"; "
                f"bottom soft-green pill: 1-line ежедневное use-context line."
            )
    else:
        body = ""

    forbidden_clause = ""
    if slot["forbidden"]:
        forbidden_clause = " Do not include: " + ", ".join(slot["forbidden"][:2]) + "."

    full = f"{head} {body}{forbidden_clause} {V7_DESIGN_HEADER}"
    return full.strip()


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
