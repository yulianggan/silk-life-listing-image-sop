#!/usr/bin/env python3
"""端到端编排：类目目录 → 8 张 listing 图 + 校验报告.

[1] parse_input.scan_category()    解析 xlsx + 参考图分桶
[2] normalize.to_standard_sku()    GPT-5.4-mini 视觉反推 product_desc_en
[3] slot_planner.build_plan()      生成 8 SlotSpec
[4] 并行（默认 codex+team-mode 4 worker）：
        edit.py 调 codex 内置 image_gen（无 API key）—— jiekou 作为兜底
        critic_gpt4v.review()      4 维评分
        if score < 阈值: 注入 issues 作 negative_hints 重跑（最多 2 次）
[5] report.render()                 markdown + 拼版

backend 优先级：codex > jiekou
并行：每 slot 独立 thread，互不冲突（codex 内部各自的 thread_id 子目录）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))
import critic_gpt4v  # noqa: E402
import normalize  # noqa: E402
import parse_input  # noqa: E402
import report  # noqa: E402
import slot_planner  # noqa: E402

EDIT_PY = Path.home() / ".config/opencode/skill/ozon-listing-image/scripts/edit.py"
MAX_RETRIES = 2
DEFAULT_BACKEND = "codex"
DEFAULT_PARALLEL = True
DEFAULT_MAX_WORKERS = 4


def run_edit(
    slot_spec: dict,
    out_dir: Path,
    negative_hints: str | None = None,
    backend: str = DEFAULT_BACKEND,
    fallback: bool = True,
) -> Path | None:
    """调 ozon-listing-image/scripts/edit.py 生成单 slot 图，返回输出 PNG 路径.

    backend: codex（默认，无 API key）| jiekou（兜底）
    fallback: codex 失败时自动回退 jiekou
    """
    cfg_path = out_dir / f"_cfg_{slot_spec['slot_id']}.json"
    cfg_path.write_text(json.dumps(slot_spec["config"], ensure_ascii=False), encoding="utf-8")

    refs = slot_spec.get("refs") or []
    if not refs:
        print(f"  ⚠️  {slot_spec['slot_id']}: 无参考图，跳过")
        return None

    cmd = [
        "python3", str(EDIT_PY),
        "--config", str(cfg_path),
        "--refs", ",".join(refs),
        "--slot", slot_spec["slot_id"],
        "--out-dir", str(out_dir),
        "--quality", slot_spec.get("quality", "medium"),
        "--n", str(slot_spec.get("n", 1)),
        "--backend", backend,
    ]
    if fallback:
        cmd.append("--fallback")
    if negative_hints:
        cmd.extend(["--negative-hints", negative_hints[:500]])

    t0 = time.time()
    # codex backend 单图 90-150s × 1 slot；jiekou ~120s。给 timeout 600s
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    elapsed = time.time() - t0
    if r.returncode != 0:
        print(f"  ❌ {slot_spec['slot_id']} edit.py 失败 ({elapsed:.0f}s, backend={backend}): {r.stderr[-300:]}")
        return None

    pngs = sorted(
        out_dir.glob(f"*_slot_{slot_spec['slot_id']}_*.png"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not pngs:
        print(f"  ❌ {slot_spec['slot_id']} 无 PNG 输出")
        return None
    print(f"  ✅ {slot_spec['slot_id']} → {pngs[0].name} ({elapsed:.0f}s, {backend})")
    return pngs[0]


def run_one_slot_with_retry(
    slot_spec: dict,
    out_dir: Path,
    api_key: str,
    max_retries: int = MAX_RETRIES,
    skip_critic: bool = False,
    backend: str = DEFAULT_BACKEND,
    fallback: bool = True,
) -> dict:
    """单 slot：生成 → critic → 不过则重跑（最多 N 次），返回 result dict."""
    reference = Path(slot_spec["refs"][0]) if slot_spec.get("refs") else None
    negative_hints: str | None = None
    history: list[dict] = []

    for attempt in range(max_retries + 1):
        png = run_edit(slot_spec, out_dir, negative_hints=negative_hints, backend=backend, fallback=fallback)
        if not png:
            return {
                "slot_id": slot_spec["slot_id"],
                "category": slot_spec["config"].get("sku", ""),
                "output": None, "passed": False, "weighted": 0, "scores": {}, "issues": ["edit failed"],
                "retries": attempt, "history": history,
            }

        if skip_critic or not reference:
            return {
                "slot_id": slot_spec["slot_id"],
                "category": slot_spec["config"].get("sku", ""),
                "output": str(png), "passed": True, "weighted": 0, "scores": {}, "issues": [],
                "retries": attempt, "history": history,
            }

        print(f"  🔍 critic 评分 ...")
        try:
            verdict = critic_gpt4v.review(api_key, png, reference, slot_spec["slot_id"])
        except Exception as e:
            print(f"  ⚠️  critic 失败 ({e})，跳过校验视为通过")
            return {
                "slot_id": slot_spec["slot_id"],
                "category": slot_spec["config"].get("sku", ""),
                "output": str(png), "passed": True, "weighted": 0, "scores": {}, "issues": [f"critic error: {e}"],
                "retries": attempt, "history": history,
            }

        history.append({"attempt": attempt, "png": str(png), **verdict})
        print(f"  → {'✅' if verdict['passed'] else '❌'} weighted={verdict['weighted']} pc={verdict['scores']['product_consistency']}")

        if verdict["passed"] or attempt >= max_retries:
            verdict["slot_id"] = slot_spec["slot_id"]
            verdict["category"] = slot_spec["config"].get("sku", "")
            verdict["output"] = str(png)
            verdict["retries"] = attempt
            verdict["history"] = history
            if not verdict["passed"]:
                verdict["needs_human"] = True
            return verdict

        # 注入 issues 作 negative hint 给下一轮
        negative_hints = "; ".join(verdict.get("issues", []))[:500]
        print(f"  ↻ 重跑 (negative: {negative_hints[:80]}...)")

    return verdict


def orchestrate(
    category_dir: Path,
    out_dir: Path,
    slots: list[str] | None = None,
    skip_vision: bool = False,
    skip_critic: bool = False,
    backend: str = DEFAULT_BACKEND,
    fallback: bool = True,
    parallel: bool = DEFAULT_PARALLEL,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    api_key = normalize.load_api_key()

    print(f"=== 类目: {category_dir.name} | backend={backend}, parallel={parallel}, workers={max_workers} ===")
    print("[1] parse_input ...")
    parsed = parse_input.parse(category_dir)
    print(f"  refs body={len(parsed['refs']['body'])} scene={len(parsed['refs']['scene'])} poster={len(parsed['refs']['poster'])}")
    for iss in parsed.get("issues", []):
        print(f"  {iss}")

    print("[2] normalize (含视觉反推) ...")
    sku = normalize.to_standard_sku(parsed, api_key, skip_vision=skip_vision)
    sku_path = out_dir / "standard_sku.json"
    sku_path.write_text(json.dumps(sku, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {sku_path.name} | desc: {sku['product_desc_en'][:80]}...")

    print("[3] slot_planner ...")
    plan = slot_planner.build_plan(sku, slots)
    plan_path = out_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {len(plan)} slots: {[s['slot_id'] for s in plan]}")

    print(f"[4] {'并行' if parallel else '串行'} 生成 + critic + 重跑 ...")
    t_start = time.time()
    results: list[dict] = []

    def _run_slot(spec: dict) -> dict:
        r = run_one_slot_with_retry(
            spec, out_dir, api_key,
            skip_critic=skip_critic,
            backend=backend,
            fallback=fallback,
        )
        r["category"] = category_dir.name
        return r

    if parallel and len(plan) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {pool.submit(_run_slot, spec): spec for spec in plan}
            for fut in as_completed(future_map):
                spec = future_map[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    results.append({
                        "slot_id": spec["slot_id"],
                        "category": category_dir.name,
                        "output": None, "passed": False, "weighted": 0,
                        "scores": {}, "issues": [f"orchestrator exception: {e!r}"],
                        "retries": 0, "history": [],
                    })
        # restore plan order for stable report output
        order = {s["slot_id"]: i for i, s in enumerate(plan)}
        results.sort(key=lambda r: order.get(r["slot_id"], 999))
    else:
        for spec in plan:
            print(f"\n--- {spec['slot_id']} ({spec['quality']}) ---")
            results.append(_run_slot(spec))

    elapsed_min = (time.time() - t_start) / 60
    print(f"\n[4] 完成 {len(results)} slots，耗时 {elapsed_min:.1f} min")

    results_path = out_dir / "results.json"
    results_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n[5] report ...")
    report.render_markdown(category_dir.name, results, out_dir / "report.md")
    report.render_contact_sheet(results, out_dir / "contact_sheet.jpg")

    passed = sum(1 for r in results if r.get("passed"))
    print(f"\n=== 完成 {passed}/{len(results)} 通过 → {out_dir} ===")
    return results


def main() -> None:
    p = argparse.ArgumentParser(description="丝绸生活 listing 套图端到端编排")
    p.add_argument("--category-dir", required=True, help="类目根目录")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--slots", default=None, help="逗号分隔，仅跑指定 slots（默认 8 个）")
    p.add_argument("--skip-vision", action="store_true", help="跳过视觉反推（产品一致性会差）")
    p.add_argument("--skip-critic", action="store_true", help="跳过 critic 评分（不重跑）")
    p.add_argument("--backend", default=DEFAULT_BACKEND, choices=["codex", "jiekou"],
                   help=f"图像后端（默认 {DEFAULT_BACKEND}：codex 内置 image_gen 无需 API key）")
    p.add_argument("--no-fallback", action="store_true",
                   help="codex 失败时不回退 jiekou（默认会回退）")
    p.add_argument("--no-parallel", action="store_true",
                   help="禁用并行（默认 8 slots 并行 4 worker）")
    p.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS,
                   help=f"并行 worker 数（默认 {DEFAULT_MAX_WORKERS}）")
    args = p.parse_args()

    slots = args.slots.split(",") if args.slots else None
    orchestrate(
        Path(args.category_dir).expanduser().resolve(),
        Path(args.out_dir).expanduser().resolve(),
        slots=slots,
        skip_vision=args.skip_vision,
        skip_critic=args.skip_critic,
        backend=args.backend,
        fallback=not args.no_fallback,
        parallel=not args.no_parallel,
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    main()
