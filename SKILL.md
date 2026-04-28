---
name: silk-life-listing-image-sop
description: >
  丝绸生活 Ozon/Russian e-commerce listing 美工思维蒸馏 SOP。
  适用于“沟通图片/卖点表/参考图 → 俄罗斯电商 8 张套图”的一键工作流：
  先根据真实美工样例生成 ArtDirectorContract，再选择设计范式，Codex 只生成无字底图，
  最后用 overlay_text.py 程序化叠加准确俄文，并用 critic 校验产品一致性、商业清晰度和 CTR 风险。
  触发词：丝绸生活出图、Ozon 套图、listing 套图、沟通图片转美工图、蒸馏美工作图思维、俄罗斯电商图片。
---

# 丝绸生活 Ozon Listing 美工思维蒸馏 SOP

## 0. 核心原则

不要让 Cloud/Claude 直接写一段“好看的图片提示词”，也不要让 Codex 直接生成带完整俄文的成品图。

正确链路：

```text
沟通图片 / listing 表 / 产品参考图
  ↓
DesignerDelta：如果有美工图，先比较“美工到底改了什么”
  ↓
ArtDirectorContract：像美工总监一样先判断商业意图、证据方式、版式、文字区
  ↓
DesignParadigm：选择稳定范式，如主图角标、尺寸图、步骤图、材质微距、场景网格
  ↓
CodexPlatePrompt：只生成无最终文字的视觉底图
  ↓
overlay_text.py：程序化叠加俄文标题、数字、角标、尺寸、步骤
  ↓
Critic：产品一致性优先，确认没有偏离实物，再看点击率和转化表达
```

这版 skill 的重点是 **美工判断层**，不是堆提示词。美工图不是把沟通图照搬得更漂亮，而是把杂乱素材压缩成买家一秒能懂的视觉答案。

## 1. 安全与类目边界

本 skill 默认只自动处理生活用品、护理用品、鞋服附件、收纳清洁、普通家居消耗品、普通车用配件等低风险商品。

遇到锋利刀刃/刀具类、武器、自卫器材、危险化学品、成人用品、药品/补剂、烟酒、赌博相关商品，必须输出：

```json
{
  "status": "needs_human_review",
  "reason": "restricted_or_sharp_tool_category",
  "auto_generate_allowed": false
}
```

不要为这些类目生成高点击高转化营销图提示词，也不要生成购买强化文案。

## 2. 输入约定

```text
<类目>/
├─ 沟通图片/
│  ├─ listing.xlsx 或 listing.xls
│  ├─ 主图 / main / product / body 参考图
│  ├─ scene / use / description 场景参考图
│  └─ 可选：竞品截图、运营备注
└─ 可选：美工图/ 或 美工图片/
   ├─ 1.png / xd_1.jpeg / hou1.png ...
   └─ 已完成的美工套图
```

文件夹名不稳定是正常情况：`美工图`、`美工图片`、`沟通图片`、`main`、`主图`、`Description`、`Variant` 都要兼容。

## 3. 从真实样例蒸馏出的美工决策

本版已吸收 6 组真实样例：

| 案例 | 沟通图 | 美工图 | 美工核心取舍 |
|---|---:|---:|---|
| 透明硅胶后跟垫 | 33 | 8 | 灰白绿医护感；保护、尺寸、步骤、水洗、材质、前后对比、鞋型适配 |
| 轮胎充气接头 | 20 | 8 | 黑橙工业感；主图冲击力强，规格/步骤仍保持白底清晰 |
| 自穿线针套装 | 37 | 8 | 米色木质手工感；统一 12 支针，围绕木盒和金色针建立视觉锚点 |
| 美甲剪 | 26 | 17 | 粉蓝美容感；参数图极简，人物图建立沙龙结果和信任 |
| 办公切割工具 | 23 | 10 | 只作为视觉范式观察；自动高转化出图需 human review |
| 黄色鞋垫除味贴 | 27 | 8 | 黄绿柠檬天然感；包装、数量、尺寸、步骤、成分、鞋型、7 天效果 |

完整规则见：

```text
templates/designer_delta_bank.yaml
templates/design_paradigms.yaml
templates/art_director_rubric.yaml
```

### 3.1 共性规律

1. **竖版 3:4 统一**：沟通图常是 800×800 或 1500×1500，美工图统一改成 900×1200 / 1200×1600。
2. **一图一个问题**：主图回答“这是什么”，尺寸图回答“合不合适”，步骤图回答“怎么用”，材质图回答“为什么可靠”。
3. **证据先于文案**：水洗就给水面，尺寸就给箭头，使用就给手部步骤，适配就给场景网格。
4. **产品本体不动**：形状、颜色、包装、数量、孔点、螺纹、针眼、透明度、金属感不能被 AI 改。
5. **俄文短而强**：主标题 2-6 个词，角标只放数字/规格/数量，副文最多 2-3 条短句。
6. **色温按类目走**：鞋护/除味用绿黄白，美容用粉蓝白，手工针套用米色木质金色，车品用黑橙金属。
7. **场景不能喧宾夺主**：人物、手、鞋、车轮、柠檬、布料只服务卖点，不允许盖过产品。

## 4. ArtDirectorContract

Cloud/Claude 必须先输出这个合同，再给 Codex：

```json
{
  "contract_version": "2026-04-28-v2",
  "status": "ready",
  "auto_generate_allowed": true,
  "category_archetype": "yellow_deodorant_sticker",
  "set_style": {
    "canvas": "1200x1600 or 900x1200, vertical 3:4",
    "palette": "sunny yellow / lemon green / clean white",
    "typography": "Cyrillic overlay only"
  },
  "sku_facts": {
    "must_preserve": ["yellow sticker shape", "package color", "12 pcs"],
    "forbidden_changes": ["do not change product color", "do not invent count"]
  },
  "slot_contracts": [
    {
      "slot_id": "hero-product",
      "buyer_question": "买家第一眼要确认什么？",
      "commercial_intent": "提升首图点击，同时确认数量和品类",
      "selected_paradigm": "hero_spec_badge",
      "visual_answer": "包装 + 产品 + 使用对象 + 数量角标",
      "overlay_text_plan": {
        "title": "СТИКЕРЫ ДЛЯ ОБУВИ",
        "badge": "12 шт",
        "subtitle": "для обуви"
      },
      "codex_plate_prompt": "Create a vertical 3:4 commercial product plate WITHOUT final readable text...",
      "negative_prompt": [
        "no final readable Cyrillic text",
        "do not alter product shape",
        "do not invent product count"
      ],
      "critic_checks": [
        "product body same as reference",
        "count and size facts preserved",
        "main title readable after overlay"
      ]
    }
  ]
}
```

## 5. 设计范式选择

优先使用这些范式：

| 范式 | 用途 | 美工样例里的表现 |
|---|---|---|
| `hero_spec_badge` | 首图点击 | 大产品 + 俄文主标题 + 数字角标 |
| `size_spec` | 尺寸规格 | 白底/浅底，产品居中，少量箭头和数字 |
| `steps_123` | 使用步骤 | 三步卡片，每步一个动作 |
| `scene_grid` | 适用范围 | 鞋型/车辆/材料/对象 2×2 网格 |
| `before_after_result` | 效果证明 | 上下或左右对比 |
| `material_macro` | 材质/成分 | 微距、成分道具、材质光泽 |
| `quantity_pack` | 数量/套装 | 包装 + 多件铺陈 + 大数字 |
| `lifestyle_human_scene` | 情绪和信任 | 人物或手部真实场景 |
| `trust_closure` | 收口信任 | 品质标题 + 稳定产品图 |

## 6. Codex 出图规则

Codex 只做 **无字底图**：

```text
Create a vertical 3:4 Russian ecommerce visual plate.
Do NOT render final readable Russian text.
Leave clean blank zones for title, badge and labels.
Keep the exact product from the reference: same shape, color, count, material and package.
Use category palette: ...
Composition: ...
```

强制负面约束：

```text
no fake Cyrillic text
no unreadable glyphs
no extra product variants
do not change package color
do not change count
do not change product material
do not crop away key product shape
```

## 7. 程序化叠字规则

所有俄文用 `scripts/overlay_text.py` 叠加。不要让图像模型直接画俄文。

原因：

- 图像模型容易生成俄文乱码。
- 俄文标题、尺寸、数量属于商品事实，不能随机变。
- 程序叠字能稳定控制字号、位置、颜色和层级。

推荐字体顺序：

```text
Arial / DejaVu Sans / Noto Sans CJK / system sans
```

## 8. Critic 硬阈值

通过标准：

```text
product_fidelity >= 8.5
weighted_score >= 7.8
no fake Cyrillic
no wrong quantity
no wrong material
no restricted auto-marketing
```

权重：

```yaml
product_fidelity: 0.42
commercial_clarity: 0.20
russian_text_correctness: 0.16
visual_hierarchy: 0.12
set_consistency: 0.06
marketplace_safety: 0.04
```

产品一致性低于阈值时，不要为了 CTR 继续美化，直接重跑或标记人工审核。

## 9. 一键流程

最小接入：

```bash
python3 scripts/art_director_contract.py \
  output/<类目>/standard_sku.json \
  --slot-plan output/<类目>/slot_plan.json \
  --out output/<类目>/art_director_contract.json
```

生成给 Codex 的任务：

```bash
python3 scripts/one_click_ru_listing.py \
  --standard-sku output/<类目>/standard_sku.json \
  --slot-plan output/<类目>/slot_plan.json \
  --out-dir output/<类目>
```

Codex 生成每张无字 `plate.png` 后叠字：

```bash
python3 scripts/overlay_text.py \
  output/<类目>/plates/hero-product.png \
  output/<类目>/art_director_contract.json \
  --slot-id hero-product \
  --out output/<类目>/slot_hero-product.png
```

## 10. 样例蒸馏流程

后续继续喂“沟通图片 + 美工图”时，先跑：

```bash
python3 scripts/distill_designer_cases.py \
  --input-zips /path/to/*.zip \
  --out-dir training_cases
```

它会输出：

```text
training_cases/
├─ extracted/
├─ manifest.json
├─ contact_sheets/
├─ art_sheets/
└─ distillation_index.md
```

然后用 `prompts/designer_delta_distillation.md` 对新样例继续补充 `templates/designer_delta_bank.yaml`。
