# CUDA / GPU 推理配置（RTX 50 系）

> 项目通过 **`INFERENCE_DEVICE=auto|cuda|cpu`** 选择 Embedding 与 Qwen Reranker 的设备；**不写死 CUDA**，无 GPU 或仅 CPU 版 PyTorch 时自动用 CPU。

---

## 本机检测（示例）

- GPU：NVIDIA GeForce **RTX 5070**
- 驱动：595.x，nvidia-smi 显示 CUDA 13.2（驱动支持版本，与 PyTorch 内置 CUDA 12.8 可并存）

---

## 问题现象

`rags` 若安装了 **`torch *+cpu`**，`torch.cuda.is_available()` 恒为 `False`，评测/API 会落在 CPU（Embedding/Rerank 极慢）。

RTX **5070 / 5080 / 5090**（Blackwell，**sm_120**）需要 PyTorch **cu128**（CUDA 12.8）构建，**cu124 及更早 wheel 不可用**。

---

## 一次性安装（Conda `rags`）

在 `rag-kb-project` 根目录 PowerShell：

```powershell
.\scripts\setup_pytorch_cuda.ps1
# 若 stable cu128 仍报 no kernel image，改用 nightly：
.\scripts\setup_pytorch_cuda.ps1 -UseNightly
```

脚本会：

1. 卸载 `torch` / `torchvision` / `torchaudio`
2. 从 `https://download.pytorch.org/whl/cu128`（或 nightly/cu128）重装
3. 在 GPU 上创建张量做冒烟验证

解释器路径默认 `D:\conda\envs\rags\python.exe`，可用 `-Python` 覆盖。

---

## 运行时的设备策略

| 环境变量 | 行为 |
|----------|------|
| `INFERENCE_DEVICE=auto`（默认） | 有 CUDA 用 GPU，否则 CPU |
| `INFERENCE_DEVICE=cuda` | 强制 GPU；不可用则 **回退 CPU** 并打 warning |
| `INFERENCE_DEVICE=cpu` | 强制 CPU |

代码：`app/inference_device.py`（Embedding：`app/embeddings.py`；Rerank：`app/qwen_rerank.py`）。

---

## 验证

```powershell
& "D:\conda\envs\rags\python.exe" -c "from app.config import get_settings; from app.inference_device import resolve_inference_device, cuda_device_info; s=get_settings(); print(resolve_inference_device(s)); print(cuda_device_info())"
```

启动 API 后访问 **`GET /health/config`**，应看到：

- `inference_device_resolved`: `cuda`
- `cuda_device_name`: `NVIDIA GeForce RTX 5070`
- `torch_cuda_built`: `true`

---

## 注意

- 不要在同一 `rags` 里混装 `torch-directml` 等与 cu128 torch 冲突的包。
- sentence-transformers / transformers 仍随 `requirements.txt` 安装；**仅 PyTorch 需 cu128**。
- 评测脚本无需改代码，设 `INFERENCE_DEVICE=auto` 即可自动走 GPU。
