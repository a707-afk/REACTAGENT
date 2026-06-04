"""构建 / 重建向量索引。请在 rag-kb-project 根目录执行：

    python scripts/reindex.py

或使用 conda 解释器全路径；脚本会将工作目录切到项目根。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def main() -> None:
    from app.cache import cache_clear
    from app.vector_index import rebuild_index

    n = rebuild_index()
    cache_clear()
    print(f"索引完成，共 {n} 个节点（检索缓存已清空）。")


if __name__ == "__main__":
    main()
