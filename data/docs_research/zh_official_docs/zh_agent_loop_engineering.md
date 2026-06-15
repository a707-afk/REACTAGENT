<!-- source: AI辅助整理 - 基于 Loop Engineering 2026 指南、Agent Harness Patterns -->
<!-- category: agent-harness/loop-engineering -->
<!-- language: zh-CN -->

# Loop Engineering：从 Prompt Engineering 到系统级 Agent 设计

## 什么是 Loop Engineering？

Prompt Engineering 优化**单次交互**。Loop Engineering 把单次交互变成**可重复、可验证的系统**。

**核心公式**：`Loop = Trigger + Verifiable Goal + Agent + Verification + Guardrails + Memory`

对比传统 ReAct：

| | ReAct | Loop Engineering |
|---|---|---|
| 抽象层级 | 单步循环（think→act→observe） | 系统级（trigger→goal→verify→guardrail→retry） |
| 终止条件 | 步数上限或 LLM 说"完成" | 外部验证器确认目标达成 |
| 质量保证 | 靠 LLM 自觉 | Verification Gate（不信任 LLM 自评） |
| 失败处理 | 报错退出 | Guardrails（降级、重试、HITL） |

## 为什么 ReAct 不够用？

ReAct 的致命缺陷：**LLM 自我评估不可靠**。Agent 说"我已经收集到足够信息了"，但实际上漏了关键数据——因为 LLM 无法客观判断自己的输出质量。

Loop Engineering 的解决方案：**外部验证器**。

```
while not verified:
    Think → Act → Observe
    VerificationGate: faithfulness_check + coverage_check
    通过 → 综合输出
    没通过 → 识别缺失 → 重新检索
```

## Verification Gate 设计

验证器不是一次性的，它持续检查 Agent 的输出：

1. **faithfulness_check**：每个事实陈述是否被检索到的源文档支撑（句级 grounding）
2. **coverage_check**：答案是否覆盖了问题的所有方面（与预期 gold facts 匹配）
3. **quality_check**：答案是否有逻辑矛盾、是否引用了足够的源

**关键设计决策**：验证器不信任 LLM 自评。用规则引擎 + 嵌入相似度做客观检查。

## Guardrails：安全网

当 Verification Gate 反复失败时，Guardrails 防止无限循环：

- **max_iterations**：硬上限，防止无限检索
- **cost_limit**：token 预算上限
- **timeout**：总时间上限
- **degradation**：逼近上限时自动降级（减少检索深度、跳过 rerank）
- **HITL fallback**：超出上限时转入人工审批流程

## 面试回答要点

被问"你的 Agent 是什么架构"，不要只说 ReAct。关键区分：
- ReAct 是循环结构，Loop Engineering 是系统结构
- 核心差异是外部验证器——不信任 LLM 自评
- Guardrails 不是报错退出，而是多层降级
