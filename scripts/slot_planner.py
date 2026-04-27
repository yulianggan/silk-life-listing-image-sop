#!/usr/bin/env python3
"""standard_sku.json → 7 个 SlotSpec（喂给 ozon-listing-image/scripts/edit.py）。

每个 SlotSpec 包含：
- slot_id: 7 图位之一
- config: 临时 SKU JSON dict，含 ozon-listing-image schema 必需字段
- refs: 该 slot 的参考图列表（按 color_palette.yaml 的 refs_count）
- quality, n: 调用参数
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
TEMPLATES_DIR = THIS_DIR.parent / "templates"
PALETTE_PATH = TEMPLATES_DIR / "color_palette.yaml"

SLOT_ORDER = [
    "main",
    "detail-size",
    "detail-compare",
    "material",
    "use-scene",
    "hand-demo",
    "package",
    "cert-review",
]

# 每个 slot 用的卖点索引（从 features_ru 取，不够就循环）
SLOT_BENEFIT_MAP = {
    "main": [0],
    "detail-size": [1, 2],
    "detail-compare": [3, 4],
    "material": [5, 6],
    "use-scene": [7, 8],
    "hand-demo": [0, 1],          # 手部演示用第 1 卖点（与 main 一致，强化记忆）
    "package": [9],
    "cert-review": [10, 11],
}


def load_palette() -> dict:
    """读 color_palette.yaml；不依赖 PyYAML（手撸最小解析）。"""
    if not PALETTE_PATH.exists():
        return {}
    try:
        import yaml  # type: ignore
        return yaml.safe_load(PALETTE_PATH.read_text(encoding="utf-8"))
    except ImportError:
        # fallback：硬编码默认（与 yaml 内容同步）
        return {
            "categories": {
                "生活类": {"primary": "mint green #A8E063", "scene": "kitchen"},
                "工具类": {"primary": "deep navy #1B2A4E", "scene": "workbench"},
                "default": {"primary": "mint green #A8E063", "scene": "studio"},
            },
            "slot_defaults": {
                slot: {
                    "quality": "high" if slot == "main" else ("low" if slot == "cert-review" else "medium"),
                    "n": 1,
                    "refs_count": 2 if slot in ("main", "use-scene") else 1,
                }
                for slot in SLOT_ORDER
            },
        }


def select_refs_for_slot(slot: str, refs: dict, n: int) -> list[str]:
    """为某个 slot 选 n 张参考图。

    优先级：body 图（产品本体）必占第 1 张；剩余从 scene/poster 补。
    use-scene 优先用 scene 图；material 优先用最大的 body 图（更可能是细节图）。
    """
    body = list(refs.get("body", []))
    scene = list(refs.get("scene", []))
    poster = list(refs.get("poster", []))

    # 第 1 张永远是产品本体（按文件大小排序，大的更清晰）
    body_sorted = sorted(body, key=lambda p: Path(p).stat().st_size if Path(p).exists() else 0, reverse=True)
    primary = body_sorted[0] if body_sorted else (poster[0] if poster else (scene[0] if scene else None))
    if not primary:
        return []

    out = [primary]
    if n == 1:
        return out

    # 第 2-N 张按 slot 类型选不同源
    if slot in ("use-scene", "hand-demo"):
        candidates = scene + poster + body_sorted[1:]
    elif slot == "material":
        candidates = body_sorted[1:] + poster
    elif slot in ("package", "cert-review"):
        candidates = poster + body_sorted[1:]
    else:
        candidates = poster + scene + body_sorted[1:]

    for p in candidates:
        if p not in out:
            out.append(p)
            if len(out) >= n:
                break
    return out


def build_slot_config(slot: str, sku: dict) -> dict:
    """把 standard_sku.json 字段塑造成 ozon-listing-image edit.py 期待的 SKU config dict.

    edit.py 用 prompts.py 的 build_edit_prompt(slot, config) 渲染 prompt。
    config 字段（详见 ozon-listing-image/scripts/prompts.py 7 个 render_slot_*）：
        product_name_ru, product_subtitle_ru, product_desc_en, category_kind,
        key_spec_ru, key_spec_label_ru, steel_badge_ru,
        features_ru[], materials_ru[],
        compare_ordinary_ru[], compare_us_ru[],
        scenario_props_en,
        size_callouts_ru[], size_tagline_ru,
        material_badge_ru,
        use_scene_tagline_ru,
        package_qty_ru, package_tagline_ru,
        cert_badges_ru[],
    """
    benefits = sku.get("benefits_ru") or []
    features_short = sku.get("features_ru") or []

    # 从原始卖点抽 slot 专用文案（如果有索引就用，没有就用第 0 个 fallback）
    def pick_benefit(idx: int, default: str = "") -> str:
        if idx < len(benefits):
            b = benefits[idx]
            # 取第一句（到第一个分隔符）
            for sep in ["。", ".", "，", ","]:
                if sep in b:
                    return b.split(sep)[0].strip()
            return b[:60]
        return default

    palette = load_palette()
    cat_kind = sku.get("category_kind", "default")
    cat_palette = palette.get("categories", {}).get(cat_kind, {})
    cert_badges = cat_palette.get("badges_ru", ["ХИТ ПРОДАЖ"])

    config = {
        "sku": sku.get("sku") or sku.get("category", "unknown"),
        "category_kind": cat_kind,
        "product_name_ru": sku["product_name_ru"],
        "product_subtitle_ru": sku["product_subtitle_ru"],
        "product_desc_en": sku["product_desc_en"] or "the product shown in the reference image",
        "key_spec_ru": "",  # silk-life xlsx 没有这个，让 prompt 忽略
        "key_spec_label_ru": "",
        "steel_badge_ru": features_short[0] if features_short else "",
        "features_ru": features_short[:3] if features_short else [pick_benefit(0)],
        "materials_ru": [],
        "compare_ordinary_ru": [pick_benefit(3, "Низкое качество"), "Быстро портится", "Неудобно"],
        "compare_us_ru": features_short[:3] if features_short else [pick_benefit(0)],
        "scenario_props_en": cat_palette.get("scene", "clean studio"),

        # silk-life-listing-image-sop 扩展字段（被 prompts.py 7 个 render_slot_* 直接读）
        "size_callouts_ru": [pick_benefit(1)] if benefits else [],
        "size_tagline_ru": "ТОЧНЫЕ РАЗМЕРЫ",
        "material_badge_ru": "ПРЕМИУМ МАТЕРИАЛ",
        "use_scene_tagline_ru": "УДОБНО КАЖДЫЙ ДЕНЬ",
        "package_qty_ru": "x1",
        "package_tagline_ru": "ВЫГОДНЫЙ НАБОР",
        "cert_badges_ru": cert_badges,
    }
    return config


def build_plan(sku: dict, slots: list[str] | None = None) -> list[dict]:
    """生成 SlotSpec 列表."""
    palette = load_palette()
    slot_defaults = palette.get("slot_defaults", {})
    slots = slots or SLOT_ORDER

    plan: list[dict] = []
    refs = sku.get("refs") or {}

    for slot in slots:
        defaults = slot_defaults.get(slot, {"quality": "medium", "n": 1, "refs_count": 1})
        spec = {
            "slot_id": slot,
            "config": build_slot_config(slot, sku),
            "refs": select_refs_for_slot(slot, refs, defaults["refs_count"]),
            "quality": defaults["quality"],
            "n": defaults["n"],
        }
        plan.append(spec)
    return plan


def main() -> None:
    p = argparse.ArgumentParser(description="生成 7 SlotSpec plan")
    p.add_argument("sku_json", help="normalize.py 产出的 standard_sku.json")
    p.add_argument("--slots", default=None, help="逗号分隔，仅生成这些 slot")
    p.add_argument("--out", default=None, help="plan.json 输出路径")
    args = p.parse_args()

    sku = json.loads(Path(args.sku_json).read_text(encoding="utf-8"))
    slots = args.slots.split(",") if args.slots else None
    plan = build_plan(sku, slots)

    out = json.dumps(plan, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"✅ {len(plan)} slots → {args.out}")
        for spec in plan:
            print(f"  - {spec['slot_id']}: {len(spec['refs'])} refs, quality={spec['quality']}, n={spec['n']}")
    else:
        print(out)


if __name__ == "__main__":
    main()
