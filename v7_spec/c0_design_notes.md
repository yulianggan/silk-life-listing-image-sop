# C0 v7 Specification Design Notes

## Key Design Decisions

### 1. Fact-First Architecture
**Decision**: Every slot generation BLOCKED until factual evidence exists in sku_truth  
**Rationale**: Enforces user rules 2-4 (packaging reference, dimensions from facts, use cases from SKU)  
**Edge case**: If seller provides incomplete data, some slots will be blocked rather than AI-invented

### 2. 7+1 Slot Structure  
**Decision**: 7 mandatory buyer questions + 1 optional trust slot  
**Rationale**: Covers complete buyer decision journey while maintaining flexibility for 7-8 image sets  
**Edge case**: safety-trust slot can be omitted for budget categories or tight image limits

### 3. Strict Cross-Topic Isolation
**Decision**: Each slot forbidden from answering other slots' questions  
**Rationale**: User rule 5 "each image answers only one question" - prevents topic bleeding  
**Edge case**: Hero slot cannot show measurements, size slot cannot show usage, etc.

### 4. Hands Policy Reversal
**Decision**: 7/8 slots forbid hands, only usage-demo allows hands (with structure-not-blocked rule)  
**Rationale**: Solves v3 "hand holding scene repetition" while preserving usage demonstration  
**Edge case**: use-proof slot shows scenarios WITHOUT hands, usage-demo shows hands WITH constraints

### 5. Real-Reference-Only Packaging
**Decision**: Packaging slot BLOCKED unless real reference images exist  
**Rationale**: User rule 2 "packaging must have real reference" - no fake packaging generation  
**Edge case**: Products without packaging photos get 7-slot sets, not 8-slot

## Constraint Hierarchy

### Level 1: Hard Blocks (Generation impossible)
- Missing identity.* → all slots blocked
- Missing dimensions.source → size-spec blocked  
- packaging.has_real_reference_image=false → unboxing-scene blocked

### Level 2: Content Constraints (Generation modified)  
- forbidden_upgrade_keywords → prompts filtered
- forbidden_cross_topics → prompt scope limited
- hands_blocking_structure=false → usage-demo composition rules

### Level 3: Quality Validation (Post-generation check)
- Cross-topic contamination detection
- Factual accuracy vs sku_truth verification  
- Visual consistency with product_grade_anchor

## Edge Case Handling

### Incomplete SKU Data
**Scenario**: Seller provides product name but no dimensions  
**Behavior**: Hero, material, callouts slots generate; size-spec slot blocked  
**Output**: 7-slot set with missing size evidence, flagged for manual completion

### Zero Real Packaging
**Scenario**: Product has no real packaging photos  
**Behavior**: unboxing-scene slot blocked, other 7 slots proceed  
**Output**: 7-slot focused on product itself, no packaging promises

### Single Use Case
**Scenario**: Only one traceable use case from listing  
**Behavior**: use-proof slot limited to that scenario, no expansion  
**Output**: Focused usage context rather than lifestyle scene grid

### Cross-Category Components  
**Scenario**: Multi-function tool (e.g., knife with bottle opener)  
**Behavior**: identity.archetype and use_cases determine slot priorities  
**Output**: Primary function dominates, secondary functions in callouts only

## v6 → v7 Migration Impact

### File Naming Changes
- v6: `slot_hero-product.png` → v7: `slot_hero-identification.png`
- v6: `slot_scene-grid.png` → v7: `slot_use-proof.png` + `slot_usage-demo.png`  
- v6: `slot_steps-123.png` → v7: `slot_usage-demo.png` (hands allowed)

### Constraint Tightening
- v6 loose material requirements → v7 mandatory material.source tracking
- v6 flexible scene generation → v7 use_cases.source restriction
- v6 hand guidelines → v7 hard hands_forbidden policy (7/8 slots)

### Factual Enforcement 
- v6 AI-estimated dimensions → v7 blocked without dimensions.source
- v6 generic packaging → v7 blocked without real reference_files
- v6 expanded use cases → v7 limited to documented use_cases only

## Technical Implementation Notes

### Validation Order
1. sku_truth completeness check  
2. Slot-specific blocking_conditions evaluation
3. Cross-topic contamination prevention
4. Post-generation compliance verification

### Integration Points
- `sku_truth_v7.yaml` loaded BEFORE any prompt construction
- `slot_question_v7.yaml` determines allowed evidence per slot  
- Existing `art_director_contract.py` needs sku_truth validation integration
- `critic_gpt4v.py` needs cross-topic detection functions

### Performance Considerations
- Blocking approach prevents wasted generation cycles on impossible slots
- Source attribution requirement may increase SKU data preparation time
- Cross-topic validation adds computational overhead but prevents rework

## Success Criteria

### Immediate (C0 completion)
- [x] Fact-first architecture spec complete
- [x] 7-question slot mapping defined
- [x] Cross-topic isolation rules specified

### Downstream (C1-C3 implementation)
- C1: Critic integration with forbidden_cross_topics detection
- C2: Visual style templates per evidence_type  
- C3: Prompt construction with sku_truth validation

### Outcome Validation
- v7 generates ONLY factual, traceable evidence per slot
- No cross-topic contamination between slots
- Product fidelity maintained (no beautification upgrades)
- Real packaging requirement enforced  
- 7-8 coherent images answering specific buyer questions