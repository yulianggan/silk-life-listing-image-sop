#!/usr/bin/env python3
"""V7 codex job runner — fact-driven pipeline with prompt review + critic loop.

Workflow per slot:
  1. build_v7_prompt(sku_truth, slot_id) — assemble fact-grounded prompt
  2. prompt_reviewer.review() — gpt-5.5 high reasoning safety + factuality scrub
  3. image_backend_router.generate_one() — gpt-image-2 edit mode
  4. critic_gpt4v.review() — gpt-5.5 high reasoning quality gate
  5. on fail: re-feed critic issues to prompt_reviewer → retry (≤MAX_ATTEMPTS)

CLI:
  python3 codex_job_runner_v7.py \\
    --listing /path/to/listing_.xlsx \\
    --comm-dir /path/to/沟通图片 \\
    --ref /path/to/main_product_ref.jpg \\
    --out-dir /path/to/output_sop_v7 \\
    [--slots hero-product,size-spec,...]

Output:
  out_dir/sku_truth.yaml
  out_dir/final/slot_*.png
  out_dir/v7_run.json (per-slot diagnostics + critic scores)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Wire to existing modules
import sku_truth_loader  # noqa: E402
import prompt_reviewer  # noqa: E402
import critic_gpt4v  # noqa: E402
from art_director_contract import build_v7_prompt, V7_SLOT_DEFS  # noqa: E402

# Image backend router lives in opencode skill dir
BACKEND_DIR = Path.home() / ".config/opencode/skill/ozon-listing-image/scripts"
if BACKEND_DIR.exists() and str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
try:
    import image_backend_router as image_backend  # type: ignore  # noqa: E402
except Exception:
    try:
        import gptimage_backend as image_backend  # type: ignore  # noqa: E402
    except Exception:
        image_backend = None  # type: ignore

DEFAULT_SLOTS = list(V7_SLOT_DEFS.keys())
MAX_ATTEMPTS = 2  # 1 first try + 1 retry on critic fail
CRITIC_PASS_WEIGHTED = 7.5
CRITIC_PASS_PRODUCT_CONSISTENCY = 8.0
CRITIC_PASS_SLOT_COMPLIANCE = 8.0


def _resize_ref(src: Path, target: tuple[int, int]) -> Path:
    """Letterbox a ref image to (w,h) PNG, return temp path."""
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        raise SystemExit("❌ Need Pillow: pip3 install --user Pillow")
    import tempfile
    img = Image.open(src).convert("RGB")
    tw, th = target
    ratio = min(tw / img.width, th / img.height)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (tw, th), (255, 255, 255))
    canvas.paste(img, ((tw - nw) // 2, (th - nh) // 2))
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    canvas.save(tmp.name, "PNG", optimize=True)
    return Path(tmp.name)


def _critic_passes(verdict: Dict[str, Any]) -> bool:
    if not verdict.get("passed"):
        return False
    scores = verdict.get("scores", {})
    return (
        verdict.get("weighted", 0) >= CRITIC_PASS_WEIGHTED
        and scores.get("product_consistency", 0) >= CRITIC_PASS_PRODUCT_CONSISTENCY
        and scores.get("slot_compliance", 10) >= CRITIC_PASS_SLOT_COMPLIANCE
    )


def _format_critic_issues_as_hints(verdict: Dict[str, Any]) -> str:
    issues = verdict.get("issues", [])[:5]
    if not issues:
        return ""
    return "\n\nNEGATIVE HINTS from prior critic review (avoid these):\n" + "\n".join(f"- {i}" for i in issues)


def run_slot(
    slot_id: str,
    sku_truth: Dict[str, Any],
    sku_truth_summary: str,
    ref_png: Path,
    out_final_dir: Path,
    api_key: str,
    timeout_s: int = 240,
    skip_review: bool = False,
) -> Dict[str, Any]:
    """Execute one slot through review→generate→critic→retry loop."""
    out_path = out_final_dir / f"slot_{slot_id}.png"
    diagnostic: Dict[str, Any] = {
        "slot": slot_id,
        "attempts": [],
        "ok": False,
        "out_path": str(out_path),
    }

    # Step 1: build raw prompt from sku_truth
    raw_prompt = build_v7_prompt(sku_truth, slot_id)
    diagnostic["raw_prompt_chars"] = len(raw_prompt)

    current_prompt = raw_prompt
    last_critic: Optional[Dict[str, Any]] = None
    canvas = sku_truth.get("canvas", {})
    size = canvas.get("size_px", "1200x1600")

    for attempt_idx in range(MAX_ATTEMPTS):
        attempt: Dict[str, Any] = {"i": attempt_idx + 1}

        # Step 2: prompt_reviewer (skip on retry — we already injected critic hints)
        # On reviewer failure: fall back to raw prompt (don't kill the slot)
        if not skip_review and attempt_idx == 0:
            try:
                rev = prompt_reviewer.review(
                    current_prompt,
                    slot_id=slot_id,
                    sku_truth_summary=sku_truth_summary,
                )
                current_prompt = rev.get("improved_prompt") or current_prompt
                attempt["review_verdict"] = rev.get("verdict")
                attempt["review_chars"] = (rev.get("char_count_before"), rev.get("char_count_after"))
                attempt["review_issues"] = rev.get("issues_found", [])[:5]
            except SystemExit as e:
                # prompt_reviewer raises SystemExit on transient endpoint errors.
                # Don't kill the slot — proceed with raw prompt.
                attempt["review_error"] = f"reviewer_systemexit: {str(e)[:200]}"
                attempt["review_verdict"] = "fallback_raw_prompt"
            except Exception as e:
                attempt["review_error"] = f"{type(e).__name__}: {str(e)[:200]}"
                attempt["review_verdict"] = "fallback_raw_prompt"

        # On retry: append last critic's issues as negative hints
        if attempt_idx > 0 and last_critic:
            current_prompt = build_v7_prompt(sku_truth, slot_id) + _format_critic_issues_as_hints(last_critic)
            attempt["retry_hints_from_critic"] = True

        # Step 3: image_gen
        if image_backend is None:
            attempt["error"] = "no image backend available"
            diagnostic["attempts"].append(attempt)
            break
        gen_t0 = time.time()
        gen = image_backend.generate_one(
            prompt_text=current_prompt,
            ref_images=[ref_png],
            out_path=out_path,
            size=size,
            timeout_s=timeout_s,
        )
        attempt["gen_elapsed_s"] = round(time.time() - gen_t0, 1)
        attempt["gen_ok"] = bool(gen.get("ok"))
        attempt["gen_backend"] = gen.get("backend")
        if not gen.get("ok"):
            attempt["error"] = gen.get("error")
            diagnostic["attempts"].append(attempt)
            continue

        # Step 4: critic
        critic_t0 = time.time()
        try:
            verdict = critic_gpt4v.review(api_key, out_path, ref_png, slot_id)
        except SystemExit as e:
            attempt["critic_error"] = str(e)[:200]
            diagnostic["attempts"].append(attempt)
            break
        attempt["critic_elapsed_s"] = round(time.time() - critic_t0, 1)
        attempt["critic_passed"] = bool(verdict.get("passed"))
        attempt["critic_weighted"] = verdict.get("weighted")
        attempt["critic_scores"] = verdict.get("scores")
        attempt["critic_issues"] = verdict.get("issues", [])[:5]
        last_critic = verdict
        diagnostic["attempts"].append(attempt)

        if _critic_passes(verdict):
            diagnostic["ok"] = True
            diagnostic["final_verdict"] = verdict
            break

    if not diagnostic["ok"] and last_critic:
        diagnostic["final_verdict"] = last_critic
    return diagnostic


def main() -> None:
    p = argparse.ArgumentParser(description="V7 fact-driven image pipeline runner")
    p.add_argument("--listing", required=True, type=Path, help="Path to listing.xlsx")
    p.add_argument("--comm-dir", type=Path, help="Path to 沟通图片 dir (for packaging detection)")
    p.add_argument("--ref", required=True, type=Path, help="Path to main product reference image (clean white-bg)")
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--slots", default="all", help="all or comma-separated slot ids")
    p.add_argument("--max-workers", type=int, default=3)
    p.add_argument("--skip-review", action="store_true", help="Skip prompt_reviewer step (cheap-mode)")
    p.add_argument("--timeout", type=int, default=240)
    args = p.parse_args()

    out_dir = args.out_dir.expanduser().resolve()
    final_dir = out_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    # Step 0: build sku_truth
    sku_truth = sku_truth_loader.build_sku_truth(
        args.listing.expanduser().resolve(),
        comm_dir=args.comm_dir.expanduser().resolve() if args.comm_dir else None,
    )
    try:
        import yaml  # type: ignore
        (out_dir / "sku_truth.yaml").write_text(
            yaml.safe_dump(sku_truth, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
    except ImportError:
        (out_dir / "sku_truth.json").write_text(
            json.dumps(sku_truth, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    sku_truth_summary = sku_truth_loader.render_summary(sku_truth)
    print("=== sku_truth ===\n" + sku_truth_summary, flush=True)

    # Auto-skip slots that depend on missing data
    pkg = sku_truth.get("packaging", {})
    auto_skip: List[str] = []
    if not pkg.get("has_real_reference_image"):
        # Don't skip home-salon-scene (it's the no-packaging fallback), but warn
        pass

    slot_ids = DEFAULT_SLOTS if args.slots == "all" else [s.strip() for s in args.slots.split(",") if s.strip()]
    slot_ids = [s for s in slot_ids if s in V7_SLOT_DEFS and s not in auto_skip]
    if not slot_ids:
        raise SystemExit("❌ no valid slots selected")

    canvas = sku_truth.get("canvas", {})
    size_str = canvas.get("size_px", "1200x1600")
    target = tuple(int(x) for x in size_str.lower().split("x"))
    ref_png = _resize_ref(args.ref.expanduser().resolve(), target)
    print(f"=== ref letterboxed to {target} → {ref_png} ===", flush=True)

    api_key = critic_gpt4v.load_api_key()

    print(f"=== running {len(slot_ids)} slot(s) workers={args.max_workers} ===", flush=True)
    results: List[Dict[str, Any]] = []
    if args.max_workers > 1:
        with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            futures = {
                pool.submit(run_slot, s, sku_truth, sku_truth_summary, ref_png, final_dir, api_key, args.timeout, args.skip_review): s
                for s in slot_ids
            }
            for fut in as_completed(futures):
                r = fut.result()
                results.append(r)
                mark = "✓" if r["ok"] else "✗"
                last = r["attempts"][-1] if r["attempts"] else {}
                w = last.get("critic_weighted", "?")
                print(f"  {mark} {r['slot']} attempts={len(r['attempts'])} weighted={w}", flush=True)
    else:
        for s in slot_ids:
            r = run_slot(s, sku_truth, sku_truth_summary, ref_png, final_dir, api_key, args.timeout, args.skip_review)
            results.append(r)
            mark = "✓" if r["ok"] else "✗"
            last = r["attempts"][-1] if r["attempts"] else {}
            w = last.get("critic_weighted", "?")
            print(f"  {mark} {r['slot']} attempts={len(r['attempts'])} weighted={w}", flush=True)

    summary_path = out_dir / "v7_run.json"
    summary_path.write_text(json.dumps({"sku_truth_path": str(out_dir / "sku_truth.yaml"), "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r["ok"])
    print(f"\n{ok}/{len(results)} slot(s) passed; summary → {summary_path}", flush=True)
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
