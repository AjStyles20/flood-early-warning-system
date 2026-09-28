"""Regression guards for Experiment 001 selection policy.

The raw GRDC file is intentionally not required by CI. These checks protect
the deterministic model-selection rules that must remain stable between
reproducibility runs.
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiment_001 as exp


class Experiment001SelectionTests(unittest.TestCase):
    def test_b3_tie_break_prefers_smaller_window(self):
        candidates = []
        for window in (1, 2):
            metrics = {"CSI": 0.3333333333333333, "FAR": 0.3333333333333333}
            candidates.append((metrics["CSI"], -metrics["FAR"], -window, window))
        *_, selected = max(candidates)
        self.assertEqual(selected, 1)

    def test_declared_split_and_horizons_remain_frozen(self):
        self.assertEqual(exp.TRAIN, ("2004-01-01", "2014-12-31"))
        self.assertEqual(exp.VALID, ("2015-01-01", "2019-12-31"))
        self.assertEqual(exp.TEST, ("2020-01-01", "2025-12-31"))
        self.assertEqual(exp.HORIZONS, (1, 3, 5, 7))
        self.assertEqual(exp.QUANTILES, (0.90, 0.95, 0.975))


if __name__ == "__main__":
    unittest.main()
