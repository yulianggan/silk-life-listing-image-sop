#!/usr/bin/env python3
"""One-command preparation workflow for Silk Life Russian ecommerce listing images.

v3 workflow:
  communication folder -> reference_manifest.json
  standard_sku.json + slot_plan.json + reference_manifest.json
  -> art_director_contract.json
  -> codex_jobs.jsonl with reference_images
  -> optional overlay of finished no-text plates.

Actual image generation is delegated to Codex/Cloud Code. Each job contains the
exact prompt plus selected product reference images that must be attached.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from art_director_contract import build_contract, load_json  # noqa: E402
from overlay_text import render_overlay  # noqa: E402
from reference_selector import build_reference_manifest  # noqa: E402


def write_jobs(contract: Dict[str, Any], out_dir: Path) -> Path:
    jobs_path = out_dir / "codex_jobs.jsonl"
    with jobs_path.open("w", encoding="utf-8") as f:
        for slot in contract.get("slot_contracts", []):
            refs = slot.get("layout_plan", {}).get("reference_images") or contract.get("reference_images", [])
            job = {
                "job_version": "2026-04-28-v3-reference-lock",
                "slot_id": slot["slot_id"],
                "selected_paradigm": slot["selected_paradigm"],
                "prompt": slot["codex_plate_prompt"],
                "negative_prompt": slot["negative_prompt"],
                "reference_images": refs,
                "product_geometry_lock": slot.get("layout_plan", {}).get("product_geometry_lock", {}),
                "overlay_text_plan": slot["overlay_text_plan"],
                "generation_policy": {
                    "attach_reference_images_first": True,
                    "use_image_edit_or_reference_composite": True,
                    "do_not_generate_product_from_text_memory": True,
                    "codex_should_not_draw_text_or_placeholder_cards": True,
                    "full_bleed_no_side_margins": True,
                },
                "expected_plate": f"plates/{slot['slot_id']}.png",
                "expected_final": f"final/slot_{slot['slot_id']}.png",
            }
            f.write(json.dumps(job, ensure_ascii=False) + "\n")
    return jobs_path


def overlay_existing_plates(contract_path: Path, contract: Dict[str, Any], plate_dir: Path, out_dir: Path, fit_mode: str) -> List[Path]:
    finals: List[Path] = []
    final_dir = out_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    for slot in contract.get("slot_contracts", []):
        sid = slot["slot_id"]
        candidates = [
            plate_dir / f"{sid}.png",
            plate_dir / f"plate_{sid}.png",
            plate_dir / f"slot_{sid}.png",
            plate_dir / f"{sid}.jpg",
            plate_dir / f"plate_{sid}.jpg",
            plate_dir / f"slot_{sid}.jpg",
        ]
        plate = next((p for p in candidates if p.exists()), None)
        if not plate:
            continue
        out = final_dir / f"slot_{sid}.png"
        render_overlay(plate, contract_path, sid, out, fit_mode=fit_mode, trim_border=True)
        finals.append(out)
    return finals


def run_shell_command(command_template: str, job: Dict[str, Any], out_dir: Path) -> None:
    """Optional backend hook.

    Example:
      --execute-template 'codex exec --prompt-file {prompt_file} --image {reference_image_1}'

    The script writes prompt files to out_dir/prompts/{slot_id}.txt and replaces:
      {slot_id}, {prompt_file}, {out_dir}, {reference_images}, {reference_image_1}
    """
    prompt_dir = out_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / f"{job['slot_id']}.txt"
    prompt_file.write_text(
        job["prompt"] + "\n\nNegative:\n" + "\n".join(job["negative_prompt"]),
        encoding="utf-8",
    )
    refs = job.get("reference_images", [])
    cmd = command_template.format(
        slot_id=job["slot_id"],
        prompt_file=str(prompt_file),
        out_dir=str(out_dir),
        reference_images=" ".join(str(x) for x in refs),
        reference_image_1=str(refs[0]) if refs else "",
    )
    subprocess.run(cmd, shell=True, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--standard-sku", type=Path, required=True, help="Path to standard_sku.json")
    parser.add_argument("--slot-plan", type=Path, default=None, help="Optional slot_plan.json")
    parser.add_argument("--comm-dir", type=Path, default=None, help="Optional 沟通图片 folder; creates reference_manifest.json")
    parser.add_argument("--reference-manifest", type=Path, default=None, help="Existing reference_manifest.json")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-slots", type=int, default=8)
    parser.add_argument("--plate-dir", type=Path, default=None, help="If no-text plates already exist, overlay text onto them")
    parser.add_argument("--fit-mode", choices=["cover", "contain"], default="cover", help="cover removes side gutters")
    parser.add_argument("--execute-template", default=None, help="Optional shell template to call Codex for each prompt")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    sku = load_json(args.standard_sku)
    slot_plan = load_json(args.slot_plan) if args.slot_plan else {}

    reference_manifest: Dict[str, Any] = {}
    ref_path = args.reference_manifest
    if ref_path:
        reference_manifest = load_json(ref_path)
    elif args.comm_dir:
        reference_manifest = build_reference_manifest(args.comm_dir)
        ref_path = args.out_dir / "reference_manifest.json"
        ref_path.write_text(json.dumps(reference_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {ref_path}")

    contract = build_contract(
        sku,
        slot_plan,
        max_slots=args.max_slots,
        reference_manifest=reference_manifest,
    )

    contract_path = args.out_dir / "art_director_contract.json"
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    if contract.get("status") != "ready":
        print(f"wrote {contract_path}")
        print(f"status={contract.get('status')} reason={contract.get('reason')}")
        print("No codex_jobs.jsonl generated for this category.")
        return

    jobs_path = write_jobs(contract, args.out_dir)
    print(f"wrote {contract_path}")
    print(f"wrote {jobs_path}")

    if args.execute_template:
        for line in jobs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            run_shell_command(args.execute_template, json.loads(line), args.out_dir)

    if args.plate_dir:
        finals = overlay_existing_plates(contract_path, contract, args.plate_dir, args.out_dir, fit_mode=args.fit_mode)
        print(f"overlayed {len(finals)} final images")


if __name__ == "__main__":
    main()
