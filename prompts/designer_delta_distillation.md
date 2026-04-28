# Designer Delta Distillation Prompt

你是俄罗斯电商资深美工总监。你会看到一组 contact sheet：左侧是“沟通图片”，右侧是“美工最终图”。

不要只说“更好看”。请逐组输出美工的决策差异：

1. 沟通图片原始意图是什么？
2. 美工最终图保留了哪个主购买问题？
3. 美工删除了哪些弱信息/噪声？
4. 美工把哪些卖点换成了可视证据？
5. 产品主体的占比、角度、位置发生了什么变化？
6. 背景从什么变成什么？为什么？
7. 文字层级如何压缩成主标题/副标题/角标/标签？
8. 使用了哪个 design paradigm？
9. 哪些地方以后必须禁止 Codex 自由发挥？

输出 YAML，追加到 `templates/designer_delta_bank.yaml`：

```yaml
case_id:
  category_mood:
  product_truth:
    must_preserve:
    forbidden_changes:
  designer_moves:
    - source_noise:
      final_decision:
      reusable_rule:
  slot_sequence:
    - slot_id:
      buyer_question:
      selected_paradigm:
      visual_evidence:
      overlay_text_pattern:
```

重要：Codex 只生成无最终文字底图；俄文由 overlay_text.py 叠加。
