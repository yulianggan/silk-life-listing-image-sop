---
name: silk-life-listing-image-sop
description: >
  丝绸生活 Ozon listing 美工思维蒸馏 SOP。用于“沟通图片/卖点表/参考图 → 美工风格套图”工作流：先提炼美工决策，再选择设计范式，生成 Codex 图片提示词与文字叠加方案，最后用视觉 critic 校验。触发词：丝绸生活出图、Ozon 套图、listing 套图、沟通图片转美工图、蒸馏美工作图思维、类目商详图、Codex 生成图片提示词。
---

# 丝绸生活 Ozon Listing 美工思维蒸馏 SOP

## 0. 这版 skill 的核心变化

不要让 Claude 直接写“好看的图片提示词”，也不要让 Codex 直接生成带完整俄文的成品图。

正确链路是：

```text
沟通图片/卖点表/参考图
  ↓
ArtDirectorContract：像美工一样先做商业判断、构图判断、取舍判断
  ↓
DesignParadigm：为每张图选一个稳定设计范式
  ↓
CodexPlatePrompt：只生成产品视觉底图/场景/留白，不生成最终俄文
  ↓
ProgrammaticTextOverlay：用脚本叠加俄文标题、角标、卖点
  ↓
Critic：校验产品一致性、卖点表达、文字可读性、CTR 风险
```

AI 出图不符合预期，通常不是“提示词不够长”，而是缺少中间的 **美工决策层**：

- 沟通图给的是素材和意图，美工图给的是“买家一眼能懂的视觉答案”。
- 美工会删除弱信息、放大强信息、换场景、重排层级，而不是照搬参考图。
- 每张图只回答一个买家问题：这是什么、解决什么、怎么用、效果如何、为什么可信。
- 俄文大字、绿色角标、留白、手部/生活场景、强主次层级，是品牌记忆点，不是装饰。

## 1. 安全与类目边界

本 skill 只处理生活用品、护理用品、鞋服附件、收纳清洁、家居消耗品、普通车用配件等低风险商品。遇到刀具、锋利刀刃、武器、自卫器材、危险化学品、成人用品、药品/补剂、烟酒、赌博相关商品时，输出 `needs_human_review`，不要生成营销图片、购买强化文案或平台上架提示词。

## 2. 输入约定

```text
<类目>/
├─ 沟通图片/
│  ├─ listing.xlsx 或 listing.xls
│  ├─ 主图 / main / product / body 参考图
│  ├─ scene / use / description 场景参考图
│  └─ 可选：竞品截图、运营备注
└─ 可选：美工图/ 或 美工图片/
   ├─ xd_1.jpeg ... xd_8.jpeg
   └─ 已完成的美工套图
```

如果同时有“沟通图片”和“美工图”，先做 **DesignerDelta**：逐张比较“美工做了哪些取舍”。如果只有沟通图片，就用内置范式生成一版 ArtDirectorContract。

## 3. 美工思维蒸馏：DesignerDelta

对每组“沟通图 → 美工图”提炼 7 类变化，不要只描述画面表象：

1. **卖点压缩**：美工把哪句长卖点压成了哪个 2-5 词俄文主标题？哪些信息被删掉了？
2. **视觉焦点**：产品、手、人物、场景、数字徽章，谁是第一眼焦点？占画面多少？
3. **证据方式**：尺寸标注、步骤图、前后对比、材质微距、数量堆叠、场景网格、信任徽章，使用了哪种证明方式？
4. **情绪方向**：干净安心、专业耐用、温柔护理、明亮生活、精密可靠，属于哪种情绪？
5. **背景替换**：参考图里的杂乱背景是否被换成品牌色背景或真实生活场景？为什么？
6. **文字层级**：主标题、角标、副标题、脚注分别放在哪里？有没有 1 秒可读性？
7. **商品真实性**：产品形状、颜色、数量、材质是否被严格保留？哪些地方允许美化，哪些不允许改？

输出 `style_memory.pattern_bank[]`，每条格式：

```json
{
  "pattern": "把长卖点压缩成一个俄文强承诺 + 一个绿色数字角标",
  "when_to_use": "卖点中有时长、数量、尺寸、功效等强数字时",
  "visual_move": "标题放顶部，数字徽章放左侧或右上，产品居中放大 55-65%",
  "avoid": "不要把 4-6 条卖点全部塞进同一张图"
}
```

## 4. ArtDirectorContract 必填字段

Claude Code 必须先生成这个 JSON，再交给 Codex：

```json
{
  "contract_version": "2026-04-27-v1",
  "status": "ok | needs_human_review",
  "category": "",
  "product_identity_lock": {
    "must_keep": ["产品外形", "颜色", "材质", "数量", "关键结构"],
    "must_not_invent": ["不存在的配件", "未提供的认证", "夸张功效", "品牌 logo"],
    "reference_priority": ["main/body 产品图", "结构图", "场景参考图"]
  },
  "buyer_read": {
    "core_buyer_question": "买家第一眼最关心什么？",
    "core_selling_axis": "功效/尺寸/耐用/便利/数量/场景/信任",
    "one_sentence_strategy": "这一套图用什么视觉逻辑说服买家"
  },
  "style_memory": {
    "brand_tokens": ["俄语粗体大字", "绿色角标", "干净留白", "真实手部/生活场景", "柔和但清晰的类目色温"],
    "pattern_bank": []
  },
  "slot_contracts": []
}
```

## 5. 每张图的 SlotContract

每张图必须包含：

```json
{
  "slot_id": "hero-product",
  "buyer_question": "这是什么，为什么值得点？",
  "design_paradigm": "hero_spec_badge",
  "one_sentence_promise_ru": "2-6 个俄文词，给文字叠加用",
  "visual_answer": "画面如何回答 buyer_question",
  "composition": {
    "focal_object": "product | hand+product | scene+product | comparison | steps",
    "product_scale": "55-65%",
    "text_safe_zones": ["top", "left_badge", "bottom_pill"],
    "background_mood": "clean warm cream / mint / dark industrial / blush minimal"
  },
  "codex_plate_prompt": "只生成无最终文字的视觉底图提示词",
  "negative_prompt": "避免项",
  "text_overlay_plan": {
    "do_not_ask_codex_to_render_final_text": true,
    "overlays": []
  },
  "critic_checklist": []
}
```

## 6. 设计范式选择规则

优先从 `templates/design_paradigms.yaml` 选择，不要临场发明版式。常用图位：

| 目的 | 推荐范式 | 画面答案 |
|---|---|---|
| 主图点击 | `hero_spec_badge` | 产品大图 + 主标题 + 数字/功效角标 |
| 卖点解释 | `product_callouts` | 产品圈注，点对点解释结构/特点 |
| 使用方式 | `steps_123` | 1/2/3 步骤，手部动作清晰 |
| 多场景 | `scene_grid_4` 或 `scene_list_text` | 4 宫格/列表展示可用场景 |
| 使用前后 | `before_after_result` | 同角度对比，强调可见变化 |
| 材质/耐用 | `material_macro` | 微距或结构分解，不靠空泛文案 |
| 数量/套装 | `pack_quantity` | 多件堆叠 + 数字大字 |
| 信任背书 | `trust_quality` | 质感产品图 + 工厂/品质承诺，不伪造认证 |

## 7. Codex 图片提示词原则

Codex 只负责生成 **视觉底图**，不负责生成最终俄文文字。提示词必须写清：

- 使用参考图锁定真实产品，不改变产品形状、颜色、材质、数量和关键结构。
- 生成 1024×1536 或 3:4 竖版 listing 图。
- 预留干净文字区域：顶部标题区、角标区、底部胶囊区；这些区域可以有浅色块，但不要生成可读文字。
- 场景、手、光线、背景可以美化，但不能让产品变成另一个商品。
- 不要生成乱码俄文、假 logo、假认证、竞品品牌、过多小字、混乱拼贴。

推荐 Codex Prompt 结构：

```text
Create a photorealistic e-commerce visual plate for a Russian Ozon listing.
Canvas: vertical 3:4, 1024x1536.
Reference lock: keep the exact product from the supplied product reference image: same silhouette, color, material, quantity, and key details.
Design paradigm: <design_paradigm>.
Composition: <composition>.
Text zones: reserve clean blank areas for later text overlay at <zones>. Do NOT render readable Cyrillic or Latin text. Use blank rounded shapes only.
Style: <palette/style tokens>.
Avoid: <negative_prompt>.
```

## 8. 俄文文字：必须后期叠加

Codex/ImageGen 对西里尔字母稳定性差，最终图里的俄文标题、角标、卖点不要交给模型生成。用 `scripts/overlay_text.py` 读取 `text_overlay_plan` 程序化叠加。

叠加规则：

- 主标题 1-2 行，单行 5 个词以内。
- 绿色数字/功效角标 1 个，优先承载时长、数量、尺寸、强功效。
- 副卖点最多 3 条，每条 2 行以内。
- 避免 6 条以上小字堆叠；看不清的文字等于没有卖点。
- 没有证据的认证、奖章、五星评价不要生成。

## 9. Critic 复核

每张图至少校验 6 项：

| 维度 | 权重 | 通过标准 |
|---|---:|---|
| 产品一致性 | 0.30 | 与参考图是同一个商品，不多配件、不改形状 |
| 商业意图 | 0.20 | 1 秒内能看懂这张图想卖什么 |
| 文字可读性 | 0.20 | 俄文无乱码，层级清楚，主标题突出 |
| 版式/CTR | 0.15 | 不拥挤、不廉价、不脏色、不像随机拼贴 |
| 品牌一致性 | 0.10 | 有丝绸生活常见的绿色角标、留白、干净真实感 |
| 合规/真实性 | 0.05 | 不伪造认证、不夸张、不处理受限商品 |

硬失败：产品变形、俄文乱码、文字由模型直接生成且不可读、卖点和图不对应、出现受限商品营销强化。

## 10. 推荐执行方式

```bash
# 1) 原有流程生成 standard_sku.json 与初步 slot plan
python3 scripts/normalize.py <category_dir> --out output/<category>/standard_sku.json
python3 scripts/slot_planner_v5.py output/<category>/standard_sku.json --target 8 > output/<category>/slot_plan.json

# 2) 新增：生成 ArtDirectorContract
python3 scripts/art_director_contract.py \
  output/<category>/standard_sku.json \
  --slot-plan output/<category>/slot_plan.json \
  --out output/<category>/art_director_contract.json

# 3) 对每个 slot，把 codex_plate_prompt 交给 Codex/image2 edit，生成 plate.png
# 4) 新增：程序化叠加俄文文字
python3 scripts/overlay_text.py plate.png output/<category>/art_director_contract.json \
  --slot-id hero-product \
  --out output/<category>/slot_hero-product.png

# 5) critic 复核，不通过则根据 issues 重跑 plate 或调整 overlay
```

## 11. 最常见失败与修复

| 失败 | 原因 | 修复 |
|---|---|---|
| 图片好看但不像产品 | prompt 没有 product_identity_lock | 在 Codex prompt 第一段写 reference lock，并把产品图设为最高优先级 |
| 俄文乱码 | 让 Codex 直接生成文字 | 改为无文字底图 + overlay_text.py |
| 像随机海报 | slot 没有 buyer_question | 每张图先写“买家问题”和“视觉答案” |
| 信息太多 | 把 Excel 全部卖点塞进图 | 一张图只讲一个承诺，最多 3 条副卖点 |
| 缺美工味 | 只有图位，没有 DesignerDelta | 先从历史“沟通图→美工图”提炼 pattern_bank |
| 每张图风格不统一 | palette 和品牌 token 没有贯穿 | 每个 SlotContract 继承同一 style_memory |

