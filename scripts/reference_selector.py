#!/usr/bin/env python3
"""Select real product reference images from a noisy communication folder.

The communication folder often contains real SKU images, competitor screenshots,
detail pages, scene references, size charts and designer examples. The image
model must not guess the product from text. This script creates a deterministic
reference_manifest.json so Cloud/Codex can attach the correct product refs first.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:
    from PIL import Image, ImageStat
except Exception:  # pragma: no cover - Pillow is optional for metadata only
    Image = None
    ImageStat = None

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

ROLE_KEYWORDS = {
    "product": [
        "product", "main", "hero", "sku", "item", "body", "real", "white",
        "主图", "商品", "产品", "实物", "白底", "主体", "正面", "原图",
    ],
    "package": [
        "pack", "package", "box", "bag", "label", "包装", "盒", "袋", "套装",
    ],
    "detail": [
        "detail", "macro", "close", "zoom", "材质", "细节", "局部", "特写", "尺寸", "size",
    ],
    "size": [
        "size", "dimension", "measure", "spec", "规格", "尺寸", "长度", "宽度", "参数",
    ],
    "scene": [
        "scene", "use", "usage", "lifestyle", "hand", "model", "description",
        "场景", "使用", "手", "人物", "描述", "详情", "安装", "步骤",
    ],
    "competitor": [
        "competitor", "compare", "amazon", "ozon", "wildberries", "1688", "taobao",
        "竞品", "对比", "参考", "截图",
    ],
}

PRODUCT_POSITIVE = set(ROLE_KEYWORDS["product"] + ROLE_KEYWORDS["package"] + ROLE_KEYWORDS["detail"])
PRODUCT_NEGATIVE = set(ROLE_KEYWORDS["scene"] + ROLE_KEYWORDS["competitor"])


def iter_images(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            # Ignore generated designer folders if a full case directory is passed.
            lowered = str(p).lower()
            if any(token in lowered for token in ["美工图", "美工图片", "designer", "final", "contact_sheet"]):
                continue
            yield p


def image_meta(path: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"width": None, "height": None, "ratio": None, "border_mean": None}
    if Image is None:
        return meta
    try:
        im = Image.open(path).convert("RGB")
        w, h = im.size
        meta.update({"width": w, "height": h, "ratio": round(w / h, 4) if h else None})
        # quick border brightness/readability hint
        border = Image.new("RGB", (w, h))
        # Crop strips rather than materializing a mask.
        strips = [
            im.crop((0, 0, w, max(1, h // 40))),
            im.crop((0, h - max(1, h // 40), w, h)),
            im.crop((0, 0, max(1, w // 40), h)),
            im.crop((w - max(1, w // 40), 0, w, h)),
        ]
        vals = []
        for s in strips:
            stat = ImageStat.Stat(s)
            vals.extend(stat.mean)
        meta["border_mean"] = round(sum(vals) / len(vals), 2) if vals else None
    except Exception:
        pass
    return meta


def contains_any(text: str, words: Iterable[str]) -> bool:
    t = text.lower()
    return any(w.lower() in t for w in words)


def classify_roles(path: Path, root: Path) -> List[str]:
    rel = str(path.relative_to(root)).lower()
    roles: List[str] = []
    for role, words in ROLE_KEYWORDS.items():
        if contains_any(rel, words):
            roles.append(role)
    if not roles:
        roles.append("unknown")
    return roles


def product_score(path: Path, root: Path, meta: Dict[str, Any]) -> float:
    rel = str(path.relative_to(root)).lower()
    score = 0.0

    for word in PRODUCT_POSITIVE:
        if word.lower() in rel:
            score += 3.0
    for word in ROLE_KEYWORDS["product"]:
        if word.lower() in rel:
            score += 2.0
    for word in ROLE_KEYWORDS["package"]:
        if word.lower() in rel:
            score += 1.5
    for word in ROLE_KEYWORDS["detail"]:
        if word.lower() in rel:
            score += 1.0
    for word in PRODUCT_NEGATIVE:
        if word.lower() in rel:
            score -= 2.5

    w, h = meta.get("width"), meta.get("height")
    if w and h:
        if min(w, h) >= 700:
            score += 1.0
        if 0.65 <= (w / h) <= 1.55:
            # real product/white background images are often square-ish
            score += 0.8
        if w / h > 2.4 or h / w > 2.4:
            score -= 1.0

    border_mean = meta.get("border_mean")
    if isinstance(border_mean, (int, float)) and border_mean > 210:
        # white or light background often indicates product shot
        score += 0.7

    # Earlier files in a folder are often main product assets.
    nums = [int(x) for x in re.findall(r"\d+", path.stem)[:2]]
    if nums and nums[0] <= 3:
        score += 0.6

    return round(score, 3)


def build_reference_manifest(comm_dir: Path, max_primary: int = 4) -> Dict[str, Any]:
    if not comm_dir.exists():
        raise FileNotFoundError(f"communication folder not found: {comm_dir}")

    images: List[Dict[str, Any]] = []
    role_groups: Dict[str, List[str]] = {k: [] for k in ["product", "package", "detail", "size", "scene", "competitor", "unknown"]}

    for p in sorted(iter_images(comm_dir)):
        meta = image_meta(p)
        roles = classify_roles(p, comm_dir)
        score = product_score(p, comm_dir, meta)
        rel = str(p.relative_to(comm_dir))
        rec = {
            "path": rel,
            "abs_path": str(p.resolve()),
            "roles": roles,
            "product_ref_score": score,
            "meta": meta,
        }
        images.append(rec)
        for r in roles:
            role_groups.setdefault(r, []).append(rel)

    ranked = sorted(images, key=lambda x: x["product_ref_score"], reverse=True)
    primary = []
    for rec in ranked:
        roles = set(rec["roles"])
        if "competitor" in roles and not (roles & {"product", "package"}):
            continue
        if "scene" in roles and rec["product_ref_score"] < 3:
            continue
        primary.append(rec["path"])
        if len(primary) >= max_primary:
            break

    if not primary and ranked:
        primary = [ranked[0]["path"]]

    return {
        "manifest_version": "2026-04-28-v3-reference-lock",
        "communication_dir": str(comm_dir.resolve()),
        "primary_product_refs": primary,
        "primary_product_abs_refs": [str((comm_dir / p).resolve()) for p in primary],
        "role_groups": role_groups,
        "ranked_images": ranked,
        "needs_visual_confirmation": True,
        "vision_instruction": (
            "Before generating any plate, inspect primary_product_refs and confirm they are the real SKU photos. "
            "Use them as immutable product anchors. If a selected reference is a competitor screenshot, scene-only "
            "image, or wrong variant, replace it with a better product/package/detail image from ranked_images."
        ),
        "codex_reference_policy": {
            "mode": "attach_primary_refs_first",
            "required": True,
            "max_refs_per_job": max_primary,
            "do_not_guess_product_from_text": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comm-dir", type=Path, required=True, help="沟通图片 folder")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-primary", type=int, default=4)
    args = parser.parse_args()

    manifest = build_reference_manifest(args.comm_dir, max_primary=args.max_primary)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out} primary_refs={len(manifest['primary_product_refs'])}")


if __name__ == "__main__":
    main()
