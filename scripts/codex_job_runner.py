#!/usr/bin/env python3
"""Run codex_jobs.jsonl: generate no-text plates, overlay Russian text, and score.

This runner is intentionally thin. Art direction lives in ArtDirectorContract;
this script only executes jobs and records whether the final image actually
passed review.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import critic_gpt4v  # noqa: E402
import report  # noqa: E402
from overlay_text import render_overlay  # noqa: E402

CODEX_BACKEND_DIR = Path.home() / ".config/opencode/skill/ozon-listing-image/scripts"
if CODEX_BACKEND_DIR.exists() and str(CODEX_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(CODEX_BACKEND_DIR))

# image_backend_router fans out across gpt-image-2 (primary) → codex CLI → jiekou.
# Override priority via env IMAGE_BACKEND_ORDER="gptimage,codex,jiekou".
try:
    import image_backend_router as codex_backend  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover - fall back to bare codex_backend if router missing
    try:
        import codex_backend  # type: ignore  # noqa: E402
    except Exception:
        codex_backend = None


def load_jobs(path: Path) -> List[Dict[str, Any]]:
    jobs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            jobs.append(json.loads(line))
    return jobs


def selected_jobs(jobs: List[Dict[str, Any]], slots: str) -> List[Dict[str, Any]]:
    if slots == "all":
        return jobs
    wanted = {s.strip() for s in slots.split(",") if s.strip()}
    return [j for j in jobs if j.get("slot_id") in wanted]


def load_api_key() -> str | None:
    env = os.environ.get("JIEKOU_API_KEY")
    if env:
        return env.strip()
    p = Path.home() / ".config" / "jiekou_api_key"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return None


def abs_out(out_dir: Path, rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    return p if p.is_absolute() else out_dir / p


def build_prompt(job: Dict[str, Any]) -> str:
    prompt = job.get("prompt", "")
    negatives = job.get("negative_prompt") or []
    if negatives:
        prompt += "\n\nNegative requirements:\n" + "\n".join(f"- {x}" for x in negatives)
    return prompt


def error_message(exc: BaseException) -> str:
    if isinstance(exc, SystemExit):
        return str(exc.code) if exc.code is not None else "SystemExit"
    return str(exc)


def scene_grid_product_presence_check(image_path: Path) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Lightweight local guardrail for the office-craft 2x2 usage grid.

    It does not replace human/vision review. It catches the common failure mode
    where the model draws one large black knife across the grid instead of one
    product instance per quadrant.
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return True, [], {"skipped": "Pillow not installed"}

    if not image_path.exists():
        return False, [f"scene-grid local check failed: missing plate {image_path}"], {}

    im = Image.open(image_path).convert("RGB")
    im.thumbnail((420, 560))
    w, h = im.size
    quadrants = [
        ("top-left", (0, int(h * 0.12), int(w * 0.50), int(h * 0.50))),
        ("top-right", (int(w * 0.50), int(h * 0.12), w, int(h * 0.50))),
        ("bottom-left", (0, int(h * 0.50), int(w * 0.50), int(h * 0.90))),
        ("bottom-right", (int(w * 0.50), int(h * 0.50), w, int(h * 0.90))),
    ]

    coverages: Dict[str, float] = {}
    valid = 0
    for name, box in quadrants:
        crop = im.crop(box)
        pixels = list(crop.getdata())
        if not pixels:
            coverages[name] = 0.0
            continue
        # Black utility-knife body pixels are near-neutral and very dark.
        dark = sum(1 for r, g, b in pixels if r < 78 and g < 78 and b < 82 and max(r, g, b) - min(r, g, b) < 34)
        coverage = dark / len(pixels)
        coverages[name] = round(coverage, 4)
        if coverage >= 0.006:
            valid += 1

    if valid >= 4:
        return True, [], {"dark_product_coverage_by_quadrant": coverages}

    return (
        False,
        [
            "scene-grid local check failed: expected a visible black utility knife in all 4 quadrants; "
            f"detected product-like dark coverage in {valid}/4 quadrants ({coverages})"
        ],
        {"dark_product_coverage_by_quadrant": coverages, "valid_quadrants": valid},
    )


def local_acceptance_checks(job: Dict[str, Any], plate: Path, final: Path) -> Tuple[bool, List[str], Dict[str, Any]]:
    slot_id = job.get("slot_id")
    if slot_id == "scene-grid":
        return scene_grid_product_presence_check(plate if plate.exists() else final)
    return True, [], {}


def run_one(
    job: Dict[str, Any],
    contract_path: Path,
    out_dir: Path,
    critic: bool,
    timeout_s: int,
    skip_existing: bool,
) -> Dict[str, Any]:
    slot_id = job["slot_id"]
    plate = abs_out(out_dir, job.get("expected_plate", f"plates/{slot_id}.png"))
    final = abs_out(out_dir, job.get("expected_final", f"final/slot_{slot_id}.png"))
    refs = [Path(p).expanduser().resolve() for p in job.get("reference_images", [])]
    result: Dict[str, Any] = {
        "slot_id": slot_id,
        "output": str(final),
        "plate": str(plate),
        "passed": False,
        "weighted": 0,
        "scores": {},
        "issues": [],
        "elapsed_s": 0,
    }

    t0 = time.time()
    try:
        if not refs:
            raise RuntimeError("job has no reference_images")
        if not skip_existing or not plate.exists():
            if codex_backend is None:
                raise RuntimeError(f"codex_backend not found under {CODEX_BACKEND_DIR}")
            plate.parent.mkdir(parents=True, exist_ok=True)
            gen = codex_backend.generate_one(
                prompt_text=build_prompt(job),
                ref_images=refs,
                out_path=plate,
                size="1024x1536",
                timeout_s=timeout_s,
            )
            if not gen.get("ok"):
                raise RuntimeError(gen.get("error") or "codex generation failed")

        render_overlay(plate, contract_path, slot_id, final, fit_mode="cover", trim_border=True)

        local_ok, local_issues, local_meta = local_acceptance_checks(job, plate, final)
        result["local_checks_passed"] = local_ok
        if local_meta:
            result["local_checks"] = local_meta
        if local_issues:
            result["issues"].extend(local_issues)

        if critic:
            api_key = load_api_key()
            if not api_key:
                result["critic_error"] = "JIEKOU_API_KEY not found"
                result["issues"].append("critic skipped: JIEKOU_API_KEY not found")
            else:
                try:
                    verdict = critic_gpt4v.review(api_key, final, refs[0], slot_id)
                    critic_issues = verdict.get("issues", [])
                    result.update(verdict)
                    if local_issues:
                        result["issues"] = local_issues + critic_issues
                        result["passed"] = False
                        result["local_checks_passed"] = False
                        if local_meta:
                            result["local_checks"] = local_meta
                except (SystemExit, Exception) as e:
                    msg = error_message(e)
                    result["critic_error"] = msg
                    result["issues"].append(f"critic failed: {msg}")
        else:
            result["passed"] = not result["issues"]
    except (SystemExit, Exception) as e:
        result["issues"].append(error_message(e))
    finally:
        result["elapsed_s"] = round(time.time() - t0, 1)

    return result


def write_results(results: List[Dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report.render_markdown(out_dir.name, results, out_dir / "report.md")
    report.render_contact_sheet(results, out_dir / "contact_sheet.jpg")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Silk Life codex_jobs.jsonl")
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--slots", default="all", help="all or comma-separated slot ids")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--critic", action="store_true")
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--skip-existing", action="store_true", help="Reuse existing plates when present")
    args = parser.parse_args()

    jobs = selected_jobs(load_jobs(args.jobs), args.slots)
    if not jobs:
        raise SystemExit("No jobs selected")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ordered: List[Dict[str, Any]] = []
    if args.max_workers <= 1 or len(jobs) == 1:
        for job in jobs:
            print(f"=== {job['slot_id']} ===", flush=True)
            r = run_one(job, args.contract, args.out_dir, args.critic, args.timeout, args.skip_existing)
            print(f"  {'PASS' if r.get('passed') else 'FAIL'} weighted={r.get('weighted', 0)} issues={len(r.get('issues', []))}", flush=True)
            ordered.append(r)
            write_results(ordered, args.out_dir)
    else:
        with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            futures = {
                pool.submit(run_one, job, args.contract, args.out_dir, args.critic, args.timeout, args.skip_existing): i
                for i, job in enumerate(jobs)
            }
            tmp: Dict[int, Dict[str, Any]] = {}
            for fut in as_completed(futures):
                idx = futures[fut]
                tmp[idx] = fut.result()
                print(f"=== {tmp[idx]['slot_id']} done ===", flush=True)
            ordered = [tmp[i] for i in sorted(tmp)]

    write_results(ordered, args.out_dir)
    passed = sum(1 for r in ordered if r.get("passed"))
    print(f"wrote {args.out_dir / 'results.json'}", flush=True)
    print(f"passed {passed}/{len(ordered)}", flush=True)


if __name__ == "__main__":
    main()
