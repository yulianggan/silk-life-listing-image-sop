# V7 通用 SOP — 事实驱动商业摄影规范

## 0. v7 设计原则（4 条北极星）

### 1. **真实优于美化**（用户硬规则 1）
产品必须保持真实外观和质感，禁止 AI 美化升级。通过 product_grade_anchor 约束市场定位，forbidden_upgrade_keywords 阻止奢华词汇。

### 2. **事实优于编造**（硬规则 2/3/4）
所有产品信息必须来自可追溯的数据源：
- 包装：仅基于 real_reference_image
- 尺寸：仅基于 dimensions.source 记录的数据
- 用途：仅基于 use_cases.source 记录的应用场景

### 3. **每图一证据**（硬规则 5）
7-8 个 slot 严格按买家问题分工，cross_topic_isolation 防止主题串联：
- 每个 slot 只回答其指定的买家问题
- 禁止跨 slot 信息污染
- 通过 slot_compliance 评分强制执行

### 4. **风格一致**（硬规则 7）
统一设计系统跨所有 slot：
- 单一字体族（Inter）
- 统一色彩系统（深蓝 #1a2b50、浅绿 #c8e8c4、白底）
- 一致圆角系统（pill_full, rounded_md, rounded_sm）

## 1. 数据流（pipeline 总图）

```
listing.xlsx + 沟通图片 + 人工输入
   ↓
sku_truth_v7.yaml（C0 schema）── 必填字段校验，缺则 BLOCK_SLOT_GENERATION
   ↓
slot_question_v7.yaml（7买家问题映射）+ material_profiles.yaml（材质约束）+ design_system.yaml（视觉标记）
   ↓
v7 prompt builder（C3 工程文档）── 事实验证 + 跨话题隔离 + 材质约束注入
   ↓
gpt-image-2 /v1/images/edits（已实施后端）
   ↓
v7 critic（现有 5 维度 + 新增 4 反造假维度）── weighted_score >= 7.5 + 所有 hard_gate >= 8.0
   ↓
失败 → 自动 fallback: (a) 纯文生图重试 (b) 降级 prompt 严苛度 (c) 人工介入
通过 → 商用级 8 图套图
```

## 2. 类目→archetype 映射决策树

```
产品类目识别（从 listing.xlsx / 沟通图片）
├─ category = "tools" 
│  ├─ 刀类 → archetype = "office_craft"
│  ├─ 剪刀 → archetype = "office_craft"
│  └─ 其他手工具 → archetype = "office_craft"
├─ category = "kitchen"
│  ├─ 刀具 → archetype = "kitchen_prep"
│  ├─ 容器 → archetype = "home_storage"
│  └─ 小电器 → archetype = "small_electronics"
├─ category = "cosmetics"
│  ├─ 化妆工具 → archetype = "beauty_care"
│  └─ 护理用品 → archetype = "grooming_tool"
├─ category = "home_storage"
│  └─ 收纳类 → archetype = "home_storage"
├─ category = "electronics"
│  └─ 小型设备 → archetype = "small_electronics"
└─ category = "fashion_accessories"
   └─ 配饰类 → archetype = "fashion_accessory"

material_profile 映射:
- 金属 sku_truth.material.primary → metal profile（反奢华约束）
- 塑料 → plastic profile（防过度光滑化）
- 织物 → fabric profile（保持真实垂感）
- 其他 → generic anti-beautification rules
```

## 3. 7 buyer questions × 8 slots 标准映射表

| 买家问题 | Slot ID | 证据类型 | 必填 sku_truth 字段 | 阻塞条件 |
|---------|---------|-----------|-------------------|---------|
| 什么 | hero-identification | identification | identity.* | identity 缺失 |
| 多大 | size-spec | dimensional | dimensions.*, dimensions.source | 所有 dimension 为空或 source 缺失 |
| 什么材质 | material-macro | material_quality | material.primary, material.finish, material.source | primary/finish 为空或 source 缺失 |
| 怎么造的 | product-callouts | structural_design | identity.category, use_cases[0..n] | category 缺失或 use_cases 为空 |
| 适合什么 | use-proof | usage_scenarios | use_cases[0..n], use_cases[*].source | use_cases 为空或任一 source 缺失 |
| 怎么用 | usage-demo | operation_proof | use_cases[0..n] | use_cases 为空 |
| 包装内容 | unboxing-scene | packaging_contents | packaging.has_real_reference_image=true, packaging.reference_files | 无真实包装参考 |
| 为何信任 | safety-trust | trust_indicators | product_grade_anchor.market_segment, identity.category | - |

**Hands Policy**: 7/8 slots 禁手，仅 usage-demo 允许手部出现（且手不能遮挡产品结构）

## 4. 缺字段降级矩阵

| 缺失字段 | 影响 Slots | 降级策略 | 示例 |
|---------|-----------|----------|------|
| dimensions.source | size-spec | BLOCK → 7图套装 | 无尺寸数据时跳过尺寸图 |
| packaging.has_real_reference_image=false | unboxing-scene | BLOCK → 7图套装 | 无真实包装时跳过开箱图 |
| use_cases 为空 | use-proof, usage-demo | BLOCK → 5图套装 | 无用途数据时跳过应用场景 |
| material.source 缺失 | material-macro | BLOCK → 降级材质展示 | 材质信息不明时跳过材质微距 |
| 所有必填字段缺失 | ALL slots | 管道终止 | 产品基本信息不全，无法生成 |

**降级优先级**: hero-identification > product-callouts > material-macro > size-spec > use-proof > usage-demo > unboxing-scene > safety-trust

## 5. critic 评分门控

### 现有 5 维度（weighted scoring）
- **product_consistency**: 40% 权重，>= 8.0 critical gate
- **cyrillic_render**: 25% 权重
- **visual_hierarchy**: 20% 权重  
- **ctr_risk**: 15% 权重
- **weighted_score**: >= 7.5 通过阈值

### 新增 4 维度（hard gates）
- **package_authenticity**: >= 8.0（防假包装）
- **dimension_provenance**: >= 8.0（防编造尺寸）
- **use_case_provenance**: >= 8.0（防编造用途）
- **metal_realism**: >= 8.0（仅金属产品，防过度美化）

### 总通过条件
```
PASS = weighted_score >= 7.5 
       AND product_consistency >= 8.0 
       AND ALL hard_gates >= 8.0
```

## 6. 失败 → 自动 fallback 策略

### A. Hard Gate Violations（事实性错误）
**触发信号**: package_authenticity < 8.0, dimension_provenance < 8.0, use_case_provenance < 8.0
**策略**: 
1. 检查 sku_truth 数据完整性
2. 重建 prompt 去除违规元素
3. 重新生成（最多 2 次）
4. 第 3 次失败 → 人工介入

### B. Product Consistency Violations
**触发信号**: product_consistency < 8.0  
**策略**:
1. 检查参考图匹配度
2. 增强产品身份约束 prompt
3. 重新生成（最多 3 次）

### C. Weighted Score Below Threshold
**触发信号**: weighted_score < 7.5
**策略**:
1. 分析具体维度短板（cyrillic_render / visual_hierarchy / ctr_risk）
2. 针对性优化 prompt（文字可读性 / 层次感 / 视觉吸引力）
3. 重试生成（最多 2 次）
4. 降级模式：减少文字元素或简化构图

### D. 成本控制
- 单 slot 重试上限：5 次
- 总成本预算：单套图 $3.0，超预算启动人工介入
- 连续失败 3 个 slot → 暂停管道，review sku_truth 质量

## 7. 商用级套图判收标准

### 硬通过条件（critic 自动）
- [x] 所有 hard gate >= 8.0
- [x] weighted_score >= 7.5  
- [x] product_consistency >= 8.0
- [x] 无 cross_topic_contamination

### 人工验收清单
- [x] **产品一致性**: 8 张图展示同一 SKU，无异形变体
- [x] **俄语文字**: 所有西里尔字母清晰可读，无乱码
- [x] **用途真实**: 使用场景可追溯到 listing 或沟通材料
- [x] **尺寸准确**: 展示的数字来源可查，无编造测量值
- [x] **材质真实**: 材料质感符合实际档次，无过度美化
- [x] **风格统一**: 色彩、字体、圆角系统在 8 图中保持一致
- [x] **无手遮挡**: usage-demo 中手部不阻挡产品关键结构

### 商用就绪标准
1. **转换目的**: 每张图回答特定买家疑问，有明确购买证据
2. **事实保证**: 所有信息可追溯到 sku_truth 数据源
3. **视觉专业**: 达到 Ozon 平台标准，符合俄罗斯电商审美
4. **合规安全**: 无误导信息，无编造规格，无夸大宣传

**最终判收**: critic 通过 + 人工验收通过 + 单次性价比 < $0.5/图 = 商用级套图