#!/usr/bin/env python3
"""Overlay Russian text from ArtDirectorContract onto a no-text plate image.

v3 rules:
- Codex must not draw text cards/placeholders.
- This script owns all title pills, badges, dimension cards, labels and Russian text.
- Default fit is full-bleed cover crop, not padding. This removes side gutters.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/Library/Fonts/Arial.ttf",
]


def find_font(bold: bool = True) -> Optional[str]:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = find_font(bold=bold)
    if font_path:
        return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def multiline_bbox(draw: ImageDraw.ImageDraw, lines: List[str], font: ImageFont.ImageFont, spacing: int = 6) -> Tuple[int, int, int, int]:
    widths = []
    heights = []
    for line in lines:
        b = draw.textbbox((0, 0), line, font=font)
        widths.append(b[2] - b[0])
        heights.append(b[3] - b[1])
    return (0, 0, max(widths) if widths else 0, sum(heights) + spacing * max(0, len(lines) - 1))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int, max_lines: int = 3) -> List[str]:
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
            if len(lines) >= max_lines - 1:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines[:max_lines]


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: int,
    max_h: int,
    start_size: int,
    min_size: int = 16,
    max_lines: int = 3,
) -> ImageFont.ImageFont:
    size = start_size
    while size >= min_size:
        font = load_font(size)
        lines = wrap_text(draw, text, font, max_w, max_lines=max_lines)
        bbox = multiline_bbox(draw, lines, font)
        if bbox[2] <= max_w and bbox[3] <= max_h:
            return font
        size -= 2
    return load_font(min_size)


def trim_uniform_border(im: Image.Image, tolerance: int = 10, max_crop_fraction: float = 0.16) -> Image.Image:
    """Crop a uniform edge border sampled from the top-left corner.

    This helps when a generated image is embedded in a screenshot-like white/black
    frame. The crop is conservative; it will not remove large non-uniform regions.
    """
    rgba = im.convert("RGBA")
    w, h = rgba.size
    if w < 20 or h < 20:
        return im

    bg = Image.new("RGBA", rgba.size, rgba.getpixel((0, 0)))
    diff = ImageChops.difference(rgba, bg).convert("L")
    # Threshold small differences.
    mask = diff.point(lambda p: 255 if p > tolerance else 0)
    bbox = mask.getbbox()
    if not bbox:
        return im

    left, top, right, bottom = bbox
    crop_w = w - (right - left)
    crop_h = h - (bottom - top)
    if crop_w < 4 and crop_h < 4:
        return im
    if crop_w / max(1, w) > max_crop_fraction or crop_h / max(1, h) > max_crop_fraction:
        return im
    return rgba.crop(bbox)


def fit_to_ratio(im: Image.Image, ratio: float = 3 / 4, mode: str = "cover") -> Image.Image:
    w, h = im.size
    cur = w / h
    if abs(cur - ratio) <= 0.01:
        return im

    if mode == "contain":
        new_w, new_h = w, h
        if cur > ratio:
            new_h = int(w / ratio)
        else:
            new_w = int(h * ratio)
        canvas = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
        canvas.paste(im, ((new_w - w) // 2, (new_h - h) // 2))
        return canvas

    # cover crop: never add side gutters
    if cur > ratio:
        target_h = h
        target_w = int(h * ratio)
    else:
        target_w = w
        target_h = int(w / ratio)
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    return ImageOps.fit(im, (target_w, target_h), method=resampling, centering=(0.5, 0.5))


def norm_box_to_px(w: int, h: int, box: Any, fallback: Tuple[float, float, float, float]) -> Tuple[int, int, int, int]:
    if isinstance(box, dict):
        raw = box.get("xywh") or box.get("box") or box.get("rect")
    else:
        raw = box
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raw = fallback
    x, y, bw, bh = [float(v) for v in raw]
    # Treat <= 1.5 as normalized xywh; otherwise pixels.
    if max(abs(x), abs(y), abs(bw), abs(bh)) <= 1.5:
        return (int(w * x), int(h * y), int(w * (x + bw)), int(h * (y + bh)))
    return (int(x), int(y), int(x + bw), int(y + bh))


def style_for(name: str) -> Dict[str, Any]:
    name = (name or "white_card").lower()
    if name == "white_pill":
        return {"bg": (255, 255, 255, 238), "fg": (55, 55, 55), "radius": 30, "outline": None}
    if name == "green_badge":
        return {"bg": (65, 130, 78, 238), "fg": (255, 255, 255), "radius": 18, "outline": None}
    if name == "dark_card":
        return {"bg": (25, 25, 25, 215), "fg": (255, 255, 255), "radius": 16, "outline": (255, 255, 255, 120)}
    if name == "red_outline":
        return {"bg": (25, 25, 25, 70), "fg": (255, 255, 255), "radius": 16, "outline": (230, 30, 30, 220)}
    if name == "transparent":
        return {"bg": None, "fg": (55, 55, 55), "radius": 0, "outline": None}
    return {"bg": (255, 255, 255, 220), "fg": (60, 60, 60), "radius": 16, "outline": None}


def draw_rounded_label(
    im: Image.Image,
    xy: Tuple[int, int, int, int],
    fill: Optional[Tuple[int, int, int, int]],
    outline: Optional[Tuple[int, int, int, int]] = None,
    radius: int = 22,
) -> None:
    if not fill and not outline:
        return
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=2 if outline else 1)


def draw_text_box(
    im: Image.Image,
    text: str,
    box: Tuple[int, int, int, int],
    style_name: str = "white_card",
    align: str = "center",
    start_size: Optional[int] = None,
    max_lines: int = 3,
) -> None:
    text = (text or "").strip()
    if not text:
        return

    style = style_for(style_name)
    x0, y0, x1, y1 = box
    w, h = im.size
    radius = max(10, min(style["radius"], int((y1 - y0) * 0.45))) if style["radius"] else 0
    draw_rounded_label(im, box, style["bg"], outline=style.get("outline"), radius=radius)

    draw = ImageDraw.Draw(im)
    pad_x = max(10, int((x1 - x0) * 0.055))
    pad_y = max(6, int((y1 - y0) * 0.14))
    max_w = max(10, x1 - x0 - pad_x * 2)
    max_h = max(10, y1 - y0 - pad_y * 2)
    if start_size is None:
        start_size = max(18, int((y1 - y0) * 0.52))
    font = fit_font(draw, text, max_w, max_h, start_size=start_size, min_size=14, max_lines=max_lines)
    lines = wrap_text(draw, text, font, max_w, max_lines=max_lines)
    bbox = multiline_bbox(draw, lines, font)
    y = y0 + (y1 - y0 - bbox[3]) // 2
    for line in lines:
        b = draw.textbbox((0, 0), line, font=font)
        tw = b[2] - b[0]
        if align == "left":
            x = x0 + pad_x
        elif align == "right":
            x = x1 - pad_x - tw
        else:
            x = x0 + (x1 - x0 - tw) // 2
        draw.text((x, y), line, font=font, fill=style["fg"])
        y += (b[3] - b[1]) + 8


def zone_box(w: int, h: int, zone: str) -> Tuple[int, int, int, int]:
    if zone == "top":
        return (int(w * 0.06), int(h * 0.04), int(w * 0.94), int(h * 0.165))
    if zone == "side_or_top":
        return (int(w * 0.06), int(h * 0.18), int(w * 0.31), int(h * 0.28))
    if zone == "bottom":
        return (int(w * 0.08), int(h * 0.83), int(w * 0.92), int(h * 0.905))
    return (int(w * 0.08), int(h * 0.05), int(w * 0.92), int(h * 0.18))


def load_contract(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_slot(contract: Dict[str, Any], slot_id: str) -> Dict[str, Any]:
    for slot in contract.get("slot_contracts", []):
        if slot.get("slot_id") == slot_id:
            return slot
    raise SystemExit(f"slot_id not found in contract: {slot_id}")


def _text_from_item(item: Any, keys: Tuple[str, ...] = ("text", "caption", "title", "label")) -> str:
    if isinstance(item, dict):
        for key in keys:
            if item.get(key):
                return str(item[key])
        return ""
    return str(item)


def _style_from_item(item: Any, default: str) -> str:
    if isinstance(item, dict):
        box = item.get("box")
        if isinstance(box, dict) and box.get("style"):
            return str(box["style"])
        if item.get("style"):
            return str(item["style"])
    return default


def _box_from_item(
    item: Any,
    w: int,
    h: int,
    fallback: Tuple[float, float, float, float],
) -> Tuple[int, int, int, int]:
    if isinstance(item, dict):
        return norm_box_to_px(w, h, item.get("box"), fallback)
    return norm_box_to_px(w, h, None, fallback)


def render_overlay(plate: Path, contract_path: Path, slot_id: str, out: Path, fit_mode: str = "cover", trim_border: bool = True) -> None:
    contract = load_contract(contract_path)
    if contract.get("status") != "ready":
        raise SystemExit(f"contract is not ready: {contract.get('status')} {contract.get('reason', '')}")
    slot = find_slot(contract, slot_id)
    plan = slot.get("overlay_text_plan", {})

    im = Image.open(plate).convert("RGBA")
    if trim_border:
        im = trim_uniform_border(im)
    im = fit_to_ratio(im, ratio=3 / 4, mode=fit_mode).convert("RGBA")
    w, h = im.size

    # Title
    title = plan.get("title", "")
    title_box = norm_box_to_px(w, h, plan.get("title_box"), (0.06, 0.04, 0.88, 0.125))
    title_style = "white_pill"
    if isinstance(plan.get("title_box"), dict) and plan["title_box"].get("style"):
        title_style = plan["title_box"]["style"]
    draw_text_box(im, title, title_box, style_name=title_style, start_size=int(h * 0.060), max_lines=2)

    # Badges
    for i, badge in enumerate(plan.get("badges", [])):
        text = _text_from_item(badge)
        if not text:
            continue
        fallback = (0.06, 0.18 + i * 0.09, 0.25, 0.10)
        box = _box_from_item(badge, w, h, fallback)
        draw_text_box(im, text, box, style_name=_style_from_item(badge, "green_badge"), start_size=int(h * 0.038), max_lines=1)

    # Dimensions
    for i, dim in enumerate(plan.get("dimensions", [])[:6]):
        text = _text_from_item(dim)
        if not text:
            continue
        fallback = (0.66, 0.28 + i * 0.08, 0.28, 0.06)
        box = _box_from_item(dim, w, h, fallback)
        draw_text_box(im, text, box, style_name=_style_from_item(dim, "white_card"), start_size=int(h * 0.026), max_lines=2)

    # Steps
    for i, step in enumerate(plan.get("steps", [])[:4]):
        text = _text_from_item(step, keys=("caption", "text", "title"))
        if not text:
            text = f"ШАГ {i + 1}"
        fallback = (0.08 + i * 0.30, 0.82, 0.21, 0.065)
        box = _box_from_item(step, w, h, fallback)
        draw_text_box(im, text, box, style_name=_style_from_item(step, "green_badge"), start_size=int(h * 0.026), max_lines=1)

    # Labels / callouts / bullets
    labels = []
    for key in ("labels", "callouts", "bullets"):
        vals = plan.get(key, [])
        if isinstance(vals, list):
            labels.extend(vals)
    label_defaults = [
        (0.06, 0.30, 0.28, 0.055),
        (0.66, 0.30, 0.28, 0.055),
        (0.06, 0.58, 0.28, 0.055),
        (0.66, 0.58, 0.28, 0.055),
        (0.08, 0.74, 0.84, 0.060),
    ]
    for i, label in enumerate(labels[:8]):
        text = _text_from_item(label)
        if not text:
            continue
        fallback = label_defaults[i] if i < len(label_defaults) else (0.08, 0.74, 0.84, 0.060)
        box = _box_from_item(label, w, h, fallback)
        draw_text_box(im, text, box, style_name=_style_from_item(label, "white_card"), start_size=int(h * 0.023), max_lines=2)

    # Subtitle last (normally bottom strip)
    subtitle = plan.get("subtitle", "")
    if subtitle:
        subtitle_box = norm_box_to_px(w, h, plan.get("subtitle_box"), (0.08, 0.84, 0.84, 0.075))
        subtitle_style = "white_pill"
        if isinstance(plan.get("subtitle_box"), dict) and plan["subtitle_box"].get("style"):
            subtitle_style = plan["subtitle_box"]["style"]
        draw_text_box(im, subtitle, subtitle_box, style_name=subtitle_style, start_size=int(h * 0.033), max_lines=2)

    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out, quality=94)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plate", type=Path)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--slot-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fit-mode", choices=["cover", "contain"], default="cover", help="cover removes side gutters; contain pads")
    parser.add_argument("--no-trim-border", action="store_true")
    args = parser.parse_args()
    render_overlay(args.plate, args.contract, args.slot_id, args.out, fit_mode=args.fit_mode, trim_border=not args.no_trim_border)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
