# V7 Prompt Construction Engineering Specification

## Overview

The v7 prompt builder is a fact-driven, constraint-based system that enforces the user's 5 hard rules through mandatory data validation before slot generation. Unlike previous versions that relied on aesthetic guidelines, v7 implements programmatic gates that **BLOCK** generation when factual requirements are unmet.

## 1. Input Contract

The v7 prompt constructor operates on three mandatory input objects:

### 1.1 sku_truth Object (Required)
```yaml
sku_truth:
  identity:              # Core product identity (required for ALL slots)
    sku_id: string
    product_name_ru: string
    category: enum["tools", "kitchen", "home_storage", "cosmetics", "electronics", "fashion_accessories"]
    archetype: enum["office_craft", "grooming_tool", "kitchen_prep", "home_storage", "beauty_care", "small_electronics", "fashion_accessory"]
  
  dimensions:            # Required for size-spec slot
    length_mm: number?
    width_mm: number?
    height_mm: number?
    blade_length_mm: number?
    weight_g: number?
    source: enum["listing_xlsx", "manual_input", "sku_field", "comm_image_measurement"]
  
  material:             # Required for material-macro slot
    primary: string
    finish: string
    hardness_rating: string?
    source: enum["listing_features", "technical_spec", "manual_input", "comm_image_text"]
  
  use_cases:            # Required for scenario/use slots
    - case_ru: string
      case_zh: string
      source: enum["listing_title", "listing_features", "comm_image_file", "manual_input"]
      context: string?
  
  packaging:            # Required for unboxing slot
    has_real_reference_image: boolean
    reference_files: string[]
    box_color_observed: string?
    box_text_observed: string?
    brand_logo_present: boolean
  
  product_grade_anchor: # Prevents beautification upgrades
    market_segment: enum["budget", "mid-range", "premium"]
    finish_quality_observed: enum["basic", "standard", "fine", "industrial"]
    forbidden_upgrade_keywords: string[]
```

### 1.2 slot_def Object (Required)
```yaml
slot_definition:
  slot_id: string                    # e.g., "hero-identification"
  buyer_question_ru: string          # e.g., "Что это?"
  evidence_type: string              # e.g., "identification"
  required_from_sku_truth: string[]  # Fields that must exist
  blocking_conditions: string[]      # Conditions that block generation
  forbidden_cross_topics: string[]   # Topics this slot cannot address
  composition_constraints: object    # Layout and visual rules
```

### 1.3 Auto-Loaded Profiles (Automatic)
- **material_profile**: Loaded from `c1_material_profiles.yaml` based on `sku_truth.material.primary`
- **design_system**: Static tokens from `c2_design_system.yaml`
- **component_map**: Slot-specific component allowlist from `c2_slot_component_map.yaml`

## 2. Construction Algorithm

### 2.1 Pseudocode Overview
```python
function build_v7_prompt(sku_truth, slot_def):
  # Step 1: Pre-generation validation gate
  validation_result = validate_required_fields(sku_truth, slot_def)
  if validation_result.has_blocking_violations:
      raise BlockSlotGeneration(validation_result.missing_fields)
  
  # Step 2: Identity lock (User Rule #1: Real product fidelity)
  identity_lock = render_identity_lock(
      product_name=sku_truth.identity.product_name_ru,
      archetype=sku_truth.identity.archetype,
      grade_anchor=sku_truth.product_grade_anchor
  )
  
  # Step 3: Slot-specific evidence rules
  slot_rules = render_slot_evidence_rules(slot_def)
  
  # Step 4: Material realism constraints (if applicable)
  material_rules = []
  if sku_truth.material.primary:
      material_profile = load_material_profile(sku_truth.material.primary)
      if material_profile:
          material_rules = render_material_constraints(material_profile)
  
  # Step 5: Component selection and rendering
  allowed_components = get_slot_components(slot_def.slot_id)
  text_components = render_text_components(
      components=allowed_components,
      sku_truth=sku_truth,
      design_system=design_system
  )
  
  # Step 6: Anti-fabrication gates (User Rules #2-4)
  forbidden_clauses = []
  if slot_def.slot_id == "unboxing-scene":
      if not sku_truth.packaging.has_real_reference_image:
          raise BlockSlotGeneration("No real packaging reference")
      forbidden_clauses.append("Only use observed packaging elements")
  
  if "size-spec" in slot_def.slot_id:
      if not sku_truth.dimensions.source:
          raise BlockSlotGeneration("No dimension source attribution")
      forbidden_clauses.append("Only use documented dimensions")
  
  if slot_def.slot_id in ["use-proof", "usage-demo"]:
      if not sku_truth.use_cases:
          raise BlockSlotGeneration("No documented use cases")
      forbidden_clauses.append("Only documented usage scenarios")
  
  # Step 7: Cross-topic isolation (User Rule #5)
  isolation_rules = render_cross_topic_barriers(slot_def.forbidden_cross_topics)
  
  # Step 8: Single product constraint
  product_count_rule = "ONE single product instance only"
  
  # Step 9: Assembly
  return assemble_prompt_sections([
      identity_lock,
      slot_rules,
      material_rules,
      text_components,
      forbidden_clauses,
      isolation_rules,
      product_count_rule
  ])
```

### 2.2 Construction Phases

**Phase 1: Validation Gate**
- Check all `required_from_sku_truth` fields exist and are non-null
- Verify source attributions are traceable
- Block generation if any hard requirements unmet

**Phase 2: Identity Preservation**
- Lock core product identity from `sku_truth.identity`
- Apply grade anchor constraints to prevent artificial upgrading
- Embed forbidden upgrade keywords as negative prompts

**Phase 3: Evidence Constraints**  
- Apply slot-specific evidence rules
- Ensure only appropriate buyer question is answered
- Block cross-topic contamination

**Phase 4: Material Realism**
- Load material profile if metal/plastic/fabric/etc detected
- Apply `must_preserve_features` as positive requirements
- Insert `forbidden_keywords_in_prompt` as negative constraints

**Phase 5: Component Assembly**
- Select allowed components from slot component matrix
- Render text with design system tokens (colors, fonts, spacing)
- Apply component-specific positioning and styling rules

## 3. Missing Field Degradation Behavior

| Missing Field | Affected Slots | Degradation Behavior |
|---|---|---|
| `sku_truth.dimensions.*` | size-spec | **Block slot entirely** — cannot generate without factual measurements |
| `sku_truth.dimensions.source` | size-spec | **Block slot entirely** — no dimension source = fabrication risk |
| `sku_truth.packaging.has_real_reference_image=false` | unboxing-scene | **Block slot entirely** — no fake packaging allowed |
| `sku_truth.packaging.reference_files` empty | unboxing-scene | **Block slot entirely** — no packaging reference = invention |
| `sku_truth.use_cases` empty | use-proof, usage-demo, scene-grid, steps-123 | **Block slots entirely** — cannot invent usage |
| `sku_truth.use_cases[*].source` missing | use-proof, usage-demo | **Block slots entirely** — no traceability = fabrication |
| `sku_truth.material.primary` null | material-macro | **Block slot entirely** — no material facts = guessing |
| `sku_truth.material.source` missing | material-macro | **Block slot entirely** — no material attribution |

### Graceful Degradation Rules
- **7-slot minimum**: If unboxing-scene blocked, safety-trust can be omitted for 7-slot set
- **Alternative angles**: If material-macro blocked, generate additional angle-variant
- **No slot substitution**: Blocked slots are NOT replaced with invented alternatives

## 4. Multi-Category Examples

### 4.1 Category A: Metal Precision Tools (剪刀/美工刀/钳子)

**Example SKU**: Stainless steel beauty scissors
```yaml
sku_truth:
  identity:
    product_name_ru: "Ножницы маникюрные"
    category: "tools"
    archetype: "grooming_tool"
  material:
    primary: "нержавеющая сталь SK2"
    finish: "полированная"
    source: "listing_features"
  use_cases:
    - case_ru: "для бровей"
      source: "listing_title"
    - case_ru: "для носовых волос"
      source: "listing_features"
```

**Generated Prompts**:

*hero-identification*:
```
Vertical 3:4 Russian e-commerce listing image of stainless steel beauty scissors. 
Product identity: Ножницы маникюрные — точный инструмент для персонального ухода. 
ONE single scissors only, polished stainless steel finish, two oval rings, curved blade tip.
Clean white background, navy and soft-green palette.

Text components (design system):
- Top-center title pill (navy bg #1a2b50, white text): "НОЖНИЦЫ МАНИКЮРНЫЕ"  
- Below subtitle (grey #6b7280): "Точный инструмент для персонального ухода"

Material constraints (metal profile):
- FORBIDDEN: luxury, mirror-finish, artisan, sparks, gleaming
- PRESERVE: rivet pin, laser engraving, blade curvature, edge geometry
- Light: soft studio lighting only, no dramatic reflections

Cross-topic isolation:
- FORBIDDEN: dimensional measurements, usage demonstrations, material close-ups
- FOCUS: product identity, basic form recognition only
```

*size-spec*:
```
Vertical 3:4 Russian e-commerce sizing technical shot of the SAME stainless steel beauty scissors.
ONE single scissors, clean neutral background, measurement reference objects.

Factual dimensions (source: listing_xlsx):
- Length: 90mm (sku_truth.dimensions.length_mm)  
- Blade: 35mm (sku_truth.dimensions.blade_length_mm)
- Ring: 20mm (sku_truth.dimensions.ring_opening_mm)

Text components (design system):
- Top-center title pill (navy bg, white text): "РАЗМЕР И ЛЕЗВИЕ"
- Three dimension cards (white bg #ffffff, navy numbers #1a2b50, green units #4a7c59):
  * "90 мм" → full length
  * "35 мм" → blade segment  
  * "20 мм" → ring opening

Cross-topic isolation:
- FORBIDDEN: usage scenarios, material details, construction callouts
- FOCUS: dimensional evidence only
```

*material-macro*:
```
Vertical 3:4 extreme close-up macro of polished stainless steel blade surface.
Material evidence shot - steel grain, cutting edge, surface finish fill 70%+ frame.
Small inset of complete scissors in corner for SKU continuity.

Text components (design system):
- Top-left material spec tag (neutral bg #f8f9fa, navy text): "Нержавеющая сталь SK2"
- Top-right material spec tag: "Полированная поверхность"

Metal realism constraints:
- Surface: actual polished finish quality (not mirror-enhanced)
- Preserve: manufacturing marks, edge geometry, surface scratches
- Light: soft studio only, no sparks/drama
- FORBIDDEN: luxury enhancement, artificial brilliance
```

### 4.2 Category B: Plastic Home Storage (收纳盒/夹子)

**Example SKU**: ABS plastic storage container
```yaml
sku_truth:
  identity:
    product_name_ru: "Контейнер для хранения"  
    category: "home_storage"
    archetype: "home_storage"
  material:
    primary: "пластик ABS"
    finish: "матовая"
    source: "technical_spec"
  dimensions:
    length_mm: 240
    width_mm: 160  
    height_mm: 80
    source: "listing_xlsx"
```

**Key Differences**:
- Material profile: plastic anti-beautification rules
- Forbidden keywords: glassy, piano-finish, lacquer, crystal-clear
- Must preserve: molding seams, surface texture, embossed logos
- Light palette: even_diffused, soft_box, matte_lighting

### 4.3 Category C: Fabric/Soft Materials (毛巾/抹布)

**Example SKU**: Cotton kitchen towel
```yaml
sku_truth:
  identity:
    product_name_ru: "Полотенце кухонное"
    category: "kitchen" 
    archetype: "kitchen_prep"
  material:
    primary: "хлопок 100%"
    finish: "махровая"
    source: "listing_description"
```

**Key Differences**:
- Material profile: fabric realism constraints
- Must preserve: weave pattern, fiber texture, natural drape, edge finishing
- Forbidden keywords: silk-like, premium_weave, luxury_textile
- Light palette: natural_window, soft_directional, textile_booth

## 5. Error Handling & Validation

### 5.1 Pre-Generation Blocking
```python
if not sku_truth.identity.product_name_ru:
    raise BlockSlotGeneration("Missing required field: identity.product_name_ru")

if slot_id == "size-spec" and not any([
    sku_truth.dimensions.length_mm,
    sku_truth.dimensions.width_mm, 
    sku_truth.dimensions.height_mm
]):
    raise BlockSlotGeneration("size-spec requires at least one dimension")

if slot_id == "unboxing-scene" and not sku_truth.packaging.has_real_reference_image:
    raise BlockSlotGeneration("unboxing-scene blocked: no real packaging reference")
```

### 5.2 Post-Generation Validation
- Anti-fabrication critic validates against sku_truth constraints
- Cross-topic isolation checker ensures slot boundaries maintained
- Material realism scorer verifies forbidden keywords absent
- Component compliance validator checks design system adherence

## 6. Implementation Notes

### 6.1 Prompt Assembly Pattern
```python
sections = [
    f"Vertical 3:4 Russian e-commerce image of {sku_truth.identity.product_name_ru}",
    f"Product identity: {render_identity_constraints()}",
    f"Slot purpose: {slot_def.buyer_question_ru} — {slot_def.purpose}",
    f"Composition: {render_composition_rules()}",
    f"Text components: {render_design_system_components()}",
    f"Material constraints: {render_material_rules()}",
    f"Cross-topic isolation: {render_forbidden_topics()}",
    f"Anti-fabrication: {render_fact_constraints()}"
]
return "\n\n".join(sections)
```

### 6.2 Design System Integration
- All text rendering uses `c2_design_system.yaml` tokens
- Color references: `palette.navy_primary` → `#1a2b50`
- Typography: `typography.sizes.title_section` → `32px`  
- Components: `components.title_main_pill` → complete styling specification

### 6.3 Critical Success Factors
1. **Fact verification before generation** — no prompts constructed without required data
2. **Source attribution tracking** — every fact traced to origin
3. **Material-specific realism** — constraints tailored to actual material category
4. **Cross-topic isolation** — each slot answers only its buyer question
5. **Component consistency** — unified visual language across all slots

The v7 system prioritizes factual accuracy over aesthetic appeal, implementing hard technical barriers that prevent AI invention while maintaining visual consistency through the design system framework.