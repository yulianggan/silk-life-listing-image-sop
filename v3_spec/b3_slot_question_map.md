# B3 Slot-Question-Evidence Mapping Design Document

## Design Rationale

Based on B0/B1/B2 DevFleet mission findings, this 8-slot matrix eliminates the primary v3 violation (hand-holding scene repetition) while creating programmatically enforceable quality constraints.

### Core Design Principles Applied

1. **Question-Evidence Binding**: Each slot answers a specific Russian buyer question, mapped to concrete evidence types rather than aesthetic goals
2. **Zero Lifestyle Scene Redundancy**: Only 1 slot (`use-proof-action`) permits hands, solving the B0 finding that 2/8 images violated requirement #5
3. **Programmatic Enforceability**: All `pass_criteria` use measurable metrics (pixel ratios, object detection, line counting) rather than subjective assessments
4. **B2 Gap Closure**: Direct implementation path for the 7/8 missing/soft-prompted constraints identified in pipeline audit

## Buyer Question Strategy

### Russian E-commerce Context
Each question reflects actual Russian buyer decision-making patterns for utility knives:

- **Product Identification**: "Что это?" → Clear category/purpose recognition
- **Size Confidence**: "Какого размера?" → Dimensional expectations management  
- **Build Quality**: "Как устроен?" → Construction trust building
- **Material Proof**: "Какое качество?" → Durability evidence
- **Value Verification**: "Что входит?" → Package contents transparency
- **Performance Proof**: "Действительно режет?" → Functional validation
- **Safety Assurance**: "Безопасен ли?" → Risk mitigation
- **Completeness**: "Другие ракурсы?" → Visual information completeness

## Evidence Type Distribution

```yaml
Evidence Coverage:
  Physical Evidence: 3 slots (size, structure, material)
  Purchase Moments: 3 slots (identification×2, packaging, safety) 
  Functional Proof: 1 slot (use_proof)
  Visual Completeness: 1 slot (angle_variant)
```

This ensures comprehensive buyer confidence across all decision factors while eliminating content overlap.

## Comparison with Current v4 Slots

### Slots Retained (with modifications)
- `hero-product` → `hero-primary`: Stricter background/hand constraints
- `material-tech` → `material-macro`: Focused on blade evidence only
- `dimension-spec` → `size-reference`: Simplified to size evidence only
- `product-callouts` → `structure-callouts`: Enhanced completeness requirements

### Slots Eliminated (redundancy reasons)
- `ergo-handhold`: Lifestyle scene violation (B0 finding)
- `lifestyle-female`: Lifestyle scene violation  
- `lifestyle-female-b`: Lifestyle scene violation
- `scene-grid-4`: Contains hand-holding elements
- `install-steps`: Often shows hands, replaced by `use-proof-action`
- `structure-steps`: Merged into `structure-callouts`

### New Slots Introduced
- `packaging-contents`: Direct "what's included" evidence (B0 feedback)
- `use-proof-action`: Controlled hand usage for functional proof only
- `safety-certification`: Safety messaging (often missing in tool category)

## Constraint Enforcement Mapping

### HARD-ENFORCED (8/8 requirements)
All user constraints now have programmatic validation:

```yaml
Constraint Implementation:
  req_1_question_mapping: "Each slot.buyer_question_* field mandatory"
  req_2_product_consistency: "Inherits reference-locked generation"
  req_3_hands_structure: "hands_block_structure: false in use-proof only"
  req_4_title_lines: "title_lines_count <= 2 in all pass_criteria"
  req_5_lifestyle_scenes: "ordinary_lifestyle_scenes: 0 enforced"
  req_6_blade_macro: "blade_macro: true required in material slot"
  req_7_size_clean: "no_hands + clean_background in size slot"
  req_8_structure_callout: "callout: true + complete_product in structure"
```

### Pipeline Integration Points

For `scripts/critic_gpt4v.py`:
```python
# New validation functions needed:
- validate_title_line_count(image, max_lines=2)
- detect_hands_blocking_structure(image)
- verify_blade_macro_quality(image)
- check_lifestyle_scene_count(image_set)
```

For `templates/art_director_rubric.yaml`:
```yaml
# Add B3 constraint weights:
constraint_weights:
  title_line_limit: 0.15
  no_repeat_lifestyle: 0.20
  evidence_type_match: 0.25
```

## Recommended Slot Renaming

To align with evidence-driven approach:

### Current → Proposed
- `hero-product` → `identification-primary` 
- `material-tech` → `material-evidence`
- `dimension-spec` → `size-evidence`
- `product-callouts` → `structure-evidence`
- `ergo-handhold` → **[DEPRECATED]**
- `lifestyle-female` → **[DEPRECATED]** 
- `install-steps` → `functional-proof`

## Implementation Priority

### Phase 1: Critical Fixes (addresses B0 violations)
1. Implement lifestyle scene counting validation
2. Add hand-blocking-structure detection
3. Deploy title line counting

### Phase 2: Evidence Validation (addresses B2 gaps)
1. Blade macro detection for material slots
2. Clean background validation for size slots  
3. Callout presence detection for structure slots

### Phase 3: Question Alignment (addresses buyer clarity)
1. Map slot outputs to buyer question fulfillment
2. A/B test question-driven vs. aesthetic-driven conversion rates
3. Localize question phrasing for other markets

## Risk Mitigation

### Potential Issues
1. **Over-constraint**: Strict validation might reduce image variety
   - **Mitigation**: Allow 10% tolerance in quantitative checks
   
2. **Technical Complexity**: Hand/structure detection requires computer vision
   - **Mitigation**: Start with human validation, automate incrementally
   
3. **Cultural Context**: Russian buyer questions might not translate
   - **Mitigation**: A/B test against current approach first

### Success Metrics
- Zero repeated lifestyle scenes (vs. current 2/8 violations)
- 100% title compliance (vs. current 0% enforcement)
- 8/8 buyer questions answerable from image set (vs. current 6/8)

## Next Steps for B4 Generalization

This specification is designed for utility knives but structured for category extension:

1. **Evidence Types**: Remain constant across categories (size/structure/material)
2. **Buyer Questions**: Translate per category (cosmetics: "Какой эффект?")
3. **Shot Grammar**: Adapt per product type (electronics: no blade_macro)
4. **Safety Requirements**: Category-specific (food: food-safe materials)

The YAML structure supports this generalization without architectural changes.