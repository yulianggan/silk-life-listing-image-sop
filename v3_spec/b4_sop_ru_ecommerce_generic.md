# 通用俄罗斯电商美工做图 SOP（v1）

## 0. 版本与适用

- **适用范围**: 俄罗斯 Ozon/Wildberries 单 SKU 8 主图套图
- **不适用**: 详情长图、视频广告、A+ 图文、品牌故事图
- **基础版本**: 基于 silk-life 美工刀 v3 规范抽象而来
- **更新日期**: 2026-04-29

## 1. 不变核心（8 条铁律）

基于用户 8 硬要求 + B1 证据语法精炼，所有类目必须遵循：

### 1.1 购买问题映射原则
- **铁律1**: 每张图必须回答一个具体购买问题
- **俄语买家决策路径**: "Что это?" → "Какого размера?" → "Как устроен?" → "Из чего сделан?" → "Безопасен ли?" → "Как использовать?" → "Что в упаковке?" → "Подходит мне?"

### 1.2 视觉一致性约束
- **铁律2**: 产品主体必须像同一个实物（颜色、材质、logo、细节完全一致）
- **铁律3**: 手部和场景不能遮挡关键结构

### 1.3 文字overlay规范
- **铁律4**: 标题短，最多 2 行（俄语≤70字符/行）
- 字体: Roboto 或 Open Sans，粗体
- 字号: 最小 24pt，最大 36pt
- 颜色: 白色底黑字，或半透明深色背景

### 1.4 场景防重复机制
- **铁律5**: 不要重复做普通手持场景
- 整套8图中，普通生活场景≤1张
- 允许例外: 专业使用演示（不算普通生活场景）

### 1.5 三类证据强制执行
- **铁律6**: 材质证据必须有微距特写（具体标准见类目侧写）
- **铁律7**: 尺寸证据必须无手、无复杂背景
- **铁律8**: 结构证据必须完整展示产品并做 callout 标注

## 2. 8-Slot 通用模板

基于 B3 美工刀规范抽象为 placeholder：

```yaml
slot_distribution:
  evidence_coverage:
    physical_evidence: 3  # size, structure, material
    purchase_moments: 3   # identification×2, packaging, safety
    functional_proof: 1   # use_proof
    visual_completeness: 1 # angle_variant
  
  hands_control:
    hands_forbidden: 7
    hands_allowed: 1      # 仅use_proof可含手，且不遮挡结构
    ordinary_lifestyle_scenes: 0

slot_mapping:
  1_hero_identification:
    buyer_question_ru: "Что это за продукт?"
    evidence_type: identification
    constraints: [clean_background, complete_product, no_hands]
    
  2_size_evidence:
    buyer_question_ru: "Какого размера?"
    evidence_type: size
    constraints: [measurement_visible, no_hands, clean_background]
    
  3_structure_evidence:
    buyer_question_ru: "Как устроен?"
    evidence_type: structure
    constraints: [callout_annotations, complete_display, no_hands]
    
  4_material_evidence:
    buyer_question_ru: "Из чего сделан?"
    evidence_type: material
    constraints: [macro_detail, quality_visible, no_hands]
    
  5_packaging_display:
    buyer_question_ru: "Что в упаковке?"
    evidence_type: packaging
    constraints: [contents_visible, no_hands, clean_layout]
    
  6_safety_certification:
    buyer_question_ru: "Безопасен ли?"
    evidence_type: safety
    constraints: [certifications_visible, warnings_clear, no_hands]
    
  7_use_proof_action:
    buyer_question_ru: "Как использовать?"
    evidence_type: use_proof
    constraints: [hands_allowed, structure_not_blocked, realistic_use]
    
  8_hero_variant_angle:
    buyer_question_ru: "Подходит мне?"
    evidence_type: angle_variant
    constraints: [different_angle, complete_product, no_hands]
```

## 3. 类目侧写

### 3.1 手工/工具类
**代表产品**: 美工刀、剪刀、改锥、钳子、锯子

**证据权重排序**: 材质 ≫ 安全 ≫ 结构 ≫ 尺寸

**必备 slot 调整**:
- `material_evidence`: 必须有刀刃/金属部分微距，显示材质纹理
- `safety_certification`: 必须显示安全警告、CE/ГОСТ标记
- `structure_evidence`: 必须 callout 关键部件（手柄、刀片、锁定机构）
- `use_proof_action`: 允许戴手套演示，但不能遮挡工具结构

**禁忌事项**:
- 不要在材质图中包含复杂背景道具
- 不要在同一套图中重复相似的手持角度
- 安全类工具禁止儿童入镜

**推荐俄文买家问题**:
1. "Нож острый?" (刀锋利吗?)
2. "Ручка удобная?" (手柄舒适吗?)
3. "Металл качественный?" (金属质量好吗?)
4. "Безопасно для детей?" (对儿童安全吗?)
5. "Лезвие сменное?" (刀片可更换吗?)

### 3.2 厨房/烘焙类
**代表产品**: 菜板、模具、揉面垫、蛋糕框、硅胶铲

**证据权重排序**: 尺寸 ≫ 材质 ≫ 使用场景 ≫ 安全

**必备 slot 调整**:
- `size_evidence`: 必须显示与标准厨具的尺寸对比
- `material_evidence`: 必须显示食品级材质标记、纹理特写
- `use_proof_action`: 允许食材道具，但产品必须是主体
- `safety_certification`: 必须显示食品级认证标志

**禁忌事项**:
- 食材道具不能盖过产品主体
- 不要使用生肉等可能引起不适的食材
- 避免过于复杂的烹饪场景

**推荐俄文买家问题**:
1. "Размер подходит?" (尺寸合适吗?)
2. "Материал пищевой?" (材料是食品级的吗?)
3. "Легко мыть?" (容易清洗吗?)
4. "Можно в посудомойке?" (可以用洗碗机吗?)
5. "Выдержит температуру?" (耐高温吗?)

### 3.3 家居/收纳类
**代表产品**: 收纳盒、挂钩、衣架、垃圾桶、置物架

**证据权重排序**: 尺寸 ≫ 容量 ≫ 装载示例 ≫ 材质

**必备 slot 调整**:
- `size_evidence`: 必须显示精确尺寸标注和参照物对比
- `structure_evidence`: 必须显示承重结构、安装方式
- `use_proof_action`: 必须显示装载容量演示
- `material_evidence`: 突出耐用性、防水防潮特性

**核心买家关切**: "装多少" 是核心问题，必有容量证据图

**禁忌事项**:
- 不要用过于凌乱的装载演示
- 避免显示品牌logo过多的装载物品
- 承重演示要现实合理

**推荐俄文买家问题**:
1. "Сколько помещается?" (能放多少?)
2. "Выдержит вес?" (能承受重量吗?)
3. "Легко монтировать?" (容易安装吗?)
4. "Материал прочный?" (材料结实吗?)
5. "Подходит размер?" (尺寸合适吗?)

### 3.4 化妆/美容类
**代表产品**: 化妆刷、美容仪、眼影盘、口红、面膜

**证据权重排序**: 材质 ≫ 使用过程 ≫ 安全 ≫ 包装

**必备 slot 调整**:
- `material_evidence`: 刷毛微距、硅胶材质特写
- `use_proof_action`: 使用过程演示，但不能露脸
- `safety_certification`: 显示皮肤测试、无害认证
- `packaging_display`: 突出卫生包装、密封性

**关键材质标准**: "刷毛微距" 等于材质证据的核心

**禁忌事项**:
- 使用过程不要露脸（用手部或局部演示）
- 避免夸张的美妆效果宣传
- 不要使用可能过敏的演示场景

**推荐俄文买家问题**:
1. "Материал безопасный?" (材料安全吗?)
2. "Мягкие щетинки?" (刷毛柔软吗?)
3. "Легко чистить?" (容易清洁吗?)
4. "Гипоаллергенно?" (低过敏吗?)
5. "Качество сборки?" (制作质量如何?)

### 3.5 小电器类
**代表产品**: 吹风机、剃须刀、电动牙刷、加湿器、充电器

**证据权重排序**: 结构 ≫ 安全/认证 ≫ 使用场景 ≫ 包装

**必备 slot 调整**:
- `structure_evidence`: 接口、电源、按钮必须 callout
- `safety_certification`: 必须显示CE、RoHS等电器认证
- `use_proof_action`: 显示操作过程，突出便利性
- `material_evidence`: 突出外壳材质、散热设计

**电器特殊要求**: 接口、电源、按钮必须清晰标注

**禁忌事项**:
- 不要在潮湿环境中演示电器
- 避免显示不当的电器使用方式
- 充电类产品必须显示接口兼容性

**推荐俄文买家问题**:
1. "Какая мощность?" (功率多大?)
2. "Безопасно использовать?" (使用安全吗?)
3. "Удобно держать?" (握持舒适吗?)
4. "Какой разъём?" (什么接口?)
5. "Есть гарантия?" (有保修吗?)

### 3.6 服饰/配件类
**代表产品**: 皮带、钱包、手表、围巾、帽子

**证据权重排序**: 材质 ≫ 尺寸 ≫ 搭配 ≫ 工艺

**必备 slot 调整**:
- `material_evidence`: 五金件、纹理微距是材质核心
- `size_evidence`: 必须显示尺码对照、可调节范围
- `structure_evidence`: 显示缝线、工艺细节
- `use_proof_action`: 搭配演示，不露脸

**材质核心**: 五金件光泽、皮革纹理、缝线工艺

**禁忌事项**:
- 搭配演示不要过于时尚杂志化
- 避免显示完整人物形象
- 价格敏感类别不要过度包装

**推荐俄文买家问题**:
1. "Материал натуральный?" (材料天然吗?)
2. "Размер регулируется?" (尺寸可调吗?)
3. "Качество фурнитуры?" (五金质量如何?)
4. "Подойдёт стиль?" (风格合适吗?)
5. "Прочная ли строчка?" (缝线结实吗?)

## 4. 文字 Overlay 规范

### 4.1 技术参数
- **字体族**: Roboto (优先) / Open Sans / Arial
- **字重**: Bold (700) 主标题，Medium (500) 副标题
- **字号范围**: 24pt-36pt 主标题，18pt-24pt 副标题
- **行间距**: 1.2-1.4 倍
- **字符限制**: 俄语 ≤70 字符/行，≤2行

### 4.2 视觉层次
```
背景 → 半透明遮罩 → 文字内容 → 描边增强
```

### 4.3 安全位置
- **主标题**: 距离边缘 ≥60px，避开产品关键部分
- **副标题**: 距离主标题 ≥20px 垂直间距
- **callout**: 指向线条粗细 2-3px，箭头明确

### 4.4 颜色系统
- **白底黑字**: 背景#FFFFFF，文字#1a1a1a
- **深底白字**: 背景rgba(0,0,0,0.7)，文字#FFFFFF
- **强调色**: 避免使用，保持简洁

## 5. Critic 检查清单

### 5.1 程序化可验证项

**自动检测函数**:
```python
# 标题合规检查
validate_title_line_count(image, max_lines=2, max_chars_per_line=70)

# 手部遮挡检测
detect_hands_blocking_structure(image) -> boolean

# 材质微距验证（类目特定）
verify_macro_quality(image, category_type) -> score

# 生活场景计数
count_lifestyle_scenes(image_set) -> count <= 1

# 尺寸证据验证
validate_size_evidence(image) -> has_reference & clean_background

# 结构callout检测
detect_callout_annotations(image) -> count >= 3
```

### 5.2 人工抽检项

**视觉质量检查**:
- [ ] 产品一致性（颜色、材质、细节匹配）
- [ ] 俄文文字语法正确性
- [ ] 证据类型与买家问题匹配度
- [ ] 整体套图视觉平衡

**买家视角验证**:
- [ ] 8个购买问题是否都有答案
- [ ] 关键决策信息是否清晰可见
- [ ] 是否符合俄罗斯电商用户习惯

## 6. 落地链路（如何与 v4 silk-life pipeline 对接）

### 6.1 新增文件结构
```
templates/
├── category_profiles.yaml          # 新文件：类目侧写配置
└── slot_matrix_generic.yaml        # 新文件：通用8-slot模板

scripts/
├── category_profile_loader.py      # 新模块：动态加载类目配置
├── critic.py                      # 增强：新增程序化验证函数
└── evidence_validator.py          # 新模块：证据类型验证器
```

### 6.2 配置加载流程
```python
# 1. SKU类目识别
category = detect_product_category(sku_title, description)

# 2. 类目侧写加载
profile = load_category_profile(category)

# 3. 8-slot模板覆盖
slot_config = merge_generic_slots_with_category_profile(
    base_slots=generic_8slot_template,
    category_profile=profile
)

# 4. 约束强制执行
constraints = enforce_hard_constraints(slot_config, user_8_requirements)
```

### 6.3 Critic 集成
```python
# critic_gpt4v.py 新增
def validate_generic_constraints(image_set, category_profile):
    results = {}
    
    # 程序化硬约束
    results['title_lines'] = validate_title_line_count(image_set)
    results['hands_blocking'] = detect_hands_blocking_structure(image_set)
    results['lifestyle_count'] = count_lifestyle_scenes(image_set)
    
    # 类目特定约束
    if category_profile['type'] == 'tools':
        results['blade_macro'] = verify_blade_macro(image_set)
    elif category_profile['type'] == 'kitchen':
        results['food_grade'] = verify_food_grade_marks(image_set)
    
    return results
```

### 6.4 模板系统升级
```yaml
# art_director_rubric.yaml 新增权重
constraint_enforcement:
  hard_constraints_weight: 0.60    # 提升硬约束权重
  aesthetic_quality_weight: 0.25   # 降低美学权重
  category_compliance_weight: 0.15 # 新增类目合规权重

validation_functions:
  - validate_title_line_count
  - detect_hands_blocking_structure
  - verify_category_evidence
  - count_lifestyle_scenes
```

## 7. 失败案例库（来自 v3/final 复审）

基于 DevFleet B0 取证复审发现的问题模式：

### 7.1 手持场景重复违规
**失败案例**: `slot_ergo-handhold.png`, `slot_repair-home-scene.png`, `slot_unboxing-scene.png`

**违规模式**: 3/8 图都是普通手持生活场景，无法提供差异化购买信息

**修复方法**: 
- 整套图中普通生活场景≤1张
- 其他手持必须是专业使用演示（如安装、维修、精确操作）
- 每个场景必须回答不同的买家问题

### 7.2 结构信息不足
**失败案例**: `slot_structure-steps.png` 命名暗示分步说明，但实际缺乏callout

**违规模式**: 结构图没有清晰标注关键部件功能

**修复方法**:
- 必须有≥3个callout标注
- 标注文字必须是功能说明，不是纯装饰
- 整个产品必须完整可见

### 7.3 尺寸信息缺失
**失败案例**: 整套v3图没有专门的尺寸对比图

**违规模式**: 买家无法判断产品实际大小

**修复方法**:
- 必须有1张专门的尺寸证据图
- 使用标准参照物（硬币、卡片、尺子）
- 背景干净，无手部遮挡

### 7.4 成功模式学习
**成功案例**: 产品主体一致性优秀，所有图中的美工刀外观完全一致

**成功要素**:
- 颜色、材质、logo位置、磨损程度一致
- 同一物理对象的视觉连贯性
- 品牌标识清晰可见

## 结语

本 SOP 将 silk-life 美工刀的成功经验抽象为通用框架，通过类目侧写系统实现跨品类复用。核心理念是程序化约束执行，确保每张图都能回答具体购买问题，同时满足俄罗斯电商平台的用户决策需求。

**版本更新路径**: 
- v1 → v2: 增加更多类目侧写
- v2 → v3: 增强程序化验证算法
- v3 → v4: 集成转化率反馈机制