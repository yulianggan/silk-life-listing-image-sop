# Add art director contract layer for Silk Life image SOP

## Summary

- Rewrite `SKILL.md` around an explicit art-director decision layer instead of direct prompt-to-image generation.
- Add `ArtDirectorContract` workflow: buyer question → design paradigm → text-free Codex plate prompt → programmatic Russian overlay → critic.
- Add reusable prompts for Claude/Cloud Code, Codex plate generation, and art-director critic review.
- Add design paradigms and rubric templates for stable layout choices.
- Add deterministic scripts:
  - `scripts/art_director_contract.py`
  - `scripts/overlay_text.py`
- Add examples for a refrigerator deodorizer SKU, including a sample contract and overlay output.
- Add a safety/category boundary so restricted categories are marked `needs_human_review` instead of generating automated marketing images.

## Why

The current workflow lets Claude write image prompts directly and asks Codex/image generation to render final Russian text. That makes outputs unstable: product identity drifts, Cyrillic text can become garbled, and layouts do not consistently match the human designer’s commercial decisions.

This PR inserts a stable “美工总监决策层” before image generation. Codex generates only the visual plate and safe text zones; `overlay_text.py` renders final Russian copy with real fonts.

## Test plan

Ran locally on the prepared files:

```bash
python3 -m py_compile scripts/art_director_contract.py scripts/overlay_text.py

python3 scripts/art_director_contract.py   examples/sample_standard_sku.json   --out /tmp/silk_life_art_director_contract_test.json

python3 scripts/overlay_text.py   examples/sample_plate.png   /tmp/silk_life_art_director_contract_test.json   --slot-id hero-product   --out /tmp/silk_life_art_director_overlay_test.png
```

Expected result: contract status is `ok`, 8 slot contracts are generated, and the overlay image is produced successfully.
