# C3 Scissors v6 Fix Plan — 5 User Issues Remediation

## Overview

This document provides specific fixes for the 5 user-identified issues with scissors v6 output, mapped to the existing 8-slot architecture with new v7-compliant prompts.

## User's 5 Critical Issues (Original Chinese)

1. **删掉或重做包装礼品图，除非你有真实包装**
2. **核实尺寸数字，没有数据就不要写毫米数**  
3. **把"安全圆头""鼻子""胡须"这类用途改成 SKU 确认过的卖点**
4. **降低金属高级化，保持真实普通不锈钢质感**
5. **删掉重复用途图，补一张真实手持使用图或收口信任图**

## Slot-by-Slot Fix Analysis

| Current Slot | User Issue | Decision | Status |
|---|---|---|---|
| hero-product | - | ✅ **KEEP** | No issues identified |
| size-spec | Issue #2 (dimension verification) | 🔄 **REDO** | Remove/verify millimeter numbers |
| angle-feature | - | ✅ **KEEP** | No issues identified |  
| material-macro | Issue #4 (metal premium reduction) | 🔄 **REDO** | Remove premium language, realistic steel |
| product-callouts | - | ✅ **KEEP** | No issues identified |
| steps-123 | Issues #3, #5 (usage claims, duplication) | 🔄 **REDO** | Verify usage claims, consolidate |
| scene-grid | Issues #3, #5 (usage claims, duplication) | 🔄 **REDO** | Merge with steps-123 approach |
| unboxing-scene | Issue #1 (fake packaging) | ❌ **DELETE/REPLACE** | No real packaging reference |

## Detailed Fix Implementation

### 1. size-spec → REDO (Issue #2: Dimension Verification)

**Problem**: v6 shows exact measurements (90mm, 35mm, 20mm) without verified source
**Solution**: Either verify dimensions from SKU data or remove specific numbers

**New v7 Prompt**:
```
Vertical 3:4 Russian e-commerce sizing reference shot of the SAME stainless steel beauty scissors.
ONE single scissors, clean neutral background with scale reference objects (ruler, coin).

DIMENSIONS POLICY (v7 constraint):
- NO specific millimeter numbers unless verified from sku_truth.dimensions.source
- Show relative size context with reference objects only
- Focus on size perception rather than exact measurements

Text components (v7 design system):
- Top-center title pill (navy bg #1a2b50, white text): "РАЗМЕР И МАСШТАБ"
- Reference context subtitle (grey #6b7280): "Компактный размер для точной работы"  
- Optional scale callout (soft-green pill): "для сравнения" → pointing to reference object

Composition:
- Clean neutral background #f8f9fa
- Scissors positioned with standard reference objects (coin, credit card, or ruler)
- No specific dimension numbers unless verified
- Focus on proportional understanding

Cross-topic isolation:
- FORBIDDEN: usage scenarios, material details, construction callouts
- FOCUS: size perception and scale context only

Material constraints (metal profile):
- Surface: maintain actual stainless steel finish
- No premium enhancement terms
- Preserve: edge geometry, manufacturing details
```

### 2. material-macro → REDO (Issue #4: Metal Premium Reduction)

**Problem**: v6 uses "СТАЛЬ ВЫСОКОГО КАЧЕСТВА" and premium enhancement language
**Solution**: Realistic ordinary stainless steel presentation

**New v7 Prompt**:
```
Vertical 3:4 extreme close-up macro of ordinary stainless steel blade surface.
Material evidence shot showing actual finish quality — 70%+ frame filled with steel surface detail.
Small complete scissors inset in corner for SKU identification continuity.

METAL REALISM CONSTRAINTS (v7 anti-beautification):
- NO luxury/premium/mirror-finish enhancement language
- Show actual material grade: standard consumer stainless steel
- Preserve authentic surface characteristics: grain, manufacturing marks, minor scratches
- Maintain realistic finish level (not jewelry-grade polish)

Text components (v7 design system):
- Top-left material spec tag (white bg #ffffff, navy text #1a2b50): "Нержавеющая сталь"
- Top-right material spec tag (neutral bg #f8f9fa, navy text): "Матовая отделка"
- Bottom-right accent pill (soft-green bg #c8e8c4): "пищевой сплав"

Lighting and quality:
- Soft studio lighting (no dramatic reflections)
- Show realistic surface imperfections and manufacturing texture
- Avoid artificial brilliance or mirror effects
- Material grade: consumer/standard (not premium/industrial)

FORBIDDEN keywords (anti-fabrication):
- высокого качества, премиум, зеркальная, артизанская, ювелирная
- sparks, gleaming, mirror-finish, luxury enhancement terms

Cross-topic isolation:
- FORBIDDEN: usage demonstrations, size measurements, construction details
- FOCUS: authentic material composition and realistic surface quality only
```

### 3. steps-123 → REDO (Issues #3, #5: Usage Verification + Duplication)

**Problem**: v6 shows "для бровей", "для бороды", "для носа" without SKU verification + duplicate content with scene-grid
**Solution**: Verify usage claims against observable SKU features, consolidate messaging

**New v7 Prompt**:
```
Vertical 3:4 sequential usage guide for the SAME stainless steel beauty scissors.
Three horizontal panels showing verified usage applications based on SKU capabilities.

USAGE VERIFICATION (v7 constraint):
- ONLY show usage scenarios that can be verified from SKU reference images
- Remove unverified claims: <待 SKU 字段确认: 鼻毛/胡须剪切是否在实际卖点中>
- Focus on visually confirmable applications: precision cutting, eyebrow grooming, fine trimming

Verified usage sequence:
Panel 1 (top): Scissors positioned for eyebrow precision work (confirmed by blade curvature)
Panel 2 (middle): Scissors showing fine-tip precision cutting capability (confirmed by pointed tip)  
Panel 3 (bottom): Scissors demonstrating edge sharpness (confirmed by blade design)

Text components (v7 design system):
- Top-center title pill (navy bg, white text): "ПРОВЕРЕННЫЕ СПОСОБЫ"
- Three numbered badges (soft-green bg #c8e8c4, navy text):
  * "1" → "точная работа с бровями"  [verified: blade curvature suitable]
  * "2" → "деликатная обрезка"      [verified: pointed tip precision]  
  * "3" → "острая заточка"          [verified: cutting edge visible]

Usage source restrictions:
- Base scenarios ONLY on what can be visually confirmed from scissors design
- Avoid specific body part claims unless verified in listing
- Focus on technique capabilities rather than specific applications

Cross-topic isolation:
- FORBIDDEN: size measurements, material details, construction explanations
- FOCUS: verified usage demonstrations only
```

### 4. scene-grid → CONSOLIDATE with steps-123 (Issues #3, #5: Duplication Fix)

**Problem**: Redundant content with steps-123, same usage verification issues  
**Solution**: Either merge into steps-123 OR replace with different content type

**Decision**: Replace scene-grid with hand-held usage demonstration (addresses Issue #5 request for "真实手持使用图")

**New v7 Prompt** (Replacement slot: usage-demo):
```
Vertical 3:4 actual usage demonstration with hands showing proper scissors technique.
HANDS ALLOWED (v7 exception) but structure must remain 70%+ visible.

HAND-HOLDING DEMONSTRATION (v7 constraint):
- ONE single person's hands demonstrating proper grip and positioning
- Scissors structure and key features must remain clearly visible
- Focus on technique rather than specific body part applications
- Realistic usage context without invented scenarios

Text components (v7 design system):
- Top-center title pill (navy bg, white text): "ПРАВИЛЬНОЕ ПРИМЕНЕНИЕ"
- Step indicators (soft-green numbered badges):
  * "1" → near proper finger positioning in rings
  * "2" → demonstrating controlled cutting motion
- Technique callout (soft-green pill): "безопасный хват"

Composition requirements:
- Hands visible but not blocking scissors identification features
- Clean, professional demonstration photography
- Focus on proper tool handling technique
- Show scissors functionality without specific usage claims

Usage verification:
- Demonstrate general precision tool handling
- Avoid specific "для носа/бороды" claims unless verified
- Focus on safe, proper handling technique
- Show tool capability without inventing applications

Cross-topic isolation:
- FORBIDDEN: size measurements, material details, construction callouts
- FOCUS: proper usage technique demonstration only
```

### 5. unboxing-scene → DELETE/REPLACE (Issue #1: Fake Packaging)

**Problem**: v6 shows "ИДЕАЛЬНЫЙ ПОДАРОК" with invented gift packaging
**Solution**: Delete entirely OR replace with trust/closing image

**Decision**: Replace with safety-trust slot (v7 architecture allows 7-8 slots)

**New v7 Prompt** (Replacement slot: safety-trust):
```
Vertical 3:4 trust and safety certification image for stainless steel beauty scissors.
Focus on quality assurance and purchase confidence factors.

TRUST ELEMENTS (v7 constraint):
- NO invented certifications or fake quality marks  
- Focus on actual product trustworthiness indicators
- Show product confidence without manufacturing fake credentials

Text components (v7 design system):
- Top-center title pill (navy bg, white text): "ГАРАНТИЯ КАЧЕСТВА"
- Trust indicator pills (soft-green bg, navy text):
  * "безопасный материал" [based on stainless steel reality]
  * "точная заточка" [based on visible edge quality]  
  * "долговечность" [based on metal construction]
- Bottom confidence statement (grey text): "проверенный инструмент для точной работы"

Trust elements to show:
- Product build quality visible in manufacturing details
- Material safety (stainless steel = food-safe/skin-safe)
- Construction durability (visible rivet, solid assembly)
- NO fake certifications or invented quality marks

Purchase confidence factors:
- Realistic quality expectations aligned with product grade
- Focus on verified product attributes
- Build trust through authentic product presentation

Cross-topic isolation:
- FORBIDDEN: usage scenarios, size measurements, material macro details
- FOCUS: authentic quality indicators and purchase confidence only
```

## Implementation Summary

### Slots to Keep (4/8):
- ✅ hero-product (no issues)
- ✅ angle-feature (no issues)  
- ✅ product-callouts (no issues)
- ✅ (one additional clean slot for 7-minimum)

### Slots to Redo (4/8):
- 🔄 size-spec → remove unverified dimensions, show scale context
- 🔄 material-macro → realistic steel quality, remove premium language  
- 🔄 steps-123 → verify usage claims, remove unconfirmed applications
- 🔄 scene-grid → replace with usage-demo (hand-held demonstration)
- ❌ unboxing-scene → replace with safety-trust (authentic quality indicators)

### Key v7 Constraints Applied:
1. **Real packaging rule**: Delete fake gift packaging, replace with authentic trust content
2. **Dimension verification**: Remove specific measurements unless source verified  
3. **Usage traceability**: Only show applications verifiable from SKU features
4. **Metal realism**: Apply anti-beautification constraints from material profile
5. **Content consolidation**: Eliminate duplicate usage messaging across slots

### Missing SKU Verification:
- 鼻毛剪切 (nose hair cutting) → `<待 SKU 字段确认>`
- 胡须修剪 (beard trimming) → `<待 SKU 字段确认>`  
- 安全圆头 (safety round tip) → `<待 SKU 字段确认>`

These require actual listing verification before inclusion in final prompts.

## Next Steps
1. User reviews fix plan and confirms approach
2. Implement verified new prompts for 4 redo slots  
3. Run v7 generation with fact constraints enabled
4. Validate output against anti-fabrication critic dimensions