#!/usr/bin/env python3
"""Overlay exact Russian text onto a generated visual plate.

The image model should create a text-free plate. This script reads the
`text_overlay_plan` from ArtDirectorContract and draws the final title,
badges, labels, and bullets with a real font.

Usage:
  python3 scripts/overlay_text.py plate.png art_director_contract.json \
    --slot-id hero-product \
    --out slot_hero-product.png \
    --font /path/to/your/Cyrillic-capable-font.ttf \
    --bold-font /path/to/your/Cyrillic-capable-bold-font.ttf
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from PIL import Image, ImageDraw, ImageFont

RGBA = Tuple[int, int, int, int]

# These are only paths to common system fonts. No font file is bundled or shared.
COMMON_REGULAR_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
]
COMMON_BOLD_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]

COLORS = {
    "text_main": (32, 43, 52, 255),
    "text_sub": (75, 85, 99, 255),
    "white": (255, 255, 255, 255),
    "panel": (255, 255, 255, 218),
    "green": (61, 132, 84, 240),
    "green_dark": (31, 99, 61, 255),
    "shadow": (0, 0, 0, 55),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_slot(contract: Dict[str, Any], slot_id: str) -> Dict[str, Any]:
    for slot in contract.get("slot_contracts", []):
        if slot.get("slot_id") == slot_id:
            return slot
    available = [s.get("slot_id") for s in contract.get("slot_contracts", [])]
    raise SystemExit(f"slot_id not found: {slot_id}. Available: {available}")


def resolve_font(path: str | None, candidates: Iterable[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = [path] if path else []
    paths.extend(candidates)
    for p in paths:
        if not p:
            continue
        fp = Path(p).expanduser()
        if fp.exists():
            try:
                return ImageFont.truetype(str(fp), size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def box_px(box: List[float], w: int, h: int) -> Tuple[int, int, int, int]:
    if len(box) != 4:
        raise ValueError(f"box must have 4 numbers, got {box}")
    x, y, bw, bh = box
    # If normalized 0-1, scale; otherwise treat as pixels.
    if 0 <= x <= 1 and 0 <= y <= 1 and 0 < bw <= 1 and 0 < bh <= 1:
        return int(x * w), int(y * h), int((x + bw) * w), int((y + bh) * h)
    return int(x), int(y), int(x + bw), int(y + bh)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    if not text:
        return 0, 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int, max_lines: int) -> List[str]:
    words = text.split()
    if not words:
        return []

    lines: List[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if text_size(draw, candidate, font)[0] <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)

    # Ellipsize last line if needed.
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        last = lines[-1]
        while last and text_size(draw, last + "…", font)[0] > max_w:
            last = last[:-1].rstrip()
        lines[-1] = last + "…" if last else lines[-1]
    return lines


def draw_shadowed_text(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: RGBA,
    shadow: bool = True,
) -> None:
    x, y = xy
    if shadow:
        draw.text((x + 2, y + 3), text, font=font, fill=COLORS["shadow"])
    draw.text((x, y), text, font=font, fill=fill)


def draw_text_block(
    img: Image.Image,
    overlay: Dict[str, Any],
    regular_font_path: str | None,
    bold_font_path: str | None,
) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    x1, y1, x2, y2 = box_px(overlay["box"], w, h)
    pad = max(12, int(min(w, h) * 0.012))
    kind = overlay.get("kind", "text")
    weight = overlay.get("weight", "regular")
    font_size = int(overlay.get("font_size", 36))
    font = resolve_font(
        bold_font_path if weight == "bold" else regular_font_path,
        COMMON_BOLD_FONTS if weight == "bold" else COMMON_REGULAR_FONTS,
        font_size,
    )
    align = overlay.get("align", "left")
    max_lines = int(overlay.get("max_lines", 2))

    if kind in {"badge", "label"}:
        fill = COLORS["green"] if kind == "badge" else COLORS["panel"]
        outline = COLORS["green_dark"] if kind == "badge" else (255, 255, 255, 255)
        radius = int(min(x2 - x1, y2 - y1) * 0.22)
        draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=fill, outline=outline, width=2)
        text_fill = COLORS["white"] if kind == "badge" else COLORS["text_main"]
    elif kind in {"bullets", "caption"}:
        radius = 26
        draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=COLORS["panel"])
        text_fill = COLORS["text_sub"]
    else:
        text_fill = COLORS["text_main"]

    if kind == "bullets":
        items = overlay.get("items") or []
        line_h = int(font_size * 1.25)
        cy = y1 + pad
        for item in items[:max_lines]:
            bullet = f"• {item}"
            lines = wrap_text(draw, bullet, font, x2 - x1 - pad * 2, 2)
            for line in lines:
                draw_shadowed_text(draw, (x1 + pad, cy), line, font, text_fill, shadow=False)
                cy += line_h
        return

    text = str(overlay.get("text", "")).strip()
    lines = wrap_text(draw, text, font, x2 - x1 - pad * 2, max_lines)
    if not lines:
        return

    line_h = int(font_size * 1.14)
    total_h = line_h * len(lines)
    start_y = y1 + max(pad, int((y2 - y1 - total_h) / 2))

    for i, line in enumerate(lines):
        tw, _ = text_size(draw, line, font)
        if align == "center":
            tx = x1 + int((x2 - x1 - tw) / 2)
        elif align == "right":
            tx = x2 - tw - pad
        else:
            tx = x1 + pad
        draw_shadowed_text(draw, (tx, start_y + i * line_h), line, font, text_fill, shadow=(kind == "title"))


def render(image_path: Path, contract_path: Path, slot_id: str, out_path: Path, font: str | None, bold_font: str | None) -> None:
    contract = load_json(contract_path)
    slot = find_slot(contract, slot_id)
    plan = slot.get("text_overlay_plan") or {}
    overlays = plan.get("overlays") or []
    if not overlays:
        raise SystemExit(f"No overlays for slot: {slot_id}")

    img = Image.open(image_path).convert("RGBA")
    # Work on original size; normalized boxes scale automatically.
    for overlay in overlays:
        draw_text_block(img, overlay, font, bold_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, quality=95)


def main() -> None:
    parser = argparse.ArgumentParser(description="Overlay exact Russian text onto a Codex visual plate")
    parser.add_argument("image", type=Path, help="Text-free plate image")
    parser.add_argument("contract", type=Path, help="art_director_contract.json")
    parser.add_argument("--slot-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--font", default=None, help="Regular Cyrillic-capable font path")
    parser.add_argument("--bold-font", default=None, help="Bold Cyrillic-capable font path")
    args = parser.parse_args()
    render(args.image, args.contract, args.slot_id, args.out, args.font, args.bold_font)
    print(f"OK: {args.out}")


if __name__ == "__main__":
    main()
