"""LLM 客户端单元测试：验证无 API key 时正确报错。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestLLMNoKey(unittest.TestCase):
    """无 SENSENOVA_API_KEYS 时调用应报 RuntimeError。"""

    def test_chat_completion_no_key(self):
        """无 API Key 时应报错。"""
        # 直接用空 key 的 Settings 构造，避免 patch.dict 环境变量长度问题
        from app.config import Settings
        from app.llm import chat_completion, _SENSENOVA_KEYS, _key_idx

        # 强制清空内部 key 缓存
        import app.llm as llm_mod
        llm_mod._SENSENOVA_KEYS = []
        llm_mod._key_idx = 0

        # 临时替换 _load_keys 让它返回空列表
        original_load = llm_mod._load_keys
        llm_mod._load_keys = lambda: []

        try:
            with self.assertRaises(RuntimeError) as ctx:
                chat_completion("sys", "user")
            self.assertIn("SENSENOVA_API_KEYS", str(ctx.exception))
        finally:
            llm_mod._load_keys = original_load
            llm_mod._SENSENOVA_KEYS = []
            llm_mod._key_idx = 0


if __name__ == "__main__":
    unittest.main()
