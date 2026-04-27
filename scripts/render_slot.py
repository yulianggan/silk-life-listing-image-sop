#!/usr/bin/env python3
"""把 slot_catalog.yaml 的 render template 填上 spec/palette/derived 字段，
输出可直接喂给 codex_backend.generate_one() 的完整 prompt。

字段填充策略（按优先级）：
  1. spec 直接命中（标准 standard_sku.json 字段：product_name_ru, features_ru[i] 等）
  2. spec.slot_overrides[slot_id][field] — 用户手工覆盖
  3. derive_<field>(spec, axes) — 衍生函数
  4. 兜底默认值（slot 模板里 "{field|default}" 语法）

cyrillic_strings 自动 collect 所有出现在 prompt 里的俄文短语，作为 codex prompt 的强制渲染列表。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CYRILLIC_PATTERN = re.compile(r"[А-Яа-яЁё][А-Яа-яЁё\s\d().,;:°№\-/\"'!?ё%]+[А-Яа-яЁё.,;:°)\d]")
PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_slot_prompt(slot: dict, spec: dict, palette: dict, axes: dict) -> str:
    """把 yaml render 模板填充为完整 codex prompt 字符串。"""
    template = slot["render"]

    fields = _collect_fields(slot, spec, palette, axes)

    # 第 1 pass：填充能填的占位符
    rendered = template
    for placeholder in PLACEHOLDER_PATTERN.findall(template):
        value = fields.get(placeholder)
        if value is None:
            value = f"<{placeholder}>"  # leave as marker for codex if missing
        rendered = rendered.replace(f"{{{placeholder}}}", str(value))

    # 第 2 pass：collect 俄文短语作为 cyrillic_strings 注入
    cyrillics = sorted({m.group(0).strip() for m in CYRILLIC_PATTERN.finditer(rendered) if 2 < len(m.group(0).strip()) < 100})
    cyrillic_block = " | ".join(f'"{c}"' for c in cyrillics) if cyrillics else "(none)"
    rendered = rendered.replace("{cyrillic_strings}", cyrillic_block)
    # also fallback for stray {cyrillic_strings} tokens not caught earlier
    rendered = rendered.replace("<cyrillic_strings>", cyrillic_block)

    return rendered


def _collect_fields(slot: dict, spec: dict, palette: dict, axes: dict) -> dict:
    """聚合：palette → spec → slot_overrides → derived。后者覆盖前者。"""
    fields: dict[str, Any] = {}

    # palette 字段
    fields.update({k: v for k, v in palette.items() if k.startswith("palette_")})

    # spec 字段（直接拷贝 standard_sku 的标量字段）
    for k, v in spec.items():
        if isinstance(v, (str, int, float, bool)):
            fields[k] = v

    # spec.derived（来自 axes 的衍生）
    for k in ("metric_value", "core_selling_axis"):
        if k in axes:
            fields[k] = axes[k]

    # slot 级 overrides（spec.slot_overrides[slot_id]）
    overrides = (spec.get("slot_overrides") or {}).get(slot["id"], {})
    fields.update(overrides)

    # 派生字段（per-slot derivation）
    fields.update(_derive_per_slot(slot["id"], spec, palette, axes, fields))

    return fields


def _derive_per_slot(slot_id: str, spec: dict, palette: dict, axes: dict, base: dict) -> dict:
    """每个 slot 的字段计算逻辑（运行时；后续可移到 yaml）。"""
    out: dict[str, Any] = {}
    title_ru = spec.get("product_name_ru", "") or spec.get("title_ru", "")
    features = spec.get("features_ru", []) or []
    metric = axes.get("metric_value", "")

    # hero-product
    if slot_id == "hero-product":
        title_tokens = title_ru.split()
        out["title_top"] = title_tokens[0].upper() if title_tokens else ""
        out["title_main"] = " ".join(title_tokens[1:3]).upper() if len(title_tokens) > 1 else title_ru.upper()
        out["key_spec_ru"] = base.get("key_spec_ru") or metric
        out["key_spec_label_ru"] = base.get("key_spec_label_ru") or _label_for_metric(metric, axes)
        out["steel_badge_ru"] = base.get("steel_badge_ru") or _default_steel_badge(axes)

    # scene-grid-4
    elif slot_id == "scene-grid-4":
        out["scene_grid_title"] = base.get("scene_grid_title") or "УНИВЕРСАЛЬНОЕ ПРИМЕНЕНИЕ"
        labels = base.get("scene_grid_labels") or _default_grid_labels(spec, axes)
        labels = (labels + ["", "", "", ""])[:4]
        out["label_1"], out["label_2"], out["label_3"], out["label_4"] = labels
        out["grid_material_i"] = "; ".join(labels[:4])

    # angle-feature
    elif slot_id == "angle-feature":
        out["feature_metric"] = metric or "30°"
        out["feature_title"] = base.get("feature_title") or f"{out['feature_metric']} — ОПТИМАЛЬНЫЙ ПАРАМЕТР"
        out["feature_subtitle"] = base.get("feature_subtitle") or _short(features[0] if features else "", 80)
        bullets = (features + ["", "", ""])[:3]
        out["bullet_1"], out["bullet_2"], out["bullet_3"] = [_short(b, 40) for b in bullets]

    # ergo-handhold
    elif slot_id == "ergo-handhold":
        out["ergo_title"] = base.get("ergo_title") or "УДОБСТВО ИСПОЛЬЗОВАНИЯ"
        bullets = (features + ["", "", ""])[:3]
        for i, b in enumerate(bullets, start=1):
            out[f"ergo_bullet_{i}"] = _short(b, 60)

    # material-tech
    elif slot_id == "material-tech":
        out["material_title"] = base.get("material_title") or "ВЫСОКОПРОЧНЫЙ МАТЕРИАЛ"
        # 找最长的 feature 当 paragraph
        long_feat = max(features, key=len, default="")
        out["material_paragraph"] = _short(long_feat, 280)

    # before-after
    elif slot_id == "before-after":
        out["before_after_title"] = base.get("before_after_title") or "ВИДИМЫЙ РЕЗУЛЬТАТ"
        out["before_state_desc"] = base.get("before_state_desc") or "subject in untreated state"
        out["after_state_desc"] = base.get("after_state_desc") or "subject improved after product use"
        out["symptom_icons_block"] = base.get("symptom_icons_block") or "(no symptom icons)"

    # product-callouts
    elif slot_id == "product-callouts":
        out["callouts_title"] = base.get("callouts_title") or "КЛЮЧЕВЫЕ ОСОБЕННОСТИ"
        callouts = base.get("callouts") or [{"label": _short(f, 30), "desc": _short(f, 50)} for f in features[:4]]
        out["callouts_block"] = "\n        ".join(
            f"• \"{c['label']}\" — {c['desc']}" for c in callouts
        ) or "(no callouts)"

    # install-steps
    elif slot_id == "install-steps":
        out["install_title"] = base.get("install_title") or "ПРОСТАЯ И БЫСТРАЯ УСТАНОВКА"
        steps = base.get("install_steps") or _default_install_steps(spec, axes)
        out["install_steps_block"] = "\n        ".join(
            f"{i+1}. \"{s}\"" for i, s in enumerate(steps[:3])
        )

    # structure-steps
    elif slot_id == "structure-steps":
        # 取最长的 features 当耐久 caption
        out["structure_caption"] = base.get("structure_caption") or _short(max(features, key=len, default=""), 220)

    # lifestyle-female / -b
    elif slot_id in ("lifestyle-female", "lifestyle-female-b"):
        suffix = "_b" if slot_id.endswith("-b") else ""
        out[f"lifestyle{suffix}_title"] = base.get(f"lifestyle{suffix}_title") or _default_lifestyle_title(slot_id, axes)
        out[f"lifestyle{suffix}_scene_en"] = base.get(f"lifestyle{suffix}_scene_en") or _default_lifestyle_scene(slot_id, spec, axes)

    # audience-fit
    elif slot_id == "audience-fit":
        out["audience_title"] = base.get("audience_title") or "ПОДХОДИТ ДЛЯ"
        segments = base.get("audience_segments") or _default_audience_segments(spec, axes)
        for i, seg in enumerate(segments[:3], start=1):
            out[f"audience_segment_{i}_label"] = seg.get("label", "")
            out[f"audience_segment_{i}_desc"] = seg.get("desc_en", "")
        out["audience_segment_universal_desc"] = (segments[2:3] or [{"desc_en": "family or general use"}])[0]["desc_en"]

    # trust-badge
    elif slot_id == "trust-badge":
        out["trust_top"] = base.get("trust_top") or "НАДЁЖНОЕ КАЧЕСТВО"
        out["trust_bottom"] = base.get("trust_bottom") or "ФАБРИЧНОЕ ПРОИЗВОДСТВО"

    # quantity-pack
    elif slot_id == "quantity-pack":
        # 从 features 提取 N шт
        qty_match = re.search(r"(\d+)\s*шт", " ".join(features))
        out["quantity_value"] = base.get("quantity_value") or (f"{qty_match.group(1)} ШТ" if qty_match else "В НАБОРЕ")
        out["quantity_label"] = base.get("quantity_label") or "УПАКОВКА"

    # vs-competitor
    elif slot_id == "vs-competitor":
        out["competitor_title"] = base.get("competitor_title") or "СРАВНЕНИЕ С ОБЫЧНЫМ"
        neg = base.get("competitor_negative_bullets") or ["✗ Низкое качество", "✗ Быстрый износ", "✗ Неудобно"]
        pos = base.get("competitor_positive_bullets") or [f"✓ {_short(f, 30)}" for f in features[:3]]
        out["competitor_negative_bullets"] = "\n            ".join(f"• {x}" for x in neg)
        out["competitor_positive_bullets"] = "\n            ".join(f"• {x}" for x in pos)

    # icon-feature-grid
    elif slot_id == "icon-feature-grid":
        icons = base.get("icon_features") or [{"label": _short(f, 25)} for f in features[:6]]
        out["icon_features_block"] = "\n        ".join(
            f"• [{ic.get('icon_hint', 'icon')}] \"{ic['label']}\"" for ic in icons
        )

    # mechanism-cycle
    elif slot_id == "mechanism-cycle":
        out["cycle_title"] = base.get("cycle_title") or "СПОСОБ ВОССТАНОВЛЕНИЯ"
        out["cycle_phase_a"] = base.get("cycle_phase_a") or "Эффективен до 6 месяцев"
        out["cycle_phase_b"] = base.get("cycle_phase_b") or "Восстановление на солнце 3-4ч/мес"

    # scene-list-text
    elif slot_id == "scene-list-text":
        out["scene_list_title"] = base.get("scene_list_title") or "ПОДХОДИТ ДЛЯ"
        items = base.get("scene_list_items") or [_short(f, 50) for f in features[:3]]
        out["scene_list_items_block"] = "\n        ".join(f"• {x}" for x in items[:3])

    # dimension-spec
    elif slot_id == "dimension-spec":
        out["dimension_title"] = base.get("dimension_title") or "УНИВЕРСАЛЬНЫЙ РАЗМЕР"
        callouts = base.get("dimension_callouts") or [{"value": metric or "10", "edge": "main dimension"}]
        out["dimension_callouts_block"] = "\n        ".join(
            f"• {c['value']} → {c['edge']}" for c in callouts[:5]
        )

    return out


# helpers
def _short(s: str, n: int) -> str:
    if not s:
        return ""
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s.rfind(" ", 0, n)
    return s[: cut if cut > 5 else n]


def _label_for_metric(metric: str, axes: dict) -> str:
    if not metric:
        return ""
    if "мм" in metric.lower() or "см" in metric.lower():
        return "ШИРИНА" if axes.get("archetype") == "tool" else "РАЗМЕР"
    if "°" in metric:
        return "УГОЛ"
    if "мл" in metric.lower():
        return "ОБЪЁМ"
    return ""


def _default_steel_badge(axes: dict) -> str:
    if axes.get("archetype") == "tool":
        return "ЯПОНСКАЯ СТАЛЬ SK2"
    if axes.get("archetype") == "auto-part":
        return "НАДЁЖНАЯ ФИКСАЦИЯ"
    if axes.get("archetype") == "cosmetic-care":
        return "НЕРЖАВЕЮЩАЯ СТАЛЬ"
    return "ВЫСОКОЕ КАЧЕСТВО"


def _default_grid_labels(spec: dict, axes: dict) -> list[str]:
    """根据 archetype 给 4 个一词标签默认值。"""
    return {
        "tool": ["Бумага", "Картон", "Плёнка", "Упаковка"],
        "cosmetic-care": ["Ногти", "Брови", "Кожа", "Уход"],
        "consumable": ["Холодильник", "Шкаф", "Обувь", "Хранение"],
        "auto-part": ["Авто", "Мото", "Велосипед", "Насос"],
        "lifestyle-accessory": ["Туфли", "Кроссовки", "Дом", "Путешествие"],
    }.get(axes.get("archetype"), ["Применение 1", "Применение 2", "Применение 3", "Применение 4"])


def _default_install_steps(spec: dict, axes: dict) -> list[str]:
    return {
        "auto-part": ["Подключите к насосу", "Закрепите на вентиле колеса", "Приступите к накачиванию"],
        "consumable": ["Снимите защитную плёнку", "Поместите в нужное место", "Используйте по назначению"],
        "lifestyle-accessory": ["Снимите защитную плёнку", "Приклейте на изделие", "Готово к использованию"],
    }.get(axes.get("archetype"), ["Шаг 1", "Шаг 2", "Шаг 3"])


def _default_lifestyle_title(slot_id: str, axes: dict) -> str:
    if slot_id == "lifestyle-female":
        return "ИДЕАЛЬНО ДЛЯ РАБОТЫ"
    return "НЕЗАМЕНИМ В БЫТУ"


def _default_lifestyle_scene(slot_id: str, spec: dict, axes: dict) -> str:
    arch = axes.get("archetype")
    if slot_id == "lifestyle-female":
        return {
            "tool": "opening a cardboard package on her desk near a window",
            "cosmetic-care": "trimming her nails carefully at a vanity table with a mirror",
            "consumable": "placing the product into a clean modern fridge",
            "lifestyle-accessory": "putting on a pair of heels in a bright entryway",
            "auto-part": "examining the part on a clean workbench",
        }.get(arch, "using the product naturally in a bright indoor setting")
    # variant B
    return {
        "tool": "kneeling on the floor, cutting wallpaper or fabric in a home craft setting",
        "cosmetic-care": "applying eyebrow finishing in a bright bathroom",
        "consumable": "rearranging items in a kitchen cabinet, the product visible",
        "lifestyle-accessory": "walking on a city street wearing comfortable everyday shoes",
        "auto-part": "kneeling next to a car tire to demonstrate use",
    }.get(arch, "using the product in a different home/outdoor context")


def _default_audience_segments(spec: dict, axes: dict) -> list[dict]:
    arch = axes.get("archetype")
    return {
        "lifestyle-accessory": [
            {"label": "Туфли", "desc_en": "elegant high-heel shoe"},
            {"label": "Кроссовки", "desc_en": "casual sneaker"},
            {"label": "Все", "desc_en": "family of mixed-age people standing together"},
        ],
        "auto-part": [
            {"label": "Автомобили", "desc_en": "passenger car tire close-up"},
            {"label": "Мотоциклы", "desc_en": "motorcycle wheel"},
            {"label": "Велосипеды", "desc_en": "bicycle wheel"},
        ],
        "cosmetic-care": [
            {"label": "Женщины", "desc_en": "young woman taking care of her hands"},
            {"label": "Мужчины", "desc_en": "man grooming his face"},
            {"label": "Семья", "desc_en": "family group photo"},
        ],
    }.get(arch, [
        {"label": "Случай 1", "desc_en": "use case 1"},
        {"label": "Случай 2", "desc_en": "use case 2"},
        {"label": "Универсально", "desc_en": "universal use"},
    ])


if __name__ == "__main__":
    import argparse
    import json
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    import slot_planner_v5

    ap = argparse.ArgumentParser(description="Render single slot prompt for testing")
    ap.add_argument("standard_sku_json")
    ap.add_argument("--slot", required=True, help="slot_id")
    args = ap.parse_args()

    sku = json.loads(open(args.standard_sku_json, encoding="utf-8").read())
    plan = slot_planner_v5.plan_for_sku(sku)
    target = next((s for s in plan["slots"] if s["slot_id"] == args.slot), None)
    if not target:
        print(f"❌ slot {args.slot} not in plan. Selected slots:")
        for s in plan["slots"]:
            print(f"  - {s['slot_id']}")
        sys.exit(1)
    catalog = slot_planner_v5.load_catalog()
    slot_def = next(s for s in catalog["slots"] if s["id"] == args.slot)
    rendered = render_slot_prompt(slot_def, sku, plan["palette"], plan["axes"])
    print(rendered)
