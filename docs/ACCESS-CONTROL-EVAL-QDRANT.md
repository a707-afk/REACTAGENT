# 权限评测（检索前 Pre-filter）

生成时间 UTC：2026-06-03T09:13:35.539475+00:00

## 摘要

- 向量后端：**qdrant**（`qdrant_path=data/qdrant_local`）
- 样例条数：**30**
- Forbidden top5：**4/4**（通过率 1.0）
- Expect top1 子串：**22/26**
- Domain top1：**22/24**

明细：`docs\eval_access_control_qdrant.json`

forbidden_*：低 clearance 用户在易触发受限文档的问法下，top5 路径不应命中给定子串；受检索排序噪声影响，请以人工 spot-check bad case。

## 路线图

权限逻辑：`app/access_prefilter.py`（向量 Chroma ids + BM25 子集预筛）；规则见 `app/access_control.py`。
