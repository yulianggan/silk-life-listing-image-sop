#!/usr/bin/env python3
"""V7 communication imagery digest — auto-extract selling points, scene props,
palette, layout archetype from real comm imagery using gpt-5.5 vision.

Usage:
  python3 comm_imagery_digest.py --comm-dir 沟通图片 --out digest.json

Per-image vision call extracts:
  - role: product_ref | designed_poster | usage_scene | spec_diagram | uncertain
  - selling_point_phrases: ["POCKET CLIP", "14.7g LIGHTWEIGHT", ...] (verbatim)
  - scene_props: ["green cutting mat", "ruler", "wallpaper roll", ...]
  - palette: ["black", "yellow accent", "navy"]
  - layout_archetype: hero | feature_callout | scene_grid_4 | spec_diagram | use_demo | trust | uncertain
  - matches_slot: hero-product | size-spec | thin-blades | material-macro | product-callouts | steps-123 | usage-demo | home-salon-scene | none

Cached by content sha256 in ~/.cache/silk-life/comm_digest/<hash>.json — same
image processed once.

Cost: ~$0.05/image, ~15s/image. A typical 沟通图片 dir has ~20 images, so first
run ~$1 / 5 min; subsequent runs free (cached).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_BASE = "http://193.122.147.249:8317/v1"
DEFAULT_KEY_FILE = Path.home() / ".config" / "gpt_image_api_key"
MODEL = os.environ.get("DIGEST_MODEL", "gpt-5.5")
REASONING = os.environ.get("DIGEST_REASONING", "high")
URL = os.environ.get("DIGEST_BASE_URL", DEFAULT_BASE).rstrip("/") + "/chat/completions"
CACHE_DIR = Path.home() / ".cache" / "silk-life" / "comm_digest"

# Filename patterns → likely role hint (model can override)
NAME_HINTS = {
    "product_ref_likely": ["主图_", "主_", "sku 属性图", "sku_", "white"],
    "designed_likely": ["image_", "image-", "img_", "img-", "卖点", "feature"],
    "scene_likely": ["描述图_", "scene", "场景"],
}


SYSTEM_PROMPT = """You are an e-commerce visual analyst. You will see ONE image from a Russian Ozon listing's communication folder. Your job: classify the image's role and extract reusable selling-point phrases, scene props, palette, and layout type so a downstream prompt builder can use this image as either a product reference or a layout/style inspiration.

Categories:

ROLE:
  - "product_ref": clean white/neutral background product shot, no text overlays, no scene props. The pure product is the subject.
  - "designed_poster": already-designed listing poster with text overlays / badges / dramatic background. These are inspiration sources for layout & selling points.
  - "usage_scene": photo showing the product in real use (with hands or work surface). May or may not have text.
  - "spec_diagram": dimension diagram / callout illustration / structural infographic.
  - "lineup_array": multiple instances of the product arranged in array (showcase/inventory shot).
  - "uncertain": cannot classify confidently.

LAYOUT_ARCHETYPE (only fill if role != product_ref):
  - "hero" / "feature_callout" / "scene_grid_4" / "spec_diagram" / "use_demo" / "trust" / "lifestyle" / "lineup" / "uncertain"

MATCHES_SLOT (the silk-life v7 8-slot taxonomy):
  - hero-product / size-spec / thin-blades / material-macro / product-callouts / steps-123 / usage-demo / home-salon-scene / none

Reply ONLY in valid JSON, no markdown:
{
  "role": "<one of above>",
  "layout_archetype": "<one of above or null>",
  "matches_slot": "<v7 slot id or 'none'>",
  "selling_point_phrases": ["<verbatim text from image, source language preserved>", ...],
  "scene_props": ["<concrete props/objects visible in scene>", ...],
  "palette": ["<dominant colors with role>", ...],
  "russian_text_present": <bool>,
  "english_text_present": <bool>,
  "brand_visible": "<brand name or null>",
  "summary_one_line": "<10-20 word summary>",
  "use_for": "<short hint how a v7 prompt builder should use this image>"
}

Example for a 'POCKET CLIP / EASY TO CARRY' poster on black background:
{
  "role": "designed_poster",
  "layout_archetype": "feature_callout",
  "matches_slot": "thin-blades",
  "selling_point_phrases": ["POCKET CLIP", "EASY TO CARRY"],
  "scene_props": ["pocket clip detail closeup", "books with knife clipped on spine"],
  "palette": ["black background", "yellow accent text", "red brand accent"],
  "russian_text_present": false,
  "english_text_present": true,
  "brand_visible": "MANUFORE",
  "summary_one_line": "Designed feature poster highlighting pocket clip and portability with closeup callout",
  "use_for": "Reuse as layout inspiration for thin-blades or new portability slot; translate POCKET CLIP to КАРМАННАЯ КЛИПСА and EASY TO CARRY to УДОБНО НОСИТЬ"
}"""


def _load_key() -> str:
    env = os.environ.get("DIGEST_API_KEY") or os.environ.get("GPT_IMAGE_API_KEY") or os.environ.get("CRITIC_API_KEY")
    if env:
        return env.strip()
    if DEFAULT_KEY_FILE.exists():
        return DEFAULT_KEY_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit(f"❌ API key not found ({DEFAULT_KEY_FILE})")


def _img_to_data_url(p: Path) -> str:
    raw = p.read_bytes()
    suffix = p.suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix, "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _content_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:24]


def _cache_path(image_path: Path) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{_content_hash(image_path)}.json"


def analyze_image(image_path: Path, force: bool = False, max_attempts: int = 3) -> Dict[str, Any]:
    """Vision-call gpt-5.5 to digest one image. Cached by content hash. Transient retry on upstream resets."""
    cache = _cache_path(image_path)
    if cache.exists() and not force:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass

    api_key = _load_key()
    body = {
        "model": MODEL,
        "reasoning_effort": REASONING,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Analyze this comm image (filename: {image_path.name})."},
                    {"type": "image_url", "image_url": {"url": _img_to_data_url(image_path)}},
                ],
            },
        ],
        "max_completion_tokens": 1500,
        "response_format": {"type": "json_object"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False)
        body_path = f.name

    last_err = ""
    try:
        import time as _t
        for attempt in range(max_attempts):
            r = subprocess.run(
                ["curl", "-sS", "--http1.1", "--max-time", "180", URL,
                 "-H", "Content-Type: application/json",
                 "-H", f"Authorization: Bearer {api_key}",
                 "--data-binary", f"@{body_path}"],
                capture_output=True, text=True, timeout=200,
            )
            if r.returncode != 0:
                last_err = f"curl rc={r.returncode}: {r.stderr[:200]}"
                _t.sleep(5 * (attempt + 1))
                continue
            try:
                resp = json.loads(r.stdout)
            except json.JSONDecodeError:
                last_err = f"non-json response: {r.stdout[:200]}"
                _t.sleep(5 * (attempt + 1))
                continue
            if "choices" not in resp or not resp["choices"]:
                err_obj = resp.get("error", {})
                err_msg = err_obj.get("message", "?") if isinstance(err_obj, dict) else str(err_obj)
                # transient — retry
                if any(s in err_msg.lower() for s in ["connection reset", "stream", "timeout", "internal_server_error", "502", "503", "504"]):
                    last_err = f"transient: {err_msg[:200]}"
                    _t.sleep(8 * (attempt + 1))
                    continue
                last_err = f"no choices: {json.dumps(resp)[:200]}"
                break
            content = resp["choices"][0]["message"]["content"].strip()
            try:
                digest = json.loads(content)
            except json.JSONDecodeError:
                if "```" in content:
                    content = content.split("```")[1].lstrip("json").strip()
                    try:
                        digest = json.loads(content)
                    except Exception as e:
                        last_err = f"digest not JSON after stripping: {e}"
                        break
                else:
                    last_err = f"digest not JSON: {content[:200]}"
                    break
            digest["_meta"] = {
                "image_path": str(image_path),
                "image_name": image_path.name,
                "content_hash": _content_hash(image_path),
                "model": MODEL,
                "reasoning_effort": REASONING,
                "attempts": attempt + 1,
            }
            cache.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
            return digest
    finally:
        try:
            os.unlink(body_path)
        except OSError:
            pass

    # All attempts failed — return error digest, do NOT raise (so scan continues)
    return {
        "error": last_err or "unknown failure",
        "_meta": {"image_path": str(image_path), "image_name": image_path.name},
    }


def scan_comm_dir(comm_dir: Path, max_images: int = 30, parallel: int = 1) -> Dict[str, Any]:
    """Scan a comm dir, digest each image, return aggregated dict.

    Aggregated keys:
      - per_image: List[digest dict]
      - primary_refs: List[Path]  — role=product_ref images sorted by name
      - designed_layouts: List[Path] — role=designed_poster images
      - usage_scenes: List[Path]
      - selling_point_phrases: List[str] (deduplicated)
      - scene_props: List[str]
      - palette: List[str]
      - slot_layout_refs: Dict[slot_id, List[image_path]]
    """
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = sorted([p for p in comm_dir.iterdir() if p.suffix.lower() in valid_exts])
    if max_images:
        images = images[:max_images]

    per_image: List[Dict[str, Any]] = []
    if parallel > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futs = {pool.submit(analyze_image, p): p for p in images}
            for fut in as_completed(futs):
                try:
                    per_image.append(fut.result())
                except Exception as e:
                    per_image.append({"_meta": {"image_path": str(futs[fut])}, "error": str(e)[:200]})
    else:
        for p in images:
            try:
                per_image.append(analyze_image(p))
            except Exception as e:
                per_image.append({"_meta": {"image_path": str(p)}, "error": str(e)[:200]})

    primary_refs: List[str] = []
    designed_layouts: List[str] = []
    usage_scenes: List[str] = []
    selling_points: List[str] = []
    scene_props: List[str] = []
    palette: List[str] = []
    slot_layout_refs: Dict[str, List[str]] = {}

    for d in per_image:
        if "error" in d:
            continue
        meta = d.get("_meta", {})
        path = meta.get("image_path", "")
        role = d.get("role")
        if role == "product_ref":
            primary_refs.append(path)
        elif role == "designed_poster":
            designed_layouts.append(path)
        elif role == "usage_scene":
            usage_scenes.append(path)
        for sp in d.get("selling_point_phrases", []) or []:
            sp = (sp or "").strip()
            if sp and sp not in selling_points:
                selling_points.append(sp)
        for prop in d.get("scene_props", []) or []:
            prop = (prop or "").strip()
            if prop and prop not in scene_props:
                scene_props.append(prop)
        for c in d.get("palette", []) or []:
            c = (c or "").strip()
            if c and c not in palette:
                palette.append(c)
        slot = d.get("matches_slot")
        if slot and slot != "none":
            slot_layout_refs.setdefault(slot, []).append(path)

    return {
        "schema_version": "v7_comm_digest_1.0",
        "comm_dir": str(comm_dir),
        "image_count": len(per_image),
        "primary_refs": primary_refs,
        "designed_layouts": designed_layouts,
        "usage_scenes": usage_scenes,
        "selling_point_phrases": selling_points,
        "scene_props": scene_props,
        "palette": palette,
        "slot_layout_refs": slot_layout_refs,
        "per_image": per_image,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="V7 comm imagery digest")
    p.add_argument("--comm-dir", type=Path, help="Required unless --single is used")
    p.add_argument("--out", help="Write JSON to this path")
    p.add_argument("--max-images", type=int, default=30)
    p.add_argument("--parallel", type=int, default=3)
    p.add_argument("--single", help="Analyze a single image instead of scan")
    p.add_argument("--force", action="store_true", help="Bypass cache")
    p.add_argument("--summary", action="store_true", help="Print summary table only")
    args = p.parse_args()

    if args.single:
        d = analyze_image(Path(args.single).expanduser().resolve(), force=args.force)
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return

    if not args.comm_dir:
        raise SystemExit("❌ --comm-dir required (or use --single for one image)")
    digest = scan_comm_dir(args.comm_dir.expanduser().resolve(), max_images=args.max_images, parallel=args.parallel)

    if args.out:
        Path(args.out).write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)

    if args.summary or not args.out:
        print(f"=== Comm imagery digest summary ({digest['image_count']} images) ===")
        print(f"  primary refs:       {len(digest['primary_refs'])}")
        print(f"  designed layouts:   {len(digest['designed_layouts'])}")
        print(f"  usage scenes:       {len(digest['usage_scenes'])}")
        print(f"  selling points:     {len(digest['selling_point_phrases'])}")
        print(f"  scene props:        {len(digest['scene_props'])}")
        print(f"  palette tokens:     {len(digest['palette'])}")
        print(f"  slot layout refs:   {dict((k, len(v)) for k, v in digest['slot_layout_refs'].items())}")
        if digest["selling_point_phrases"]:
            print("\n  Selling points (top 10):")
            for sp in digest["selling_point_phrases"][:10]:
                print(f"    • {sp}")
        if digest["scene_props"]:
            print("\n  Scene props (top 10):")
            for sp in digest["scene_props"][:10]:
                print(f"    • {sp}")


if __name__ == "__main__":
    main()
