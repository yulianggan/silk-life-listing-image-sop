# B2 v4 管道差距分析（commit 743ae21）

## 1. v4 自称修复 vs 用户硬要求 对照

| v4 自称修复 | 用户硬要求 | 是否对应 |
|-------------|------------|----------|
| 产品细节偏离实物 | 要求 2: 产品主体一致 | ✅ 完全对应 |
| Codex 不知道哪张是实物图 | 要求 2: 产品主体一致 | ✅ 完全对应 |
| 文字与预留空间错位 | 要求 4: 标题 ≤2 行 | ⚠️ 部分对应 |
| 左右留白过多 | 无直接对应 | ❌ 技术问题，非用户要求 |
| 旧直出链路误报通过 | 无直接对应 | ❌ 技术问题，非用户要求 |
| 美工刀风格跑偏 | 要求 6,7,8: slot 专用约束 | ⚠️ 部分对应 |

**核心发现**: v4 主要解决产品一致性（要求 2），但对其他 7 条硬要求覆盖不足。

## 2. 逐条要求的实现状态

### 要求 1：每张图回答购买问题
- **SKILL.md**: 第 7 节提及"买家 1 秒内能不能知道这张图回答的问题"
- **templates**: art_director_rubric.yaml - commercial_clarity 评分项
- **scripts**: art_director_contract.py:106 每个 slot 有 buyer_question 定义
- **critic**: critic_gpt4v.py 有 visual_hierarchy 评分，但无硬阈值
- **状态：SOFT-PROMPTED** - 有指导但无强制校验

### 要求 2：产品主体一致
- **SKILL.md**: 第 4 节完整的 product_geometry_lock 机制
- **templates**: reference_lock_rules.yaml:26-44 strict_reference_lock 规则
- **scripts**: reference_selector.py + art_director_contract.py:459-489 几何锁实现
- **critic**: art_director_rubric.yaml:16 product_fidelity_min: 8.5 硬阈值
- **状态：HARD-ENFORCED** - 完整管道强制执行

### 要求 3：手部场景不遮挡关键结构
- **SKILL.md**: 仅在 unboxing-scene 要求中提及"产品主体露出 60% 以上"
- **templates**: 无相关约束
- **scripts**: office_craft_slot_generation_requirements:880-890 部分 slot 有提及
- **critic**: 无专门检查
- **状态：MENTIONED** - 零星提及，无系统性约束

### 要求 4：标题短，最多 2 行
- **SKILL.md**: 无明确提及 2 行限制
- **templates**: 无约束
- **scripts**: overlay_text.py 有 max_lines 参数，但未统一设为 2
- **critic**: 无检查
- **状态：MISSING** - 完全未接入管道

### 要求 5：不重复手持场景
- **SKILL.md**: 无提及
- **templates**: 无约束  
- **scripts**: 无检查逻辑
- **critic**: 无检查
- **状态：MISSING** - 完全未接入管道

### 要求 6：材质图必须有刀片微距
- **SKILL.md**: 第 8 节 material-macro 规定"刀片微距证明金属边缘"
- **templates**: design_paradigms.yaml 有 material_macro 定义，但无刀具专用约束
- **scripts**: art_director_contract.py:863-867 office_craft_slot_generation_requirements 强制 blade macro
- **critic**: 无专门检查
- **状态：SOFT-PROMPTED** - slot 特定提示，但无校验

### 要求 7：尺寸图必须无手、无干净背景
- **SKILL.md**: 第 8 节 size-spec 明确禁止"no hand, no lifestyle props"
- **templates**: 无约束
- **scripts**: art_director_contract.py:847-851 office_craft_slot_generation_requirements 明确禁手
- **critic**: 无专门检查
- **状态：SOFT-PROMPTED** - 提示层面约束，无强制校验

### 要求 8：结构图完整+callout
- **SKILL.md**: 第 8 节定义 product-callouts 为"ОСНОВНЫЕ ОСОБЕННОСТИ"最多 4 个标注
- **templates**: 无约束
- **scripts**: art_director_contract.py:869-874 + overlay 计划生成 4 个标签位
- **critic**: 无专门检查  
- **状态：SOFT-PROMPTED** - overlay 规划支持，但无完整性校验

## 3. 高风险缺口（MISSING/MENTIONED 的）

**按影响排序的前 3 个缺口：**

1. **要求 5: 手持场景重复** (MISSING) - B0 发现这是唯一违规项，v4 完全未解决
2. **要求 4: 标题 ≤2 行** (MISSING) - 直接影响视觉层级和可读性
3. **要求 3: 手部遮挡关键结构** (MENTIONED) - 影响产品识别度，仅零星提及

## 4. 修补建议（仅指向位置，不写代码）

### 高优先级（MISSING 项）
- **手持场景重复校验**: 在 `critic_gpt4v.py` 增加 scene_repetition 评分维度
- **标题行数限制**: 在 `overlay_text.py` 统一设置 max_lines=2，在 `art_director_rubric.yaml` 添加硬阈值
- **手部遮挡检查**: 在 `codex_job_runner.py` local_acceptance_checks 增加产品可见度检查

### 中优先级（SOFT-PROMPTED 强化）
- **材质图刀片微距校验**: 在 `critic_gpt4v.py` 增加 slot 特定检查
- **尺寸图无手校验**: 在 `local_acceptance_checks` 增加手部检测
- **结构图完整性**: 在 overlay 计划中强制 4 个 callout，critic 检查标签数量

### 管道整合点
- **约束中心化**: templates/art_director_rubric.yaml 应包含所有 8 条硬要求的评分权重
- **slot 约束映射**: art_director_contract.py 的 office_craft_slot_generation_requirements 应覆盖所有相关 slot