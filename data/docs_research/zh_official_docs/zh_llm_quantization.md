<!-- source: AI辅助整理 | category: llm/deployment | language: zh-CN -->

# LLM 本地部署全流程：量化方案对比（GGUF/AWQ/GPTQ）

## 为什么要量化

Qwen3.6-35B-A3B 原始 FP16 需要 ~70GB 显存。Q4 量化后 ~20GB，单卡 3060 12GB + CPU offload 可跑。

## 三种量化方案

### GGUF/GGML（llama.cpp 生态）
- **格式**：文件级量化，直接加载
- **精度**：Q4_K_M（最佳性价比）、Q5_K_M（精度优先）、Q8_0（接近无损）
- **适用**：消费级 GPU、CPU 混合推理
- **工具**：llama.cpp、Ollama
- **速度**：Q4_K_M 在 RTX 3060 12GB 约 30-110 tok/s（视 offload 比例）

### AWQ（Activation-aware Weight Quantization）
- **格式**：权重量化 + 激活值校准
- **精度**：4-bit，对重要权重保留更高精度
- **适用**：纯 GPU 推理
- **工具**：vLLM、TGI
- **速度**：比 GGUF 快约 20%（纯 GPU）

### GPTQ（Post-Training Quantization）
- **格式**：逐层量化 + 校准数据集
- **精度**：4-bit / 8-bit
- **适用**：纯 GPU 推理
- **工具**：AutoGPTQ、ExLlama

## 3060 12GB 部署方案

**单卡方案**（12GB）：
- BGE-M3：~2GB（常驻 GPU）
- bge-reranker-v2-m3：~1GB（常驻 GPU）
- Qwen3.6-35B-A3B GGUF iQ4_XS：~17GB 文件大小，GPU offload 约 20 层（~8GB），剩余 MoE 专家层在 CPU
- 速度：30-50 tok/s（取决于上下文长度）

**双卡方案**（24GB）：Q4_K_M 全 GPU，100-240 tok/s。**推荐生产用**。

## 面试回答要点
"我选 GGUF Q4_K_M——不是因为它简单，而是因为我的场景需要 CPU-GPU 混合推理（MoE 模型的专家层不需要全在 GPU）。AWQ 只适合纯 GPU 部署。"
