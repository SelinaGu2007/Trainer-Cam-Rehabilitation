import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import run_robustness_evaluation  # noqa: E402


class RobustnessEvaluationTests(unittest.TestCase):
    def test_all_synthetic_robustness_scenarios_pass(self):
        report = run_robustness_evaluation.run_evaluation()
        self.assertEqual(report["format"], "trainercam.robustness-report")
        self.assertTrue(report["summary"]["passed"])
        self.assertEqual(report["summary"]["scenario_count"], 10)
        self.assertEqual(report["metrics"]["user_switch_error_count"], 0)
        self.assertEqual(report["metrics"]["tracking_recovery_rate"], 1.0)
        self.assertTrue(report["limitations"]["synthetic_data_only"])


if __name__ == "__main__":
    unittest.main()
