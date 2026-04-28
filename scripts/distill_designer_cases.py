#!/usr/bin/env python3
"""Extract uploaded training zips and build contact sheets for DesignerDelta distillation.

The script expects zips containing:
  沟通图片/
  美工图/ or 美工图片/

It fixes common macOS zip filename mojibake, skips __MACOSX, and creates:
  extracted/
  manifest.json
  contact_sheets/
  art_sheets/
  distillation_index.md
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFont

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def decode_zip_name(name: str) -> str:
    try:
        return name.encode("cp437").decode("utf-8")
    except Exception:
        return name


def safe_extract(zip_path: Path, out_dir: Path) -> int:
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = decode_zip_name(info.filename)
            if (
                name.startswith("__MACOSX/")
                or name.endswith("/")
                or "/._" in name
                or Path(name).name.startswith("._")
                or Path(name).name == ".DS_Store"
            ):
                continue
            parts = [p for p in Path(name).parts if p not in ("..", ".", "")]
            if not parts:
                continue
            dest = out_dir.joinpath(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            count += 1
    return count


def font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def inspect_images(case_dir: Path) -> List[Dict[str, Any]]:
    items = []
    for p in case_dir.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS:
            continue
        rel = p.relative_to(case_dir)
        folder = rel.parts[0] if rel.parts else ""
        try:
            im = Image.open(p)
            w, h = im.size
        except Exception:
            w = h = None
        items.append({
            "path": str(p),
            "rel": str(rel),
            "folder": folder,
            "name": p.name,
            "w": w,
            "h": h,
            "bytes": p.stat().st_size,
        })
    return items


def sort_images(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    import re
    def key(x: Dict[str, Any]):
        nums = [int(n) for n in re.findall(r"\d+", x["name"])]
        return (x["folder"], nums[:2], x["name"])
    return sorted(items, key=key)


def make_grid(items: List[Dict[str, Any]], title: str, out: Path, thumb: int = 180, cols: int = 4) -> None:
    title_font = font(24)
    small_font = font(13)
    pad = 12
    label_h = 42
    title_h = 42
    rows = max(1, math.ceil(len(items) / cols))
    w = cols * (thumb + pad) + pad
    h = title_h + rows * (thumb + label_h + pad) + pad
    canvas = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 8), title, fill=(0, 0, 0), font=title_font)
    for i, item in enumerate(items):
        r, c = i // cols, i % cols
        x = pad + c * (thumb + pad)
        y = title_h + r * (thumb + label_h + pad)
        try:
            im = Image.open(item["path"]).convert("RGB")
            im.thumbnail((thumb, thumb), Image.Resampling.LANCZOS)
            frame = Image.new("RGB", (thumb, thumb), (246, 246, 246))
            frame.paste(im, ((thumb - im.width)//2, (thumb - im.height)//2))
            canvas.paste(frame, (x, y))
        except Exception:
            draw.rectangle((x, y, x+thumb, y+thumb), fill=(230, 230, 230))
        draw.rectangle((x, y, x+thumb, y+thumb), outline=(210, 210, 210))
        label = f"{i+1}. {item['name']}"
        if len(label) > 34:
            label = label[:31] + "..."
        draw.text((x, y + thumb + 3), label, fill=(0, 0, 0), font=small_font)
        dim = f"{item.get('w')}x{item.get('h')}" if item.get("w") else ""
        draw.text((x, y + thumb + 22), dim, fill=(90, 90, 90), font=small_font)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=92)


def make_case_sheets(case: str, items: List[Dict[str, Any]], out_dir: Path) -> Dict[str, str]:
    items = sort_images(items)
    comm = [x for x in items if x["folder"] == "沟通图片"]
    art = [x for x in items if x["folder"].startswith("美工")]
    comm_sheet = out_dir / "contact_sheets" / f"{case}_communication.jpg"
    art_sheet = out_dir / "art_sheets" / f"{case}_designer.jpg"
    make_grid(comm, f"{case} communication images ({len(comm)})", comm_sheet, thumb=160, cols=4)
    make_grid(art, f"{case} designer final images ({len(art)})", art_sheet, thumb=280, cols=4 if len(art) > 8 else 2)
    return {"communication_sheet": str(comm_sheet), "designer_sheet": str(art_sheet)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-zips", nargs="+", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    out = args.out_dir
    if out.exists():
        shutil.rmtree(out)
    (out / "raw").mkdir(parents=True)
    (out / "extracted").mkdir()
    manifest: Dict[str, Any] = {"cases": {}}

    for zstr in args.input_zips:
        z = Path(zstr)
        if not z.exists():
            continue
        shutil.copy2(z, out / "raw" / z.name)
        case_dir = out / "extracted" / z.stem
        case_dir.mkdir(parents=True)
        safe_extract(z, case_dir)
        items = inspect_images(case_dir)
        sheets = make_case_sheets(z.stem, items, out)
        counts: Dict[str, int] = {}
        for item in items:
            counts[item["folder"]] = counts.get(item["folder"], 0) + 1
        manifest["cases"][z.stem] = {
            "zip": z.name,
            "counts": counts,
            "images": [{k: v for k, v in item.items() if k != "path"} for item in items],
            **sheets,
        }

    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Designer Delta Distillation Index", ""]
    for case, data in manifest["cases"].items():
        lines += [
            f"## {case}",
            f"- counts: {data['counts']}",
            f"- communication sheet: {data['communication_sheet']}",
            f"- designer sheet: {data['designer_sheet']}",
            "",
        ]
    (out / "distillation_index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
