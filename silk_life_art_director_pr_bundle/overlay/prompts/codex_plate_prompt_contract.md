# Codex Plate Prompt Contract

Use this as the final prompt template sent to Codex/image generation for each slot.
The generated image should be a visual plate without final text. Final Russian copy is added later by `overlay_text.py`.

```text
Create a photorealistic e-commerce visual plate for a Russian Ozon product listing.
Canvas: vertical 3:4, 1024x1536px.

REFERENCE LOCK:
Use the supplied product reference as the source of truth. Keep the exact same product silhouette, color, material, quantity, proportions, and key physical details. Do not add extra accessories or change the product into a different item.

DESIGN PARADIGM:
{design_paradigm}

BUYER QUESTION:
{buyer_question}

VISUAL ANSWER:
{visual_answer}

COMPOSITION:
{composition}

TEXT SAFE ZONES:
Reserve clean blank areas for later text overlay: {text_safe_zones}.
Use simple blank rounded rectangles, translucent panels, or empty badge shapes only.
Do NOT render readable Cyrillic or Latin text. Do NOT render fake logos or certification text.

STYLE:
Silk Life listing style: clean commercial product photography, clear hierarchy, soft but high-contrast lighting, green accent badge shapes, generous negative space, professional Ozon thumbnail readability.
Palette intent: {palette_intent}

NEGATIVE PROMPT:
Avoid: unreadable text, random Cyrillic letters, fake certification seals, fake brand logos, extra product parts, wrong material, distorted hands, cluttered collage, tiny paragraphs, dirty colors, low-budget poster look, overdecorated background, cropped product, inconsistent scale.
```

## When to regenerate

Regenerate the plate, not the text overlay, if:

- Product body is wrong.
- Hands/scenes hide the product.
- Text zones are too busy.
- Background fights with product color.
- The image looks like a generic stock photo instead of a product listing plate.

Adjust overlay, not the plate, if:

- Russian text is too long.
- Title hierarchy is weak.
- Badge placement overlaps product.
- Bullet copy needs trimming.
