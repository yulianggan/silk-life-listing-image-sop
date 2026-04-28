#!/usr/bin/env python3
"""Overlay Russian text from ArtDirectorContract onto a no-text plate image.

Usage:
  python3 scripts/overlay_text.py plate.png art_director_contract.json \
    --slot-id hero-product --out final.png

This script is deliberately simple and deterministic. It prevents AI-generated
garbled Cyrillic by rendering real text with a real font.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/Library/Fonts/Arial.ttf",
]


def find_font(bold: bool = True) -> str | None:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = find_font(bold=bold)
    if font_path:
        return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int, start_size: int, min_size: int = 18) -> ImageFont.ImageFont:
    size = start_size
    while size >= min_size:
        font = load_font(size)
        lines = wrap_text(draw, text, font, max_w)
        bbox = multiline_bbox(draw, lines, font)
        if bbox[2] <= max_w and bbox[3] <= max_h:
            return font
        size -= 2
    return load_font(min_size)


def multiline_bbox(draw: ImageDraw.ImageDraw, lines: List[str], font: ImageFont.ImageFont, spacing: int = 6) -> Tuple[int, int, int, int]:
    widths = []
    heights = []
    for line in lines:
        b = draw.textbbox((0, 0), line, font=font)
        widths.append(b[2] - b[0])
        heights.append(b[3] - b[1])
    return (0, 0, max(widths) if widths else 0, sum(heights) + spacing * max(0, len(lines) - 1))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    words = text.split()
    lines: List[str] = []
    cur = ""
    for word in words:
        trial = word if not cur else f"{cur} {word}"
        b = draw.textbbox((0, 0), trial, font=font)
        if (b[2] - b[0]) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines[:3]


def draw_rounded_label(
    im: Image.Image,
    xy: Tuple[int, int, int, int],
    fill: Tuple[int, int, int, int],
    outline: Tuple[int, int, int, int] | None = None,
    radius: int = 22,
) -> None:
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline)


def draw_text_box(
    im: Image.Image,
    text: str,
    box: Tuple[int, int, int, int],
    fill: Tuple[int, int, int] = (40, 40, 40),
    align: str = "center",
    bg: Tuple[int, int, int, int] | None = None,
    start_size: int = 64,
) -> None:
    if not text:
        return
    if bg:
        draw_rounded_label(im, box, bg, radius=max(12, int((box[2] - box[0]) * 0.04)))
    draw = ImageDraw.Draw(im)
    pad = max(8, int((box[2] - box[0]) * 0.04))
    max_w = box[2] - box[0] - pad * 2
    max_h = box[3] - box[1] - pad * 2
    font = fit_font(draw, text, max_w, max_h, start_size)
    lines = wrap_text(draw, text, font, max_w)
    bbox = multiline_bbox(draw, lines, font)
    y = box[1] + (box[3] - box[1] - bbox[3]) // 2
    for line in lines:
        b = draw.textbbox((0, 0), line, font=font)
        tw = b[2] - b[0]
        if align == "left":
            x = box[0] + pad
        elif align == "right":
            x = box[2] - pad - tw
        else:
            x = box[0] + (box[2] - box[0] - tw) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += (b[3] - b[1]) + 8


def zone_box(w: int, h: int, zone: str) -> Tuple[int, int, int, int]:
    if zone == "top":
        return (int(w*0.06), int(h*0.04), int(w*0.94), int(h*0.18))
    if zone == "side_or_top":
        return (int(w*0.06), int(h*0.18), int(w*0.32), int(h*0.30))
    if zone == "bottom":
        return (int(w*0.08), int(h*0.82), int(w*0.92), int(h*0.92))
    return (int(w*0.08), int(h*0.05), int(w*0.92), int(h*0.18))


def load_contract(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_slot(contract: Dict[str, Any], slot_id: str) -> Dict[str, Any]:
    for slot in contract.get("slot_contracts", []):
        if slot.get("slot_id") == slot_id:
            return slot
    raise SystemExit(f"slot_id not found in contract: {slot_id}")


def render_overlay(plate: Path, contract_path: Path, slot_id: str, out: Path) -> None:
    contract = load_contract(contract_path)
    slot = find_slot(contract, slot_id)
    plan = slot.get("overlay_text_plan", {})

    im = Image.open(plate).convert("RGBA")
    # normalize to vertical 3:4 if needed; do not crop product, pad instead.
    w, h = im.size
    target_ratio = 3 / 4
    if abs((w / h) - target_ratio) > 0.03:
        new_w = w
        new_h = int(w / target_ratio)
        if new_h < h:
            new_h = h
            new_w = int(h * target_ratio)
        canvas = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
        canvas.paste(im, ((new_w - w)//2, (new_h - h)//2))
        im = canvas
        w, h = im.size

    # subtle readability overlay for top title only
    title = plan.get("title", "")
    title_box = zone_box(w, h, plan.get("title_zone", "top"))
    draw_text_box(im, title, title_box, fill=(55, 55, 55), align="center", bg=(255, 255, 255, 170), start_size=int(h*0.065))

    # badges
    for i, badge in enumerate(plan.get("badges", [])):
        text = badge.get("text", "") if isinstance(badge, dict) else str(badge)
        if not text:
            continue
        bx = zone_box(w, h, "side_or_top")
        # stagger multiple badges
        offset = i * int(h * 0.09)
        bx = (bx[0], bx[1] + offset, bx[2], bx[3] + offset)
        draw_text_box(im, text, bx, fill=(255, 255, 255), align="center", bg=(65, 130, 78, 235), start_size=int(h*0.040))

    # dimensions as small right-side labels
    dims = plan.get("dimensions", [])
    if dims:
        for i, dim in enumerate(dims[:4]):
            box = (int(w*0.67), int(h*(0.26 + i*0.08)), int(w*0.94), int(h*(0.32 + i*0.08)))
            draw_text_box(im, str(dim), box, fill=(70,70,70), align="center", bg=(255,255,255,180), start_size=int(h*0.028))

    # steps bottom small labels
    steps = plan.get("steps", [])
    if steps:
        for i, step in enumerate(steps[:3]):
            txt = step.get("caption", f"ШАГ {i+1}") if isinstance(step, dict) else str(step)
            box = (int(w*(0.08 + i*0.30)), int(h*0.82), int(w*(0.28 + i*0.30)), int(h*0.89))
            draw_text_box(im, txt, box, fill=(255,255,255), align="center", bg=(65,130,78,230), start_size=int(h*0.025))

    subtitle = plan.get("subtitle", "")
    if subtitle:
        draw_text_box(im, subtitle, zone_box(w, h, "bottom"), fill=(55,55,55), align="center", bg=(255,255,255,160), start_size=int(h*0.033))

    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out, quality=94)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plate", type=Path)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--slot-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    render_overlay(args.plate, args.contract, args.slot_id, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
