#!/usr/bin/env python3
"""One-command preparation workflow for Silk Life Russian ecommerce listing images.

This script prepares the part that should be deterministic:
  standard_sku.json + optional slot_plan.json
  -> art_director_contract.json
  -> codex_jobs.jsonl
  -> optional overlay of finished no-text plates.

Actual image generation is intentionally delegated to Codex/Cloud Code because
different teams run different image backends. Each job contains the exact
`codex_plate_prompt` that should be sent to Codex.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

# Allow running both as installed script and from repo root.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from art_director_contract import build_contract, load_json  # noqa: E402
from overlay_text import render_overlay  # noqa: E402


def write_jobs(contract: Dict[str, Any], out_dir: Path) -> Path:
    jobs_path = out_dir / "codex_jobs.jsonl"
    with jobs_path.open("w", encoding="utf-8") as f:
        for slot in contract.get("slot_contracts", []):
            job = {
                "slot_id": slot["slot_id"],
                "selected_paradigm": slot["selected_paradigm"],
                "prompt": slot["codex_plate_prompt"],
                "negative_prompt": slot["negative_prompt"],
                "overlay_text_plan": slot["overlay_text_plan"],
                "expected_plate": f"plates/{slot['slot_id']}.png",
                "expected_final": f"final/slot_{slot['slot_id']}.png",
            }
            f.write(json.dumps(job, ensure_ascii=False) + "\n")
    return jobs_path


def overlay_existing_plates(contract_path: Path, contract: Dict[str, Any], plate_dir: Path, out_dir: Path) -> List[Path]:
    finals: List[Path] = []
    final_dir = out_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    for slot in contract.get("slot_contracts", []):
        sid = slot["slot_id"]
        candidates = [
            plate_dir / f"{sid}.png",
            plate_dir / f"plate_{sid}.png",
            plate_dir / f"slot_{sid}.png",
        ]
        plate = next((p for p in candidates if p.exists()), None)
        if not plate:
            continue
        out = final_dir / f"slot_{sid}.png"
        render_overlay(plate, contract_path, sid, out)
        finals.append(out)
    return finals


def run_shell_command(command_template: str, job: Dict[str, Any], out_dir: Path) -> None:
    """Optional backend hook.

    Example:
      --execute-template 'codex exec --prompt-file {prompt_file}'

    The script writes prompt files to out_dir/prompts/{slot_id}.txt and replaces:
      {slot_id}, {prompt_file}, {out_dir}
    """
    prompt_dir = out_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / f"{job['slot_id']}.txt"
    prompt_file.write_text(job["prompt"] + "\n\nNegative:\n" + "\n".join(job["negative_prompt"]), encoding="utf-8")
    cmd = command_template.format(slot_id=job["slot_id"], prompt_file=str(prompt_file), out_dir=str(out_dir))
    subprocess.run(cmd, shell=True, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--standard-sku", type=Path, required=True, help="Path to standard_sku.json")
    parser.add_argument("--slot-plan", type=Path, default=None, help="Optional slot_plan.json")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-slots", type=int, default=8)
    parser.add_argument("--plate-dir", type=Path, default=None, help="If no-text plates already exist, overlay text onto them")
    parser.add_argument("--execute-template", default=None, help="Optional shell template to call Codex for each prompt")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    sku = load_json(args.standard_sku)
    slot_plan = load_json(args.slot_plan) if args.slot_plan else {}
    contract = build_contract(sku, slot_plan, max_slots=args.max_slots)

    contract_path = args.out_dir / "art_director_contract.json"
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    if contract.get("status") != "ready":
        print(f"status={contract.get('status')} reason={contract.get('reason')}")
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
        finals = overlay_existing_plates(contract_path, contract, args.plate_dir, args.out_dir)
        print(f"overlayed {len(finals)} final images")


if __name__ == "__main__":
    main()
