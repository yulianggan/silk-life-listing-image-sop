#!/usr/bin/env python3
"""从 standard_sku.json 推断 11 个产品维度，驱动 slot_planner 评分。

11 维度（v5.1）：
  archetype, use_complexity, effect_visibility, scene_breadth,
  has_strong_metric, tactile_value, lifestyle_value, pack_count,
  durability_centrality, is_consumable, competitor_pressure
+ derived flags: precision_critical, components_gt_1, callout_points,
  mechanism_recoverable, material_style, target_user_warmth

规则尽量保守 — 不确定时给中性默认值。standard_sku.json 可以加
`product_axes_override: {axis: value, ...}` 字段强制覆盖。
"""
from __future__ import annotations

import re
from typing import Any

# 类目 → archetype（v3 类目类型 → v5 archetype 映射）
CATEGORY_TO_ARCHETYPE = {
    "美工刀": "tool",
    "指甲剪": "cosmetic-care",
    "针套装": "cosmetic-care",
    "眉毛剪刀": "cosmetic-care",
    "后跟贴": "lifestyle-accessory",
    "抗菌鞋垫贴纸": "consumable",
    "冰箱除味剂": "consumable",
    "轮胎充气接头": "auto-part",
    "拉链扣": "lifestyle-accessory",
    "条码": "consumable",
}

# 数字 spec 单位（用于 has_strong_metric / metric_extract）
METRIC_PATTERN = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(мм|см|м|°|г|мл|кг|шт|w|вт|в|v)\b", re.IGNORECASE)

# 效果关键词
EFFECT_KEYWORDS = ["до", "после", "эффект", "результат", "сразу", "мгновенно"]
RECOVERY_KEYWORDS = ["восстанов", "перезаряд", "солнц", "промы", "освеж"]
CONSUMABLE_KEYWORDS = ["запах", "поглощ", "абсорб", "одноразов", "сменный", "расходн"]
N_PACK_PATTERN = re.compile(r"(?:набор|комплект|упаковк|в\s*наборе)[^\d]{0,15}(\d+)\s*шт", re.IGNORECASE)
QTY_INLINE_PATTERN = re.compile(r"\b(\d+)\s*шт\b", re.IGNORECASE)


def infer_axes(sku: dict) -> dict:
    """主入口：从 standard_sku.json 推 11 axes + 衍生 flags。"""
    overrides = sku.get("product_axes_override", {}) or {}

    # 基础信息
    category = sku.get("category", "")
    title_ru = sku.get("title_ru", "") or sku.get("product_name_ru", "")
    desc_en = sku.get("product_desc_en", "")
    benefits = sku.get("benefits_ru", [])
    features = sku.get("features_ru", [])
    search_terms = sku.get("search_terms_ru", "") or ""
    all_text_ru = " ".join([title_ru, *benefits, *features]).lower()

    archetype = overrides.get("archetype") or CATEGORY_TO_ARCHETYPE.get(category, "lifestyle-accessory")

    # 核心 11 axes
    axes = {
        "archetype": archetype,
        "use_complexity": _infer_use_complexity(all_text_ru, archetype),
        "effect_visibility": _infer_effect_visibility(all_text_ru, archetype),
        "scene_breadth": _infer_scene_breadth(benefits, search_terms),
        "has_strong_metric": _has_strong_metric(features + benefits),
        "tactile_value": _infer_tactile_value(archetype, desc_en),
        "lifestyle_value": _infer_lifestyle_value(archetype),
        "pack_count": _infer_pack_count(all_text_ru),
        "durability_centrality": _infer_durability(benefits, archetype),
        "is_consumable": archetype == "consumable" or any(k in all_text_ru for k in CONSUMABLE_KEYWORDS),
        "competitor_pressure": overrides.get("competitor_pressure", "medium"),  # 无信号默认中
    }

    # 衍生 flags（slot triggers 用）
    metric_match = METRIC_PATTERN.search(" ".join(features + benefits))
    metric_value = f"{metric_match.group(1)} {metric_match.group(2).upper()}" if metric_match else ""

    derived = {
        "precision_critical": axes["archetype"] in ("auto-part", "tool") and axes["has_strong_metric"],
        "components_gt_1": _count_components(desc_en, all_text_ru) > 1,
        "callout_points": min(6, len([f for f in features if 5 < len(f) < 80])),
        "mechanism_recoverable": axes["is_consumable"] and any(k in all_text_ru for k in RECOVERY_KEYWORDS),
        "core_selling_axis": _infer_core_axis(benefits, axes),
        "metric_value": metric_value,
        "material_style": _infer_material_style(desc_en, archetype),
        "target_user_warmth": _infer_user_warmth(archetype, search_terms),
    }

    # apply remaining overrides
    for k, v in overrides.items():
        if k in axes:
            axes[k] = v
        elif k in derived:
            derived[k] = v

    axes.update(derived)
    return axes


def _infer_use_complexity(text: str, archetype: str) -> str:
    if archetype in ("auto-part",):
        return "multi-step"
    step_signals = ["шаг", "этап", "снимите", "приклейте", "вставьте", "подключите", "закрепите"]
    if sum(1 for s in step_signals if s in text) >= 2:
        return "multi-step"
    return "one-step"


def _infer_effect_visibility(text: str, archetype: str) -> str:
    if archetype not in ("cosmetic-care", "consumable"):
        return "none"
    if sum(1 for k in EFFECT_KEYWORDS if k in text) >= 2:
        return "strong-before-after"
    if archetype == "cosmetic-care":  # 美容/护理默认有可见效果
        return "strong-before-after"
    return "none"


def _infer_scene_breadth(benefits: list[str], search_terms: str) -> str:
    # 优先 multi-material（材料/任务种类更具体）；audience 是次要信号
    material_signals = ["бумаг", "ткан", "плёнк", "картон", "кож", "резин", "пластик", "обои", "коробк", "винил"]
    material_count = sum(1 for s in material_signals if s in " ".join(benefits).lower())
    if material_count >= 3:
        return "multi-material"
    audience_signals = ["мужчин", "женщин", "детск", "семь", "профессион", "школьн", "автомобил", "велосипед", "мотоцикл"]
    audience_count = sum(1 for s in audience_signals if s in (search_terms.lower() + " ".join(benefits).lower()))
    if audience_count >= 3:
        return "multi-audience"
    return "single-scene"


def _has_strong_metric(items: list[str]) -> bool:
    return any(METRIC_PATTERN.search(s) for s in items)


def _infer_tactile_value(archetype: str, desc_en: str) -> str:
    if archetype in ("tool", "cosmetic-care"):
        return "high"
    if "handle" in desc_en.lower() or "grip" in desc_en.lower() or "holder" in desc_en.lower():
        return "high"
    return "low"


def _infer_lifestyle_value(archetype: str) -> str:
    return {
        "tool": "high",
        "cosmetic-care": "high",
        "lifestyle-accessory": "high",
        "consumable": "medium",
        "auto-part": "low",
    }.get(archetype, "medium")


def _infer_pack_count(text: str) -> str:
    m = N_PACK_PATTERN.search(text) or QTY_INLINE_PATTERN.search(text)
    if m and int(m.group(1)) > 1:
        return "n-pack"
    return "single"


def _infer_durability(benefits: list[str], archetype: str) -> str:
    durability_keywords = ["прочн", "надёжн", "долгий", "износ", "срок служб", "сменн", "замен"]
    hits = sum(1 for b in benefits for k in durability_keywords if k in b.lower())
    if hits >= 2 or archetype in ("auto-part", "tool"):
        return "core"
    return "secondary"


def _count_components(desc_en: str, text_ru: str) -> int:
    """很粗略：look for plural component words."""
    component_words = ["blade", "button", "slider", "handle", "ratchet", "лезви", "ползун", "клипс", "ручк"]
    parts = sum(1 for w in component_words if w in (desc_en.lower() + " " + text_ru))
    return max(1, parts)


def _infer_core_axis(benefits: list[str], axes: dict) -> str:
    text = " ".join(benefits).lower()
    score = {
        "spec_performance": 0,
        "multi_use": 0,
        "durability": 0,
        "care_effect": 0,
        "aesthetic": 0,
    }
    if axes["has_strong_metric"]: score["spec_performance"] += 2
    if axes["scene_breadth"] in ("multi-material", "multi-audience"): score["multi_use"] += 2
    if axes["durability_centrality"] == "core": score["durability"] += 2
    if axes["effect_visibility"] == "strong-before-after": score["care_effect"] += 3
    if "стильн" in text or "элегант" in text or "цвет" in text: score["aesthetic"] += 1
    return max(score, key=score.get)


def _infer_material_style(desc_en: str, archetype: str) -> str:
    d = desc_en.lower()
    if any(k in d for k in ["brass", "metal", "shiny", "polished", "chrome", "steel"]) and archetype == "auto-part":
        return "metallic-shiny"
    if any(k in d for k in ["silicone", "transparent", "rubber", "soft", "gel"]):
        return "translucent-soft"
    if any(k in d for k in ["matte", "plastic", "textured"]):
        return "matte-textured"
    if archetype == "cosmetic-care":
        return "polished-metal"
    return "matte-soft"


def _infer_user_warmth(archetype: str, search_terms: str) -> str:
    if archetype == "auto-part":
        return "masculine-rugged"
    if archetype in ("cosmetic-care", "lifestyle-accessory"):
        return "warm-feminine"
    if "мужч" in search_terms.lower():
        return "masculine-rugged"
    return "neutral-pro"


if __name__ == "__main__":
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(description="推断产品 11 个维度（v5.1）")
    ap.add_argument("standard_sku_json", help="standard_sku.json 路径")
    args = ap.parse_args()

    sku = json.loads(open(args.standard_sku_json, encoding="utf-8").read())
    axes = infer_axes(sku)
    print(json.dumps(axes, ensure_ascii=False, indent=2))
