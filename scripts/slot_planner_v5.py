#!/usr/bin/env python3
"""v5.1 slot 选择器：按 product_axes 给 18 个 slot 评分，选 8 张。

算法：
  1. hero-product 必出
  2. 其他 17 个 slot 按 trigger 命中数 + archetype 命中加权打分
  3. score 从高到低取 7 个，加上 hero-product = 8
  4. 最终按 priority（hero=10/scene=20/feature=30/...）排序展示

输入：sku（含 axes）
输出：list[dict]，每个 dict = {slot_id, priority, score, palette, render_template, fields_filled}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml  # PyYAML

import product_axes_inferrer

THIS_DIR = Path(__file__).parent
TEMPLATES_DIR = THIS_DIR.parent / "templates"
SLOT_CATALOG = TEMPLATES_DIR / "slot_catalog.yaml"
PALETTES = TEMPLATES_DIR / "palettes.yaml"

DEFAULT_TARGET_SLOTS = 8


def load_catalog() -> dict:
    return yaml.safe_load(SLOT_CATALOG.read_text(encoding="utf-8"))


def load_palettes() -> dict:
    return yaml.safe_load(PALETTES.read_text(encoding="utf-8"))


def select_palette(axes: dict, palettes: dict) -> str:
    """按 material_style + target_user_warmth 给 3 palette 打分，选最高分。"""
    finish = axes.get("material_style", "matte-soft")
    warmth = axes.get("target_user_warmth", "neutral-pro")
    scored = []
    for pname, p in palettes["palettes"].items():
        s = 0
        if finish in p["matches"].get("product_finish", []):
            s += 2
        if warmth in p["matches"].get("target_user_warmth", []):
            s += 1
        scored.append((pname, s))
    scored.sort(key=lambda x: -x[1])
    if scored[0][1] == 0:
        # 无任何匹配，按 default_priority 第 1 个
        return palettes["default_priority"][0]
    return scored[0][0]


# 评分加权：丝绸生活 brand 实测调整
#   - archetype 命中：+1（不过度偏向某类目下的所有 slot）
#   - lifestyle_value 命中 high：+3（丝绸生活强 lifestyle 风，真人 lifestyle 是核心）
#   - effect_visibility 命中 strong-before-after：+3（美容/护理类核心 hook）
#   - tactile_value=high：+2（手感是触感产品的次要核心）
#   - durability_centrality=core：+2
#   - 其他命中：+1
AXIS_WEIGHTS = {
    "archetype": 1,
    "lifestyle_value": 3,
    "effect_visibility": 3,
    "tactile_value": 2,
    "durability_centrality": 2,
}


def score_slot(slot: dict, axes: dict) -> int:
    """加权评分（v5.1 实测调整）。"""
    if slot["triggers"].get("always"):
        return 1000  # hero 必出
    score = 0
    triggers = slot["triggers"]
    for axis_name, expected_values in triggers.items():
        if axis_name == "always":
            continue
        actual = axes.get(axis_name)
        if actual is None:
            continue
        matched = False
        for ev in expected_values:
            if isinstance(ev, bool) and isinstance(actual, bool) and ev == actual:
                matched = True; break
            if isinstance(ev, int) and isinstance(actual, int) and actual >= ev:
                matched = True; break
            if isinstance(ev, str) and str(actual) == ev:
                matched = True; break
        if matched:
            score += AXIS_WEIGHTS.get(axis_name, 1)
    return score


def select_slots(axes: dict, catalog: dict, target: int = DEFAULT_TARGET_SLOTS) -> list[dict]:
    """主选择：hero-product 必出 + 其他按 score top-(target-1)。"""
    scored = []
    hero = None
    for slot in catalog["slots"]:
        s = score_slot(slot, axes)
        if slot["id"] == "hero-product":
            hero = (slot, s)
        else:
            scored.append((slot, s))
    if hero is None:
        raise ValueError("slot_catalog.yaml 缺 hero-product")

    # 排序：score desc，priority asc（同分时 priority 小的优先）
    scored.sort(key=lambda x: (-x[1], x[0]["priority"]))
    chosen_pool = [hero] + scored[: target - 1]

    # 最终按 priority 排序作展示顺序
    chosen_pool.sort(key=lambda x: x[0]["priority"])
    return [{"slot": s, "score": sc} for s, sc in chosen_pool]


def plan_for_sku(sku: dict, target: int = DEFAULT_TARGET_SLOTS) -> dict:
    """端到端：sku → axes → palette → 8 slot 选择 + 字段填充。"""
    axes = product_axes_inferrer.infer_axes(sku)
    catalog = load_catalog()
    palettes = load_palettes()
    palette_name = select_palette(axes, palettes)
    palette = palettes["palettes"][palette_name]
    chosen = select_slots(axes, catalog, target)
    return {
        "axes": axes,
        "palette_name": palette_name,
        "palette": palette,
        "slots": [
            {
                "slot_id": entry["slot"]["id"],
                "title": entry["slot"]["title"],
                "priority": entry["slot"]["priority"],
                "score": entry["score"],
                "required_fields": entry["slot"].get("required_fields", []),
                "render_template": entry["slot"]["render"],
            }
            for entry in chosen
        ],
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="v5.1 slot planner — 18 候选选 8")
    ap.add_argument("standard_sku_json", help="standard_sku.json 路径")
    ap.add_argument("--target", type=int, default=DEFAULT_TARGET_SLOTS)
    ap.add_argument("--summary-only", action="store_true", help="只打印 slot 选择摘要")
    args = ap.parse_args()

    sku = json.loads(open(args.standard_sku_json, encoding="utf-8").read())
    plan = plan_for_sku(sku, args.target)

    if args.summary_only:
        print(f"=== 类目: {sku.get('category', '?')} | palette: {plan['palette_name']} ===")
        print(f"axes: archetype={plan['axes']['archetype']} | "
              f"effect={plan['axes']['effect_visibility']} | "
              f"metric={plan['axes']['has_strong_metric']} | "
              f"lifestyle={plan['axes']['lifestyle_value']} | "
              f"durability={plan['axes']['durability_centrality']} | "
              f"is_consumable={plan['axes']['is_consumable']}")
        print(f"\n选中 {len(plan['slots'])} slot:")
        for s in plan['slots']:
            print(f"  [{s['priority']:3d}] {s['slot_id']:24s} score={s['score']}")
    else:
        print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))
