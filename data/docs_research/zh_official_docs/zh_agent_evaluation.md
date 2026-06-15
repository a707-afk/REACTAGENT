<!-- source: AI辅助整理 | category: agent/evaluation | language: zh-CN -->

# Agent 评测体系：Faithfulness + Coverage 双指标设计

## 为什么传统检索指标不够

Recall@5、MRR、nDCG 衡量的是检索层质量，但 Deep Research Agent 的产出是综合报告。报告质量 ≠ 单次检索质量。你需要评测的是 Agent 的最终输出，不是中间步骤。

## 核心指标

### Faithfulness（忠实度）
**定义**：报告中每个事实陈述是否被检索到的源文档支撑。
**计算**：句级 grounding（sentence_level_grounding）→ 每句打分 → unsupported_rate = 未被支撑的句子占比。faithfulness = 1 - unsupported_rate。
**目标**：≥ 0.85。

### Fact Coverage（事实覆盖度）
**定义**：报告是否覆盖了问题的所有关键方面。
**计算**：预设 gold_facts（如"Qdrant HNSW 延迟 5ms""Milvus 支持 GPU 索引"）→ 检查报告是否提及每个 fact。LLM-as-judge 或关键词匹配。
**目标**：≥ 0.80。

### Avg Steps（收敛效率）
**定义**：Agent 平均需要多少步 ReAct 循环才能达到验证通过。
**计算**：统计所有评测 case 的 avg_steps。正常值 2-4 步。
**目标**：≤ 3 步。

## 评测集构建

不要用检索文档反向生成问题（过拟合）。构建方法：
1. 领域专家写 10 个基准问题
2. LLM 基于问题生成 40 个变体（口语化、多跳、限定条件）
3. 人工筛选 30 个高质量 case
4. 每个 case 标注 gold_facts（3-5 个应出现的关键事实）

## 面试回答要点
"我的评测体系是两维：faithfulness（每句话是否被源支撑）+ fact_coverage（是否覆盖所有关键事实）。不是 dry-run 造的假数据，是真实检索 + 句级 grounding 算出来的。"
