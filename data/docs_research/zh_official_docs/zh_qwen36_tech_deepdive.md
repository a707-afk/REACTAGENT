<!-- source: AI辅助整理 | category: llm/qwen | language: zh-CN -->

# Qwen3.6-35B-A3B 技术深度解读

## MoE 架构核心

35B 总参数，但每次推理只激活 3B——这就是 A3B 的含义。模型有多个"专家"子网络（Experts），每个 token 通过路由器（Router）选择最相关的 1-2 个专家激活，其余专家休眠。这种设计使得推理速度接近 3B 密集模型，但能力对标 35B 水平。

## 关键 Benchmark

SWE-bench Verified：73.4%（前代 Qwen3.5-35B-A3B 是 52.0%）。Aider Polyglot：78.7% 成功率（进入公开榜单 Top 10），LiveCodeBench：80.40。GPQA：86。

**对比参考**：Qwen3.6-35B-A3B 的 SWE-bench 分数接近 Claude Sonnet 4.5 水平，但参数量小得多。

## 关键技术特性

**Agentic Coding**：专为仓库级代码理解和前端工作流优化。支持多文件编辑、跨文件引用追踪。

**Thinking Preservation**：新选项保留历史消息中的推理过程，让多轮 Agent 任务更连贯。

**多模态能力**：原生支持图像理解、文档处理。

## 在 3060 上的部署

Q4_K_M GGUF 量化：文件 ~20GB，GPU offload ~20 层（~7-8GB）+ CPU 处理 MoE 专家层。iQ4_XS（更激进量化）在 12GB 上可达 30-110 tok/s。
