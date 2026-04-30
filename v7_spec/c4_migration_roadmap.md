# V6→V7 工程迁移路线图

## 关键风险

### 1. **prompt 构造器重写风险（高）**
- **风险**: v6 prompt 构造逻辑深度重写，可能破坏现有美工刀/剪刀 archetype 经验
- **Mitigation**: 保留 v6 prompt 作为 fallback，渐进式迁移单个 archetype
- **监控指标**: v7 vs v6 critic 通过率对比，前 3 周必须 >= 85%

### 2. **sku_truth 数据准备成本（中）**
- **风险**: 每个 SKU 需要详细事实标注，工作量可能 10x 增长
- **Mitigation**: 实施智能默认值 + 半自动 listing.xlsx 解析，人工只填补空缺
- **监控指标**: sku_truth 完成时间 < 5min/SKU

### 3. **critic 新维度调优困难（中）**
- **风险**: 4 个新 hard gate 可能过于严格，导致合格率暴跌
- **Mitigation**: 分阶段启用，先 warning 模式运行 2 周收集数据
- **监控指标**: hard gate 通过率 >= 60%（初期）→ >= 80%（稳定期）

## 第一周可交付的最小可商用版本

**目标**: M1-M5 + M8 实现基础 v7 管道，支持美工刀/剪刀两类目基线验证

**交付标准**:
- sku_truth 加载和基础校验 ✅
- v7 prompt 构造器核心逻辑 ✅  
- critic 集成 4 新维度（warning 模式）✅
- 美工刀 + 剪刀回归测试通过 ✅
- 成本控制 < $1.0/套图 ✅

---

## 迁移步骤甘特卡

| 步骤 | 做什么 | 改哪里（文件） | 工作量 | 风险 | 依赖关系 |
|---|---|---|---|---|---|
| **M1** | 实现 sku_truth.yaml 加载与校验 | 新增 `scripts/sku_truth_loader.py` | 半天 | 低 | 无 |
| **M2** | 改造 prompt 构造器走 v7 架构 | 重写 `scripts/art_director_contract.py` 核心函数 | 2 天 | 高 | M1 |
| **M3** | critic 新增 4 反造假维度 | 改 `scripts/critic_gpt4v.py` + 新增材质 profile 加载 | 1 天 | 中 | M1 |
| **M4** | codex_job_runner 接入 v7 fallback | 改 `scripts/codex_job_runner.py:run_one` 逻辑 | 半天 | 中 | M2, M3 |
| **M5** | 设计系统 token 注入器 | 新增 `scripts/design_token_renderer.py` | 1 天 | 低 | 无（可并行 M1-M4） |
| **M6** | v6 实测套图回归基线 | 新增 `tests/regression/v6_baseline.json` | 半天 | 低 | M4 |
| **M7** | listing.xlsx 自动解析为 sku_truth | 新增 `scripts/listing_xlsx_to_sku_truth.py` | 1 天 | 中 | M1（可并行） |
| **M8** | 美工刀 + 剪刀两类目回归验证 | run_v7 全套，对比 v6 基线 | 半天 | 中 | M1-M6 全部 |
| **M9** | 新类目试跑（厨房/家居/化妆品选一） | 选品 + sku_truth 准备 + run_v7 | 1 天 | 中 | M8 |
| **M10** | 文档和模板生产化 | 更新 `SKILL.md` + commit `v7_spec/` 到 master | 半天 | 低 | M9 |
| **M11** | 退役 overlay_text 兼容代码 | 删除 v3-v5 代码路径，简化管道 | 2 小时 | 低 | M10（确认 v7 稳定后） |
| **M12** | 上线后转化数据回收评估 | 1 周后分析 Ozon CTR/转化率 vs v6 | - | - | M11 + 1周 |

### 并行性分析

**Week 1 并行轨道**:
- 轨道 A: M1 → M2 → M4（核心数据流）  
- 轨道 B: M3（critic 扩展）
- 轨道 C: M5, M7（工具链扩展）

**Week 2 整合**:
- M6 → M8（验证轨道）
- M9 → M10（扩展和文档化）

**Week 3+ 清理**:
- M11（代码清理）
- M12（效果评估）

---

## 详细实施方案

### M1: SKU Truth 加载器 (0.5天)
```python
# scripts/sku_truth_loader.py
class SkuTruthLoader:
    def __init__(self, sku_truth_path: Path):
        self.sku_truth = self._load_and_validate(sku_truth_path)
    
    def _load_and_validate(self, path: Path) -> dict:
        # 加载 YAML + 根据 c0_sku_truth_v7.yaml schema 校验
    
    def get_blocking_conditions(self, slot_id: str) -> List[str]:
        # 返回该 slot 的阻塞条件列表
    
    def validate_slot_requirements(self, slot_id: str) -> ValidationResult:
        # 检查 slot 所需字段是否存在
```

**交付物**: 
- 校验器可以成功 BLOCK 缺字段的 slot
- 加载器接受 JSON/YAML 两种格式
- 错误信息明确指出缺失字段和修补建议

### M2: Prompt 构造器重写 (2天)
```python
# scripts/art_director_contract.py 主要改动
def office_craft_slot_generation_requirements_v7(sku_truth, slot_def):
    # 替换现有的 office_craft_slot_generation_requirements
    
    # 1. 预验证门控
    validation = validate_sku_truth_requirements(sku_truth, slot_def)
    if validation.has_blocking_violations:
        raise BlockSlotGeneration(validation.blocking_reasons)
    
    # 2. 身份锁定（防美化升级）
    identity_constraints = render_identity_lock(sku_truth.product_grade_anchor)
    
    # 3. slot 专用证据规则  
    slot_rules = render_slot_evidence_rules(slot_def)
    
    # 4. 材质约束（如果适用）
    material_constraints = []
    if sku_truth.material.primary:
        material_profile = load_material_profile(sku_truth.material.primary)
        material_constraints = render_material_constraints(material_profile)
    
    # 5. 设计系统 token 注入
    visual_components = render_visual_components(slot_def.slot_id)
    
    return build_final_prompt(identity_constraints, slot_rules, material_constraints, visual_components)
```

**迁移策略**:
- 保留原 `office_craft_slot_generation_requirements` 作为 `_v6_fallback`
- 新函数先在测试模式运行，critic 对比两版本输出
- v7 通过率 >= 80% 后正式切换

### M3: Critic 扩展 (1天)
```python
# scripts/critic_gpt4v.py 主要改动
def review_with_anti_fabrication(api_key, generated_png, reference_img, slot_id, sku_truth=None):
    # 现有 5 维度保持不变
    base_scores = review_base_dimensions(api_key, generated_png, reference_img, slot_id)
    
    # 新增 4 反造假维度（仅当 sku_truth 存在时）
    anti_fab_scores = {}
    if sku_truth:
        anti_fab_scores = review_anti_fabrication_dimensions(
            generated_png, sku_truth, slot_id
        )
    
    # 综合评分逻辑
    weighted_score = calculate_weighted_score(base_scores)  
    hard_gate_passed = check_all_hard_gates(base_scores, anti_fab_scores)
    
    return {
        "scores": {**base_scores, **anti_fab_scores},
        "weighted_score": weighted_score,
        "hard_gate_passed": hard_gate_passed,
        "overall_passed": weighted_score >= 7.5 and hard_gate_passed
    }
```

**集成方式**:
- 新维度前 2 周 warning 模式（记录分数但不影响通过率）
- 收集 hard gate 分布数据，调优阈值
- 第 3 周起正式启用作为阻塞门控

### M4: Job Runner 整合 (0.5天)
```python
# scripts/codex_job_runner.py 改动
def run_one(config):
    # 现有逻辑保持，在 prompt 构造前加载 sku_truth
    if config.get("sku_truth_path"):
        sku_truth = load_sku_truth(config.sku_truth_path)
    else:
        sku_truth = None  # 兼容性回退
    
    # 传递 sku_truth 到 prompt 构造器和 critic
    prompt = art_director_contract.generate_v7_prompt(sku_truth, slot_def)
    
    # critic 调用新接口
    critique = critic_gpt4v.review_with_anti_fabrication(
        api_key, generated_png, reference_img, slot_id, sku_truth
    )
    
    # 失败 fallback 逻辑
    if not critique.overall_passed:
        return handle_v7_fallback(critique.failure_reasons, sku_truth, config)
```

### M6: 回归基线建立 (0.5天)
```json
// tests/regression/v6_baseline.json
{
  "baselineVersion": "v6_final",
  "testCases": [
    {
      "sku": "silk_beauty_knife_001",
      "archetype": "office_craft", 
      "v6Results": {
        "critic_scores": {"product_consistency": 8.2, "weighted": 7.8},
        "cost": "$2.40",
        "generation_time": "8m32s",
        "manual_approval": true
      }
    },
    {
      "sku": "silk_scissors_001", 
      "archetype": "office_craft",
      "v6Results": {
        "critic_scores": {"product_consistency": 7.9, "weighted": 7.6},
        "cost": "$2.80", 
        "generation_time": "11m05s",
        "manual_approval": false,
        "issues": ["fabricated_packaging", "invented_dimensions"]
      }
    }
  ],
  "acceptance_criteria": {
    "cost_regression_threshold": "110%",  // v7 成本不超过 v6 的 110%
    "critic_regression_threshold": "95%",  // v7 评分不低于 v6 的 95%
    "manual_approval_improvement": ">= v6"  // 人工通过率不能下降
  }
}
```

### M8: 回归验证 (0.5天)
```bash
# 回归测试脚本
python scripts/run_v7_regression.py \
  --baseline tests/regression/v6_baseline.json \
  --test-skus silk_beauty_knife_001,silk_scissors_001 \
  --output tests/regression/v7_results.json \
  --compare-mode
```

**验收标准**:
- [x] 成本控制: v7 <= v6 * 1.1
- [x] 质量保证: v7 critic >= v6 critic * 0.95  
- [x] 事实正确性: v7 hard gate >= 8.0（新增能力）
- [x] 视觉一致性: 设计系统 token 正确渲染

---

## 风险应急预案

### A. M2 Prompt 重写失败
**症状**: v7 生成质量显著低于 v6，critic 通过率 < 60%
**应急方案**: 
1. 立即回退到 `_v6_fallback` prompt 路径
2. 分析失败案例，逐个 slot 调优  
3. 延长 M2 时间到 1 周，获取更多调优数据

### B. M3 Hard Gate 过严
**症状**: 4 新维度通过率 < 40%，大量误杀
**应急方案**:
1. 降低阈值到 6.0（临时）
2. 增加 2 周数据收集期
3. 重新标定基于实际数据的合理阈值

### C. M8 回归失败  
**症状**: v7 整体表现不如 v6 基线
**应急方案**:
1. v7 保持实验分支状态，不合并 master
2. 识别核心失败点（cost/quality/consistency）
3. 重新评估 v7 架构可行性，必要时分阶段实施

---

## 成功衡量指标

### 技术指标
- **生成成功率**: >= 85%（vs v6 的 78%）
- **Critic 通过率**: >= 80%（vs v6 的 72%）
- **事实准确率**: >= 95%（v6 无此指标，v7 新增能力）
- **成本控制**: <= $2.5/套图（vs v6 的 $2.8）

### 商业指标  
- **人工审核时间**: <= 2min/套图（vs v6 的 5min）
- **返工率**: <= 10%（vs v6 的 25%）
- **上线转化率**: >= v6 基线（通过 M12 数据验证）

### 用户体验指标
- **SKU 准备时间**: <= 5min/SKU（包含 sku_truth 填写）
- **管道执行时间**: <= 15min/套图（vs v6 的 18min）
- **错误定位时间**: <= 1min（通过明确错误提示）

**里程碑判断**: 所有技术指标达标 + 至少 2/3 商业指标改善 = v7 迁移成功