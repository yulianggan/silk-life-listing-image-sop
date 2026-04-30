# Critic Integration Notes v7
## How to integrate 4 new anti-fabrication dimensions into critic_gpt4v.py

### Function Signature Changes

**Before (current):**
```python
def slot_compliance_addendum(slot_id: str) -> str:
```

**After (required):**
```python
def slot_compliance_addendum(slot_id: str, sku_truth: dict = None) -> str:
```

**New main review function signature:**
```python
def review_with_anti_fabrication(
    api_key: str, 
    generated_png: Path, 
    reference_img: Path, 
    slot_id: str, 
    sku_truth: dict = None
) -> dict:
```

### New JSON Response Fields

The critic will return **9 dimensions** instead of current 5:

```python
# Current return structure (keep unchanged)
"scores": {
    "product_consistency": 0-10,    # weighted 0.4
    "cyrillic_render": 0-10,        # weighted 0.25  
    "visual_hierarchy": 0-10,       # weighted 0.2
    "ctr_risk": 0-10,              # weighted 0.15
    "slot_compliance": 0-10,        # hard gate >= 8.0
}

# New anti-fabrication fields (add to scores object)
"scores": {
    # ... existing 5 fields above ...
    "package_authenticity": 0-10,   # hard gate >= 8.0
    "dimension_provenance": 0-10,    # hard gate >= 8.0  
    "use_case_provenance": 0-10,     # hard gate >= 8.0
    "metal_realism": 0-10,          # hard gate >= 8.0 (conditional)
}
```

### Weighted vs Hard Gate Architecture

**Weighted Dimensions (aesthetic quality):**
- `product_consistency` (0.4) + `cyrillic_render` (0.25) + `visual_hierarchy` (0.2) + `ctr_risk` (0.15) = 1.0
- Calculate `weighted_score = sum(score * weight)`
- Pass threshold: `weighted_score >= 7.5`

**Hard Gate Dimensions (fact compliance):**
- All 5 hard gates must score `>= 8.0` individually
- `slot_compliance` (existing) + 4 new anti-fabrication dimensions
- Single hard gate failure = automatic overall failure
- These do NOT contribute to weighted score

### Implementation Strategy

1. **Backward Compatibility**: Keep existing `review()` function unchanged for legacy calls
2. **New Function**: Add `review_with_anti_fabrication()` that accepts sku_truth
3. **Conditional Activation**: New dimensions auto-disable if sku_truth missing or incomplete
4. **Graceful Degradation**: Falls back to 5-dimension mode if new data unavailable

### System Prompt Extensions

**Current system prompt:** Describes 5 dimensions + slot-specific rules

**New approach:** Dynamic system prompt construction based on available data:

```python
def build_system_prompt(slot_id: str, sku_truth: dict = None) -> str:
    base_prompt = BASE_SYSTEM_PROMPT  # Current 5 dimensions
    
    if sku_truth:
        # Add anti-fabrication dimensions section
        base_prompt += "\n\nANTI-FABRICATION DIMENSIONS:"
        
        if sku_truth.get("packaging", {}).get("has_real_reference_image"):
            base_prompt += "\npackage_authenticity: ..."
            
        if sku_truth.get("dimensions", {}).get("source"):
            base_prompt += "\ndimension_provenance: ..."
            
        if sku_truth.get("use_cases"):
            base_prompt += "\nuse_case_provenance: ..."
            
        if is_metal_material(sku_truth.get("material", {}).get("primary", "")):
            base_prompt += "\nmetal_realism: ..."
    
    base_prompt += slot_compliance_addendum(slot_id, sku_truth)
    return base_prompt
```

### Data Loading Requirements

**Material Profiles Integration:**
```python
def load_material_profile(material_primary: str) -> dict:
    """Load material-specific constraints from c1_material_profiles.yaml"""
    # Implementation loads YAML and matches material_primary against aliases
    # Returns forbidden_keywords, must_preserve_features, etc.
```

**SKU Truth Validation:**
```python
def validate_sku_truth_for_dimension(dimension_id: str, sku_truth: dict) -> bool:
    """Check if sku_truth contains required fields for this dimension"""
    requirements = {
        "package_authenticity": ["packaging.has_real_reference_image"],
        "dimension_provenance": ["dimensions.source"],  
        "use_case_provenance": ["use_cases"],
        "metal_realism": ["material.primary", "material.finish"]
    }
    # Return False if required fields missing -> auto-disable dimension
```

### Pass/Fail Logic Update

**Current logic:**
```python
passed = (
    weighted >= PASS_THRESHOLD
    and scores["product_consistency"] >= HARD_PRODUCT_CONSISTENCY  
    and slot_compliance >= HARD_SLOT_COMPLIANCE
)
```

**New logic:**
```python
# Collect all active hard gates
hard_gates = ["slot_compliance"]  # Always active
if sku_truth:
    if sku_truth.get("packaging", {}).get("has_real_reference_image") is not None:
        hard_gates.append("package_authenticity")
    if sku_truth.get("dimensions", {}).get("source"):
        hard_gates.append("dimension_provenance")
    if sku_truth.get("use_cases"):
        hard_gates.append("use_case_provenance")
    if is_metal_material(sku_truth.get("material", {}).get("primary", "")):
        hard_gates.append("metal_realism")

# Check all hard gates
hard_gate_passed = all(scores.get(gate, 10) >= 8.0 for gate in hard_gates)

passed = (
    weighted >= PASS_THRESHOLD
    and scores["product_consistency"] >= HARD_PRODUCT_CONSISTENCY
    and hard_gate_passed
)
```

### CLI Arguments Extension

**Add optional sku_truth parameter:**
```bash
# Current usage (unchanged)
python critic_gpt4v.py generated.png reference.png --slot hero

# New usage (with anti-fabrication)  
python critic_gpt4v.py generated.png reference.png --slot hero --sku-truth /path/to/sku_truth.json
```

### Error Handling

**Missing SKU Truth:** Graceful degradation to 5-dimension mode
**Invalid Material Category:** Auto-skip metal_realism dimension  
**OCR Extraction Failure:** Conservative scoring (assume potential violation)
**Malformed sku_truth:** Log warning, continue with available dimensions

### Migration Path

**Phase 1:** Deploy new critic alongside existing (feature flag)
**Phase 2:** Update pipeline to pass sku_truth when available  
**Phase 3:** Make anti-fabrication dimensions mandatory for v7 spec
**Phase 4:** Deprecate old 5-dimension-only mode

This design maintains full backward compatibility while enabling the fact-based constraint enforcement required by the v7 architecture.