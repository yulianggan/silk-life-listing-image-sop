#!/usr/bin/env bash
set -euo pipefail

# Run this script from anywhere. It applies the prepared overlay to a local
# clone of yulianggan/silk-life-listing-image-sop, commits it, pushes a branch,
# and creates a PR if the GitHub CLI is authenticated.
#
# Usage:
#   cd /path/to/silk-life-listing-image-sop
#   /path/to/apply_and_create_pr.sh
#
# Optional:
#   BRANCH=feat/art-director-contract-v2 /path/to/apply_and_create_pr.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OVERLAY_DIR="$SCRIPT_DIR/overlay"
BRANCH="${BRANCH:-feat/art-director-contract}"
TITLE="Add art director contract layer for Silk Life image SOP"

if [ ! -d ".git" ]; then
  echo "Error: run this from the root of a local git clone." >&2
  exit 1
fi

if [ ! -f "$OVERLAY_DIR/SKILL.md" ]; then
  echo "Error: overlay files not found at $OVERLAY_DIR" >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Error: no origin remote configured." >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Error: working tree has uncommitted changes. Commit/stash them first." >&2
  git status --short
  exit 1
fi

git fetch origin master
git checkout master
git pull --ff-only origin master
git checkout -b "$BRANCH"

# Apply overlay
cp -R "$OVERLAY_DIR"/. .

git add \
  SKILL.md \
  prompts/art_director_system.md \
  prompts/codex_plate_prompt_contract.md \
  prompts/critic_art_director.md \
  templates/design_paradigms.yaml \
  templates/art_director_rubric.yaml \
  scripts/art_director_contract.py \
  scripts/overlay_text.py \
  examples/sample_standard_sku.json \
  examples/sample_art_director_contract.json \
  examples/sample_plate.png \
  examples/sample_overlay.png

# Local validation
python3 -m py_compile scripts/art_director_contract.py scripts/overlay_text.py
python3 scripts/art_director_contract.py examples/sample_standard_sku.json --out /tmp/silk_life_art_director_contract_test.json >/dev/null
python3 scripts/overlay_text.py examples/sample_plate.png /tmp/silk_life_art_director_contract_test.json --slot-id hero-product --out /tmp/silk_life_art_director_overlay_test.png >/dev/null

git commit -F "$SCRIPT_DIR/COMMIT_MESSAGE.txt"
git push -u origin "$BRANCH"

if command -v gh >/dev/null 2>&1; then
  gh pr create --base master --head "$BRANCH" --title "$TITLE" --body-file "$SCRIPT_DIR/PR_BODY.md"
else
  echo
  echo "Branch pushed: $BRANCH"
  echo "GitHub CLI not found. Open GitHub and create a PR from $BRANCH into master."
fi
