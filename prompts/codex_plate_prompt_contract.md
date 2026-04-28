# Codex Plate Prompt Contract

Codex/image generation must receive only the `codex_plate_prompt` from ArtDirectorContract.

The prompt must say:

```text
Create a vertical 3:4 commercial Russian ecommerce product visual plate.
Do NOT render final readable Russian/Cyrillic text.
Leave clean blank zones for overlay title, badge, labels and step numbers.
Use only neutral placeholder shapes such as blank rounded label boxes.
Keep the product exactly like the reference image: same shape, color, package, material, count and key details.
Use this design paradigm: {selected_paradigm}
Use this category palette and mood: {palette}
Composition: {layout_plan}
Visual evidence: {visual_answer}
```

Negative prompt must include:

```text
no final text
no fake Cyrillic
no garbled letters
no extra products
do not change product count
do not change product color
do not change material
do not crop away key product features
no cluttered background
```

After Codex returns the plate, run overlay_text.py. Never ask Codex to draw the final title.
