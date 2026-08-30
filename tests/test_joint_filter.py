import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "test_exe"))

from joint_filter import JointFilterBank, JointFilterConfig  # noqa: E402


def body(position, confidence=3):
    joints = []
    for index in range(32):
        value = [float(position[0] + index), float(position[1]), float(position[2])]
        if index == 5:
            value = [-200.0, 100.0, 1800.0]
        elif index == 12:
            value = [200.0, 100.0, 1800.0]
        joints.append(
            {"joint_index": index, "position_mm": value, "confidence_level": confidence}
        )
    return {"body_id": 7, "joints": joints}


class JointFilterTests(unittest.TestCase):
    def test_short_missing_joint_is_held_then_becomes_unavailable(self):
        bank = JointFilterBank(JointFilterConfig(maximum_hold_frames=2))
        bank.update(body([0, 0, 1800]), 0)
        missing = body([0, 0, 1800])
        missing["joints"][7]["confidence_level"] = 0
        first, quality = bank.update(missing, 33333)
        self.assertIn(7, quality["predicted_joint_indices"])
        second, quality = bank.update(missing, 66666)
        self.assertIn(7, quality["predicted_joint_indices"])
        third, quality = bank.update(missing, 99999)
        self.assertNotIn(7, quality["valid_joint_indices"])
        self.assertFalse(third["joints"][7]["filter_valid"])

    def test_large_jump_is_rejected(self):
        config = JointFilterConfig(maximum_joint_speed_body_scales_per_second=2.0)
        bank = JointFilterBank(config)
        bank.update(body([0, 0, 1800]), 0)
        jumped = body([2000, 0, 1800])
        _, quality = bank.update(jumped, 33333)
        self.assertIn(7, quality["rejected_joint_indices"])

    def test_filter_reduces_jitter_variance(self):
        bank = JointFilterBank(
            JointFilterConfig(
                ema_alpha_high_confidence=0.35,
                ema_alpha_low_confidence=0.15,
                maximum_joint_speed_body_scales_per_second=100.0,
            )
        )
        raw, filtered = [], []
        for index in range(60):
            x = 20.0 if index % 2 else -20.0
            sample = body([x, 0, 1800])
            result, _ = bank.update(sample, index * 33333)
            raw.append(sample["joints"][7]["position_mm"][0])
            filtered.append(result["joints"][7]["position_mm"][0])
        self.assertLess(np.var(filtered[10:]), np.var(raw[10:]) * 0.25)


if __name__ == "__main__":
    unittest.main()
