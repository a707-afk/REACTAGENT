"""router_calibration：输出范围与默认 bundle 可读性."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestRouterCalibration(unittest.TestCase):
    def tearDown(self) -> None:
        from app.router_calibration import load_calibration_bundle
        from app.config import get_settings

        load_calibration_bundle.cache_clear()
        get_settings.cache_clear()

    def test_calibrate_probability_in_unit_interval(self):
        from app.router_calibration import calibrate_probability

        for raw in (0.0, 0.37, 0.75, 1.0):
            cal, rr = calibrate_probability(raw, branch="merged")
            self.assertEqual(rr, raw)
            self.assertGreaterEqual(cal, 0.0)
            self.assertLessEqual(cal, 1.0)


def _load_fit_module():
    import importlib.util

    path = ROOT / "scripts" / "fit_router_calibration.py"
    spec = importlib.util.spec_from_file_location("_fit_router_cal", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFitHelpers(unittest.TestCase):
    def test_fit_logistic_runs_on_tiny_set(self):
        mod = _load_fit_module()
        fit_logistic_platt = mod.fit_logistic_platt

        fs = [_log(i) for i in range(2, 6)]
        ys = [1, 0, 1, 0]
        a, b = fit_logistic_platt(fs, ys)
        self.assertTrue(any(abs(x) < 99 for x in (a, b)))



def _log(x):
    import math

    return math.log(x)


if __name__ == "__main__":
    unittest.main()
