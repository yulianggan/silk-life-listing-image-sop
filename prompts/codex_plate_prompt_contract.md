# Codex Plate Prompt Contract v3

Codex/image generation must receive only the `codex_plate_prompt` from `ArtDirectorContract`, plus the `reference_images` listed in the same job.

## Mandatory behavior

```text
Use the attached real product reference image(s) as the immutable product anchor.
Do not generate the product from text memory.
Preserve the exact silhouette, length, width, thickness, color, material, package, count, and key structural details.
If the product is long and slim, keep it long and slim. Do not shorten or fatten it.
Create a vertical 3:4 full-bleed Russian ecommerce product visual plate.
Fill the entire canvas edge-to-edge: no side white borders, no gutters, no screenshot frame.
Do NOT render final readable Russian/Cyrillic text.
Do NOT draw placeholder text cards, empty rounded boxes, random UI frames, label outlines, or fake glyphs.
Only leave smooth clean background in overlay safe zones. overlay_text.py will draw all cards and text later.
```

## Required fields in each codex job

```json
{
  "slot_id": "",
  "prompt": "",
  "negative_prompt": [],
  "reference_images": [],
  "product_geometry_lock": {},
  "overlay_text_plan": {},
  "generation_policy": {
    "attach_reference_images_first": true,
    "use_image_edit_or_reference_composite": true,
    "do_not_generate_product_from_text_memory": true,
    "codex_should_not_draw_text_or_placeholder_cards": true,
    "full_bleed_no_side_margins": true
  }
}
```

## Negative prompt must include

```text
no final readable Cyrillic text
no fake glyphs
no placeholder text boxes
no empty rounded label cards
no random UI frames
no side white borders
no left/right empty gutters
do not alter product shape
do not alter product length-to-width ratio
do not make the product shorter, fatter, thicker, or simplified
do not change product color
do not change material
do not change package or count
```

After Codex returns the no-text plate, run `overlay_text.py`. Never ask Codex to draw the final title or the white/green text cards.
