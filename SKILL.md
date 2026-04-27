---
name: silk-life-listing-image-sop
description: 丝绸生活 Ozon listing 美工套图 SOP（端到端 8 图位）。当用户提到"丝绸生活出图"、"silk listing 套图"、"类目套图"、"Ozon 8 张图"、"沟通图片"+"美工图"、"生成商详套图"时触发。吃一个类目"沟通图片"文件夹（含 xlsx 卖点表 + 网上下载的产品参考图），自动产出 8 张符合丝绸生活视觉语言（俄语 SEO 大字 + 绿色数字角标 + 类目色温 + 手部演示）的 listing PNG，用 GPT-4V 反向校验产品一致性 + CTR 风险，低于阈值自动重跑。底层调 ozon-listing-image 的 image2 edit 模式。
---

# 丝绸生活 Ozon Listing 美工套图 SOP

> 把外部美工的工作蒸馏成 AI SOP。一次跑一个类目文件夹，1 小时内拿到 7 张套图 + 校验报告。

## 触发场景

- "丝绸生活 冰箱除味剂 出图"
- "silk listing 套图 抗菌鞋垫贴纸"
- "类目套图 美工刀"
- "Ozon 7 张图"
- "沟通图片转美工图"

## 端到端流程

```
输入：/Users/mac/Documents/ozns/丝绸生活/<类目>/沟通图片/
       ├─ listing.xlsx（俄文标题 + 12 卖点 + 中文描述 + 可选竞品 URL）
       ├─ 主_XX.jpg / main.png（产品白底图）
       └─ image_X.jpg / Description_X.jpg（参考图）
                ↓
[1] parse_input.scan_category()        — xlsx/xls 宽容解析 + 参考图分桶
[2] normalize.to_standard_sku()        — 字段归一化
[3] normalize.augment_with_vision()    — ⭐ GPT-4V 看产品参考图反推 product_desc_en
                                         （image2 模式必需，否则产品永远画错）
[4] slot_planner.build_plan()          — 7 SlotSpec 生成
[5] 8 slot **并行**（默认 4 worker，ThreadPoolExecutor）：
        edit.py 调 codex 内置 image_gen（默认）→ jiekou.ai gpt-image-2-edit（兜底）
        critic_gpt4v.review()         — 4 维评分（产品一致性 0.4 / 俄语 0.25 / 视觉层级 0.2 / CTR 风险 0.15）
        if score < threshold: 注入 negative hint 重跑（最多 2 次）
[6] report.render()                    — markdown 报告 + 4×2 拼版缩略图

输出：output/<类目>/
       ├─ slot_main.png ... slot_cert-review.png（8 张）
       ├─ standard_sku.json
       ├─ report.md（每张分数 + issues + 重跑次数）
       └─ contact_sheet.jpg
```

## CLI 入口

```bash
# 默认（推荐）：codex 内置 image_gen + 4 worker 并行 + jiekou 兜底
python3 ~/.config/opencode/skill/silk-life-listing-image-sop/scripts/orchestrate.py \
  --category-dir /Users/mac/Documents/ozns/丝绸生活/冰箱除味剂 \
  --out-dir /tmp/silk-life-test/冰箱除味剂

# 强制走 jiekou（旧链路、需要 jiekou API key）
python3 .../orchestrate.py --category-dir ... --out-dir ... --backend jiekou

# 串行调试（看每个 slot 输出）
python3 .../orchestrate.py --category-dir ... --out-dir ... --no-parallel

# 不让 codex 失败回退 jiekou（严格 codex-only）
python3 .../orchestrate.py --category-dir ... --out-dir ... --no-fallback
```

## Backend 选择

| Backend | 鉴权 | 计费 | 稳定性 | 默认 |
|---|---|---|---|---|
| `codex` | ChatGPT 登录态（无 API key） | ChatGPT 配额 | 强 | ✅ |
| `jiekou` | `~/.config/jiekou_api_key` | jiekou 套餐 | 偶发 5xx | 兜底 |

- 默认 `--backend codex --fallback`：codex 失败自动回退 jiekou
- codex 内置 `image_gen` 工具走 ChatGPT 通道，不消耗 jiekou 额度
- 单图实测：codex 90-150s（含 codex CLI 调度开销 ~60s），jiekou 60-120s
- 8 图 4 worker 并行 ≈ 2-4 min（vs 串行 13-20 min）

## 为什么不用 team-mode MCP

用户提到 "team-mode 拉多个 codex 成员"，实际实现走 ThreadPoolExecutor 而非 team-mode MCP。原因：

- team-mode MCP（`mcp__team-mode__*`）是 agent-to-agent 通信层（rooms / inbox / message），需要 agent 主动注册到 team 里
- codex CLI 是 subprocess，不会主动连 team-mode MCP server，无法成为 team member
- 我们要的核心是"并行 spawn N 个 codex 进程"——`concurrent.futures.ThreadPoolExecutor` 直接搞定，零依赖
- 每个 codex exec 子进程独立 thread_id（落到 `~/.codex/generated_images/<thread_id>/`），互不冲突
- 后续如需 observability（向 team-mode room 推送进度），可在 orchestrate.py 里加 progress_callback 钩子

## 8 图位标准序列（与历史美工图 xd_1.jpeg ~ xd_8.jpeg 对齐）

| Slot | 内容 | 关键视觉元素 | 数据来源 |
|---|---|---|---|
| 1 main | 主图 | 俄语 SEO 大字 + 绿色数字角标 + 手 | 标题 + 卖点 1 |
| 2 detail-size | 尺寸/规格图 | 数字标注 + 箭头 + 白底 | 卖点 2-3 |
| 3 detail-compare | 对比图 | ОБЫЧНЫЙ vs НАШ 分屏 | 卖点 4-5 |
| 4 material | 材质细节 | 微距特写 | 卖点 6-7 |
| 5 use-scene | 使用场景 | 类目色温 + 真实生活 | 卖点 8-9 |
| 6 hand-demo | 手部演示 | 手持/操作产品特写，"丝绸生活"独立强势元素 | 卖点 1（强化） |
| 7 package | 包装展示 | 盒装 + 数量徽章 | 卖点 10 |
| 8 cert-review | 认证/评价 | 5 星 + ХИТ 信任徽章 | 卖点 11-12 |

## "丝绸生活"视觉风格 Token

- 俄语粗体大字（Cyrillic）
- 绿色圆形/胶囊角标（含数字+单位"6 месяцев"/"12 штук"或生态词"без отдушки"）
- 手部真实演示
- **类目色温映射**：
  - 生活类（除味剂/后跟贴/鞋垫）→ 绿黄场景
  - 工具类（指甲剪/美工刀/轮胎接头/针套装）→ 深蓝/金属/木质

## 反向校验机制

| 维度 | 权重 | 评分依据 | 硬阈值 |
|---|---|---|---|
| 产品一致性 | 0.4 | 与参考图 body 比对（颜色、形状、关键特征） | < 8 强制重跑 |
| 俄语渲染 | 0.25 | OCR + 关键词命中率 | < 7 重跑 |
| 卖点视觉层级 | 0.2 | 主标题 / 角标 / 副文 三级清晰 | — |
| CTR 风险 | 0.15 | 字体劣质/布局拥挤/颜色脏扣分 | — |

加权 ≥ 7.5 通过。最多重跑 2 次，仍不过标记 `needs_human`，不阻塞其他 slot。

## 文件结构

```
silk-life-listing-image-sop/
├── SKILL.md                     # 本文件
├── scripts/
│   ├── orchestrate.py           # 主入口
│   ├── parse_input.py           # xlsx/xls 宽容解析 + 参考图分桶
│   ├── normalize.py             # 归一化 + GPT-4V 视觉反推 product_desc_en
│   ├── slot_planner.py          # 7 SlotSpec 生成
│   ├── critic_gpt4v.py          # GPT-4V 反向校验
│   └── report.py                # markdown + 拼版
├── templates/
│   ├── color_palette.yaml       # 类目→色温映射
│   └── critic_rubric.yaml       # 校验维度+权重+阈值
└── prompts/
    ├── visual_descriptor.md     # GPT-4V 视觉反推 system prompt
    └── critic_system.md         # GPT-4V 校验 system prompt
```

## 依赖

- ozon-listing-image skill（image2 edit 模式）— 底层调用
- jiekou.ai API key（`~/.config/jiekou_api_key`，与 ozon-listing-image 共用）
- Python：openpyxl, xlrd 1.x, Pillow, PyYAML（视觉反推与 critic 用 jiekou.ai 的 chat completions 端点，不用 openai SDK）

## 输入侧已知不一致（parse_input 已容错）

- 针套装 listing 是 `.xls` 古格式（OLE Composite，需要 xlrd 1.x）
- 轮胎充气接头 xlsx 列名只有 A/B/D（无俄语/中文标题）
- 后跟贴 sheet 名是 `Sheet1`、只有 8 行卖点
- 主图前缀混乱：`主_` / `主图_` / `main` 都有
- 美工图文件夹有的叫 `美工图片` 有的叫 `美工图`

## 触发场景关键词（更多）

- 丝绸生活、Ozon 7 图、套图、商详、listing、美工
- 冰箱除味剂、后跟贴、抗菌鞋垫贴纸、指甲剪、美工刀、轮胎充气接头、针套装
- 沟通图片、美工图、main 图、详情图

## 后续可扩展

- [ ] 接 Ozon API 自动 A/B 上架
- [ ] 7 天后自动从 mongo 拉 CR 数据出胜负判定
- [ ] 飞书自动推送 report.md
- [ ] mask 蒙版精确控制重绘区域（v2）
