# V7 Design System Prompt Injection Guide

## Purpose

This guide explains how to inject design system tokens from `c2_design_system.yaml` into image generation prompts. The goal is to ensure consistent visual appearance across all 8 slots while maintaining natural language flow.

## Core Principle: Token-to-Prompt Translation

Instead of hardcoding visual specifications in each prompt, use this systematic approach:

1. **Identify the slot** and its allowed components from `c2_slot_component_map.yaml`
2. **Select appropriate components** based on the content being displayed
3. **Translate component tokens** into natural language descriptions using the patterns below
4. **Inject component descriptions** seamlessly into the prompt narrative

## Component Injection Patterns

### 1. title_main_pill
**Design Tokens:**
- `bg_color: navy_primary (#1a2b50)`
- `text_color: white`
- `font_size: title_section (32px)`
- `border_radius: pill_full (999px)`

**Prompt Injection Pattern:**
```
Top-center title pill: deep navy blue background (#1a2b50), crisp white text, fully rounded pill shape, Inter font 32pt weight 700, subtle shadow. Text reads "[TITLE_CONTENT]" with maximum 28 Russian characters per line, up to 2 lines, center-aligned.
```

**Example Usage:**
- `slot=hero-identification`: "Text reads 'Керамический нож для кухни'"
- `slot=size-spec`: "Text reads 'Размеры изделия'"
- `slot=material-macro`: "Text reads 'Материал изделия'"

### 2. highlight_label_pill
**Design Tokens:**
- `bg_color: green_soft (#c8e8c4)`
- `text_color: navy_primary (#1a2b50)`
- `font_size: label_pill (24px)`

**Prompt Injection Pattern:**
```
Highlight label pill: soft light green background (#c8e8c4), deep navy blue text (#1a2b50), fully rounded pill, Inter font 24pt weight 600, positioned [POSITION]. Text reads "[HIGHLIGHT_CONTENT]" single line only, max 20 Russian characters.
```

**Example Usage:**
- `position=bottom-right-corner`: For hero badge "Премиум качество"
- `position=callout-endpoint`: For product feature "Главное преимущество"
- `position=benefit-emphasis`: For use-proof benefits "Универсальное применение"

### 3. dimension_card
**Design Tokens:**
- `bg_color: white`
- `number_color: navy_primary (#1a2b50)`
- `unit_color: green_accent (#4a7c59)`
- `border_radius: rounded_md (12px)`

**Prompt Injection Pattern:**
```
Dimension card: clean white background with subtle gray border, 12px rounded corners, soft shadow. Large navy blue number (#1a2b50) in Inter Bold 32pt, followed by smaller green unit text (#4a7c59) in Inter Medium 20pt. Layout pattern: "[NUMBER] [UNIT]". Center-aligned within card.
```

**Example Usage (3 cards for size-spec):**
```
Three dimension cards arranged in clean grid:
- Card 1: "25 см" (length)
- Card 2: "3 см" (width)  
- Card 3: "1.2 см" (height)
Each card: white background, navy numbers, green units, 12px rounded corners.
```

### 4. scene_label_pill
**Design Tokens:**
- `bg_color: navy_primary (#1a2b50)`
- `text_color: white`
- `font_size: label_pill (24px)`

**Prompt Injection Pattern:**
```
Scene context pill: deep navy blue background (#1a2b50), white text, fully rounded pill, Inter font 24pt weight 700, positioned [CONTEXT_POSITION]. Text reads "[CONTEXT_NAME]" single line, max 16 Russian characters.
```

**Example Usage:**
- `use-proof slot`: "Кухня", "Ресторан", "Кемпинг" positioned at context corners
- `usage-demo slot`: "Правильный хват" positioned as technique label

### 5. numbered_step_badge (Extension Component)
**Design Tokens:**
- `bg_color: green_soft (#c8e8c4)`
- `text_color: navy_primary (#1a2b50)`
- `border_radius: rounded_lg (16px)`
- `min_width: 56px, min_height: 56px`

**Prompt Injection Pattern:**
```
Square step badge: light green background (#c8e8c4), navy blue number (#1a2b50), 16px rounded corners, 56x56px minimum size, Inter Bold 32pt. Single digit "[STEP_NUMBER]" centered. Position follows logical sequence flow.
```

**Example Usage (usage-demo slot):**
```
Sequential step badges showing usage progression:
- Badge "1" positioned at initial grip position
- Badge "2" positioned at cutting motion
- Badge "3" positioned at final result
Each badge: green background, navy number, square with rounded corners.
```

### 6. subtitle_secondary_text (Extension Component)
**Design Tokens:**
- `bg_color: transparent`
- `text_color: grey_subtitle (#6b7280)`
- `font_size: body_regular (18px)`

**Prompt Injection Pattern:**
```
Secondary explanatory text: transparent background, medium gray color (#6b7280), Inter Regular 18pt, positioned below main title. Text reads "[SUBTITLE_CONTENT]" with max 35 characters per line, up to 3 lines, left-aligned, normal line height.
```

### 7. technical_annotation_label (Extension Component)
**Design Tokens:**
- `bg_color: white`
- `text_color: navy_primary (#1a2b50)`
- `border_color: navy_primary, border_width: 2px`
- `border_radius: rounded_sm (6px)`

**Prompt Injection Pattern:**
```
Technical callout label: white background, navy blue text (#1a2b50), 2px navy border, 6px rounded corners, Inter SemiBold 14pt. Connected to product feature with thin navy line. Text reads "[TECHNICAL_TERM]" single line, max 12 characters.
```

**Example Usage (product-callouts slot):**
```
Three technical annotation labels connected by callout lines:
- "Эргономичная ручка" → pointing to handle area
- "Острое лезвие" → pointing to blade edge
- "Защитный чехол" → pointing to sheath
Each label: white background, navy text and border, small rounded corners.
```

### 8. material_spec_tag (Extension Component)
**Design Tokens:**
- `bg_color: background_neutral (#f8f9fa)`
- `text_color: navy_primary (#1a2b50)`
- `border_radius: rounded_md (12px)`

**Prompt Injection Pattern:**
```
Material specification tag: neutral light background (#f8f9fa), navy blue text (#1a2b50), 12px rounded corners, Inter Medium 18pt. Positioned overlaying material surface. Text reads "[MATERIAL_SPEC]" up to 2 lines, max 18 characters per line, center-aligned.
```

## Slot-Specific Injection Examples

### Hero Identification Slot
```
Professional product photography with clean studio background. 

Top-center title pill: deep navy blue background (#1a2b50), white text "Керамический нож для кухни", fully rounded pill, Inter Bold 32pt, subtle shadow.

Below title: explanatory text in medium gray (#6b7280), "Профессиональный кухонный инструмент", Inter Regular 18pt.

Optional bottom-right badge: light green pill (#c8e8c4) with navy text "Премиум качество", fully rounded, Inter SemiBold 24pt.
```

### Size Specification Slot
```
Clean measurement layout with neutral background.

Top title pill: navy background (#1a2b50), white text "Размеры изделия", fully rounded, Inter Bold 32pt.

Three dimension cards in organized grid:
- Card 1: white background, "25" in navy Bold 32pt, "см" in green Medium 20pt (#4a7c59), 12px rounded corners
- Card 2: white background, "3" in navy Bold 32pt, "см" in green Medium 20pt, 12px rounded corners  
- Card 3: white background, "1.2" in navy Bold 32pt, "см" in green Medium 20pt, 12px rounded corners

Each card has subtle shadow and clean spacing for measurement clarity.
```

### Product Callouts Slot
```
Technical product view with structural annotations.

Top title pill: navy background (#1a2b50), white text "Конструкция изделия", fully rounded pill, Inter Bold 32pt.

Four technical callout labels connected by thin navy lines:
- "Эргономичная ручка": white background, navy text and 2px border, 6px corners, Inter SemiBold 14pt
- "Острое лезвие": white background, navy text and border, pointing to blade edge
- "Защитный чехол": white background, navy text and border, pointing to protective cover
- "Нескользящая основа": white background, navy text and border, pointing to base grip

Key feature emphasis: light green pill (#c8e8c4) with navy text "Главное преимущество" positioned at most important feature.
```

## Text Content Guidelines

### Russian Text Considerations
- Always account for Cyrillic character width in max length calculations
- Russian text typically requires 15-20% more horizontal space than Latin equivalents
- Use common, clear terminology that Russian buyers understand immediately

### Content Hierarchy
1. **Primary**: title_main_pill content should be the most important information
2. **Secondary**: highlight_label_pill for key differentiators or benefits
3. **Supporting**: subtitle_secondary_text for additional context
4. **Technical**: annotation labels for specific component identification

### Forbidden Practices
- **Never hardcode colors**: Always reference design system tokens
- **Never mix fonts**: Only use Inter family across all components
- **Never use custom radius values**: Only use system-defined radius tokens
- **Never exceed max character limits**: Respect component constraints
- **Never contaminate across topics**: Each slot stays in its buyer question lane

## Implementation Workflow

1. **Slot Identification**: Determine which of the 8 slots is being generated
2. **Component Selection**: Check `c2_slot_component_map.yaml` for allowed components
3. **Content Planning**: Plan what text content goes in each component
4. **Token Translation**: Convert design tokens to natural language using patterns above
5. **Prompt Assembly**: Weave component descriptions into coherent image prompt
6. **Validation**: Verify no forbidden components or cross-topic contamination

## Quality Checklist

Before finalizing any prompt with design system injection:

- [ ] All colors reference palette tokens (no ad-hoc hex values)
- [ ] Only Inter font family specified across all components
- [ ] Only system radius values used (pill_full, rounded_md, etc.)
- [ ] Character limits respected for all text components
- [ ] Component positioning logical and non-overlapping
- [ ] Slot's forbidden components not included
- [ ] Cross-topic isolation maintained (e.g., no size info in material slot)
- [ ] User's 4 core component specifications exactly followed
- [ ] Russian text appropriately sized for Cyrillic characters

This systematic approach ensures that every generated image maintains visual consistency while serving its specific buyer question purpose within the v7 specification framework.