---
name: silk-life-listing-image-sop
description: >
  丝绸生活 Ozon/Russian e-commerce listing 美工思维蒸馏 SOP。
  适用于“沟通图片/卖点表/参考图 → 俄罗斯电商 8 张套图”的一键工作流：
  先从沟通图片中锁定真实商品图，再生成 ArtDirectorContract，Codex 只做 reference-locked 无字底图，
  最后由 overlay_text.py 程序化叠加准确俄文，并用 critic 校验产品一致性、长宽比例、文字位置和画布铺满。
  触发词：丝绸生活出图、Ozon 套图、listing 套图、沟通图片转美工图、蒸馏美工作图思维、俄罗斯电商图片。
---

# 丝绸生活 Ozon Listing 美工思维蒸馏 SOP v4

## 0. 这版修复的问题

这版针对实测图片里的 6 个问题做了硬修复：

1. **产品细节偏离实物**：例如真实产品很修长，但生成图变短、变胖。
2. **Codex 不知道哪张是实物图**：沟通图片里混有竞品、场景、尺寸、详情页截图，模型会随机“猜产品”。
3. **文字与预留空间错位**：Codex 先画随机空白框，`overlay_text.py` 再按固定位置叠字，天然会错位。
4. **左右留白过多**：图像模型或后处理把画布当成带边框截图，而不是 full-bleed 电商图。
5. **旧直出链路误报通过**：`orchestrate.py` 会让模型直接画俄文和卡片，且曾出现空分数 `passed=true`。
6. **美工刀风格跑偏**：美工成品是办公/手工/文具风，不是黑金证书、五星好评或危险刀具营销风。

正确链路：

```text
沟通图片文件夹
  ↓
reference_selector.py：从沟通图片中筛选真实商品图
  ↓
reference_manifest.json：primary_product_refs + role_groups + geometry hints
  ↓
ArtDirectorContract：商业意图 + 设计范式 + 产品几何锁 + overlay 盒子
  ↓
Codex：必须附带 reference_images，只做 reference-locked 无字底图
  ↓
overlay_text.py：自己绘制文字框、俄文、下划线标题、角标、编号和箭头
  ↓
codex_job_runner.py + Critic：检查实物一致、长宽比例、文字位置、无左右白边；critic 失败也要写 results.json
```

`scripts/orchestrate.py`、`scripts/slot_planner.py` 是 legacy 兼容链路。除非明确排查旧结果，不要用它们作为正式出图入口。

## 1. 类目策略：不做类目硬拦截，改为事实一致性门

本项目只服务内部俄罗斯电商商品图生产，不在 skill 内做“类目硬拦截”。  
也就是说：`ArtDirectorContract` 不再因为类目关键词直接中断，而是始终围绕 SKU 事实、实物参考图和平台文案进行图片生产准备。

保留的硬门只和出图质量有关：

```text
必须锁定真实商品图
必须保留产品形状、颜色、包装、数量、材质、长宽比例
必须避免 AI 凭文字重画产品
必须避免俄文乱码
必须避免文字框错位
必须避免左右白边和过大留白
必须避免尺寸、数量、材料、效果描述与 SKU 不一致
```

类目是否允许上架、是否需要额外人工审核，由业务/平台流程在本 skill 外处理。

## 2. 输入约定

```text
<类目>/
├─ 沟通图片/
│  ├─ listing.xlsx 或 listing.xls
│  ├─ 主图 / main / product / body / 实物 / 白底 参考图
│  ├─ detail / macro / size / scene / use / description 参考图
│  └─ 可选：竞品截图、运营备注
└─ 可选：美工图/ 或 美工图片/
   ├─ 1.png / xd_1.jpeg / hou1.png ...
   └─ 已完成的美工套图
```

## 3. 第一步：选择真实商品图

不要直接让 Codex 根据标题生成产品。先跑：

```bash
python3 scripts/reference_selector.py   --comm-dir output/<类目>/沟通图片   --out output/<类目>/reference_manifest.json
```

输出里最重要的是：

```json
{
  "primary_product_refs": ["主图/real_product.jpg", "detail/product_detail.png"],
  "role_groups": {
    "product": [],
    "package": [],
    "detail": [],
    "size": [],
    "scene": [],
    "competitor": []
  },
  "vision_instruction": "Before generating any plate, inspect primary_product_refs..."
}
```

Cloud/Codex 视觉模型还要再确认一次：`primary_product_refs` 是否真的是售卖 SKU，而不是竞品图、详情页截图或场景示意。

## 4. 产品几何锁 Product Geometry Lock

ArtDirectorContract 必须包含：

```json
{
  "reference_images": ["..."],
  "product_geometry_lock": {
    "mode": "strict_reference_lock",
    "physical_length_to_width_ratio_estimate": 10.0,
    "rules": [
      "Use the attached/selected real product image as the immutable product anchor.",
      "Do not redraw the product from memory.",
      "Do not shorten, fatten, bend, recolor, repackage, mirror incorrectly, or simplify key structure."
    ]
  }
}
```

如果 SKU 或尺寸图里出现 `130 мм / длина` 和 `13 мм / ширина`，脚本会推导出约 `10:1` 的长宽比例。细长产品必须保持细长；变短变胖直接失败。

## 5. Codex 出图规则

Codex 必须拿到 `codex_jobs.jsonl` 里的 `reference_images`，并用 image edit / composite / inpaint 的方式围绕真实产品做场景。

Codex prompt 必须包含：

```text
Use the attached real product reference image(s) as the immutable product anchor.
Do not generate the product from text memory.
Preserve the same silhouette, length, width, color, material, package, count, and key structural details.
Do NOT render final readable Russian/Cyrillic text.
Do NOT draw placeholder text cards, empty rounded boxes, random UI frames, or label outlines.
Only leave smooth clean background in overlay safe zones.
Fill the entire 3:4 canvas edge-to-edge: no side white borders, no gutters, no empty left/right margins.
```

## 6. 叠字规则：overlay_text.py 拥有文字框

不要再让 Codex 先画空白文字框。原因是 Codex 的框位置随机，而脚本按固定区域叠字，必然错位。

现在由 `overlay_text.py` 负责：

- 绘制白色标题 pill
- 绘制绿色角标
- 绘制下划线标题，并保证下划线在文字下方而不是穿字
- 绘制尺寸卡片
- 绘制步骤卡片
- 绘制 callout 标签
- 叠加所有俄文

`overlay_text_plan` 必须有 normalized boxes：

```json
{
  "title": "РАЗМЕР И ЛЕЗВИЕ",
  "title_box": {"xywh": [0.06, 0.04, 0.88, 0.12], "style": "white_pill"},
  "badges": [
    {"text": "9 мм", "box": {"xywh": [0.06, 0.18, 0.25, 0.10], "style": "green_badge"}}
  ],
  "dimensions": [
    {"text": "130 мм / длина", "box": {"xywh": [0.68, 0.38, 0.26, 0.055], "style": "white_card"}}
  ],
  "steps": [
    {"caption": "ШАГ 1", "box": {"xywh": [0.08, 0.82, 0.20, 0.065], "style": "green_badge"}}
  ],
  "labels": []
}
```

默认会：

```text
trim_uniform_border
cover crop 到 3:4
绘制所有卡片和文字
```

如果确实不想裁切，可以：

```bash
python3 scripts/overlay_text.py plate.png contract.json   --slot-id hero-product   --out final.png   --fit-mode contain
```

## 7. 从真实样例蒸馏出的美工决策

本版已吸收 7 组真实样例：

| 案例 | 沟通图 | 美工图 | 美工核心取舍 |
|---|---:|---:|---|
| 透明硅胶后跟垫 | 33 | 8 | 灰白绿医护感；保护、尺寸、步骤、水洗、材质、前后对比、鞋型适配 |
| 冰箱除味剂 | 24 | 11 | 白绿厨房清新感；尺寸、保鲜对比、场景网格、材质吸附、阳光再生 |
| 轮胎充气接头 | 20 | 8 | 黑橙工业感；主图冲击力强，规格/步骤仍保持白底清晰 |
| 自穿线针套装 | 37 | 8 | 米色木质手工感；统一 12 支针，围绕木盒和金色针建立视觉锚点 |
| 美甲剪 | 26 | 17 | 粉蓝美容感；参数图极简，人物图建立沙龙结果和信任 |
| 办公切割工具 | 23 | 10 | 办公工具风；主图、尺寸、30°、SK2微距、结构圈注、三步使用、用途网格、拆包收口；避免做成手账生活海报 |
| 黄色鞋垫除味贴 | 27 | 8 | 黄绿柠檬天然感；包装、数量、尺寸、步骤、成分、鞋型、7 天效果 |

完整规则见：

```text
templates/designer_delta_bank.yaml
templates/reference_lock_rules.yaml
templates/design_paradigms.yaml
templates/art_director_rubric.yaml
```

办公切割工具固定 8 图位：

```text
1 主图：КАНЦЕЛЯРСКИЙ НОЖ + 9 мм + ДЛЯ БУМАГИ И УПАКОВКИ
2 尺寸：РАЗМЕР И ЛЕЗВИЕ，标 9 мм / 130 мм / 13 мм
3 角度：30° ДЛЯ ТОЧНОГО РЕЗА，角度标注贴近刀尖
4 材质：СТАЛЬ SK2，刀片微距证明金属边缘
5 结构：ОСНОВНЫЕ ОСОБЕННОСТИ，最多 4 个 callout
6 三步：ПРОСТОЕ ИСПОЛЬЗОВАНИЕ，动作必须不用读字也看得懂
7 场景：ДЛЯ РАЗНЫХ ЗАДАЧ，四格各出现同一 SKU
8 拆包：ДЛЯ РАСПАКОВКИ，刀尖必须落在纸箱胶带/缝隙上
```

## 8. 一键流程

正式流程：

```bash
python3 scripts/one_click_ru_listing.py \
  --standard-sku output/<类目>/standard_sku.json \
  --comm-dir output/<类目>/沟通图片 \
  --out-dir output/<类目>
```

`--slot-plan` 是可选覆盖。不要把旧 `orchestrate.py` 生成的 `plan.json` 当作这里的 `slot_plan.json` 传入。

它会生成：

```text
output/<类目>/reference_manifest.json
output/<类目>/art_director_contract.json
output/<类目>/codex_jobs.jsonl
```

`codex_jobs.jsonl` 每行包含：

```json
{
  "slot_id": "hero-product",
  "prompt": "...",
  "reference_images": ["/absolute/path/to/real_product.jpg"],
  "product_geometry_lock": {},
  "overlay_text_plan": {},
  "expected_plate": "plates/hero-product.png",
  "expected_final": "final/slot_hero-product.png"
}
```

生成 no-text plate、叠字并评分：

```bash
python3 scripts/codex_job_runner.py \
  --jobs output/<类目>/codex_jobs.jsonl \
  --contract output/<类目>/art_director_contract.json \
  --out-dir output/<类目> \
  --slots all \
  --max-workers 1 \
  --critic
```

如果已经有 no-text plate，只叠字不重新生成：

```bash
python3 scripts/one_click_ru_listing.py \
  --standard-sku output/<类目>/standard_sku.json \
  --reference-manifest output/<类目>/reference_manifest.json \
  --plate-dir output/<类目>/plates \
  --out-dir output/<类目>
```

## 9. Critic 硬阈值

通过标准：

```text
product_fidelity >= 8.5
geometry_lock >= 8.5
overlay_alignment >= 8.0
canvas_fill >= 8.0
weighted_score >= 7.8
no fake Cyrillic
no wrong quantity
no wrong material
no side gutters
```

产品一致性或几何锁低于阈值时，不要为了 CTR 继续美化，直接重跑或标记人工审核。

## 10. 样例继续蒸馏

后续继续喂“沟通图片 + 美工图”时，先跑：

```bash
python3 scripts/distill_designer_cases.py   --input-zips /path/to/*.zip   --out-dir training_cases
```

再用 `prompts/designer_delta_distillation.md` 和 `prompts/reference_image_selector.md` 继续补充规则库。
