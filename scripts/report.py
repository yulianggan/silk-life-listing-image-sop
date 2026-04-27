#!/usr/bin/env python3
"""生成 report.md（每张图分数+issues+重跑次数）+ contact_sheet.jpg（4×2 拼版）."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

GRID_COLS = 4
GRID_ROWS = 2
THUMB = 400  # 单格缩略宽度


def render_markdown(category: str, results: list[dict], out_md: Path) -> None:
    lines: list[str] = []
    a = lines.append
    a(f"# {category} — 套图生成报告")
    a("")
    passed = sum(1 for r in results if r.get("passed"))
    a(f"**通过 {passed}/{len(results)}** | 加权阈值 7.5 | 产品一致性硬阈值 8.0")
    a("")
    a("| Slot | 状态 | 加权 | 一致性 | 俄语 | 视觉 | CTR | 重跑 | 文件 |")
    a("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in results:
        s = r.get("scores", {})
        status = "✅" if r.get("passed") else ("⚠️ needs_human" if r.get("retries", 0) >= 2 else "❌")
        out = r.get("output") or ""
        fname = Path(out).name if out else "(no output)"
        a(
            f"| {r['slot_id']} | {status} | {r.get('weighted', 0)} | "
            f"{s.get('product_consistency', 0)} | {s.get('cyrillic_render', 0)} | "
            f"{s.get('visual_hierarchy', 0)} | {s.get('ctr_risk', 0)} | "
            f"{r.get('retries', 0)} | `{fname}` |"
        )
    a("")
    a("## Issues 详情")
    a("")
    for r in results:
        if not r.get("issues"):
            continue
        a(f"### {r['slot_id']}")
        for iss in r["issues"]:
            a(f"- {iss}")
        a("")
    out_md.write_text("\n".join(lines), encoding="utf-8")


def render_contact_sheet(results: list[dict], out_jpg: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except ImportError:
        print("⚠️  Pillow 未装，跳过拼版")
        return
    pngs = [Path(r["output"]) for r in results if r.get("output") and Path(r["output"]).exists()]
    if not pngs:
        print("⚠️  无可拼图")
        return

    cell_w, cell_h = THUMB, int(THUMB * 1.5)  # 3:4 比例
    canvas = Image.new("RGB", (cell_w * GRID_COLS, cell_h * GRID_ROWS), (240, 240, 240))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 22)
    except OSError:
        font = ImageFont.load_default()

    for i, r in enumerate(results[: GRID_COLS * GRID_ROWS]):
        col, row = i % GRID_COLS, i // GRID_COLS
        png = Path(r.get("output", ""))
        if not png.exists():
            continue
        img = Image.open(png).convert("RGB")
        img.thumbnail((cell_w, cell_h - 30), Image.LANCZOS)
        x = col * cell_w + (cell_w - img.width) // 2
        y = row * cell_h + 30 + (cell_h - 30 - img.height) // 2
        canvas.paste(img, (x, y))
        label = f"{r['slot_id']} | {'✅' if r.get('passed') else '❌'} {r.get('weighted', 0)}"
        draw.text((col * cell_w + 8, row * cell_h + 4), label, fill=(0, 0, 0), font=font)

    canvas.save(out_jpg, "JPEG", quality=85)


def main() -> None:
    p = argparse.ArgumentParser(description="生成 report.md + contact_sheet.jpg")
    p.add_argument("results_json", help="orchestrate.py 的 results JSON")
    p.add_argument("--out-dir", required=True)
    args = p.parse_args()

    results = json.loads(Path(args.results_json).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    category = results[0].get("category", "unknown") if results else "unknown"

    md_path = out_dir / "report.md"
    sheet_path = out_dir / "contact_sheet.jpg"
    render_markdown(category, results, md_path)
    render_contact_sheet(results, sheet_path)
    print(f"✅ {md_path}")
    print(f"✅ {sheet_path}")


if __name__ == "__main__":
    main()
