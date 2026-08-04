import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "test_exe"
sys.path.insert(0, str(ANALYSIS_DIR))

import assessment  # noqa: E402
import exercise_profile  # noqa: E402


class ExerciseProfileTests(unittest.TestCase):
    def test_default_arm_raise_profile_is_valid(self):
        profile = exercise_profile.load_profile("arm_raise")
        self.assertEqual(profile.profile_id, "arm_raise")
        self.assertEqual(len(profile.features), 9)
        self.assertIn(7, profile.required_joints)
        self.assertGreater(profile.features[0].weight, profile.features[4].weight)

    def test_duplicate_feature_id_is_rejected(self):
        profile_path = PROJECT_ROOT / "config" / "exercises" / "arm_raise.json"
        import json

        raw = json.loads(profile_path.read_text(encoding="utf-8"))
        raw["features"][1]["id"] = raw["features"][0]["id"]
        with self.assertRaises(exercise_profile.ExerciseProfileError):
            exercise_profile.parse_profile(raw)

    def test_error_score_is_bounded_and_monotonic(self):
        self.assertEqual(assessment.score_errors([], 8, 35), 0.0)
        self.assertEqual(assessment.score_errors([0, 0], 8, 35), 100.0)
        self.assertGreater(
            assessment.score_errors([10, 10], 8, 35),
            assessment.score_errors([30, 30], 8, 35),
        )


class AssessmentReportTests(unittest.TestCase):
    def setUp(self):
        self.profile = exercise_profile.load_profile("arm_raise")
        frame_count = 4
        self.tutor_angles = np.zeros((frame_count, 3, len(self.profile.features)))
        self.customer_angles = self.tutor_angles.copy()
        self.path = [(index, index) for index in range(frame_count)]
        self.motion = SimpleNamespace(
            frame_indices=np.arange(frame_count),
            timestamps_usec=np.arange(frame_count, dtype=float) * 33333.0,
        )
        self.quality = {"required_joint_coverage": 1.0, "usable_frame_count": frame_count}

    def create_report(self):
        return assessment.create_assessment_report(
            self.customer_angles,
            self.tutor_angles,
            self.path,
            self.profile,
            self.motion,
            self.motion,
            copy.deepcopy(self.quality),
            copy.deepcopy(self.quality),
        )

    def test_identical_motion_receives_full_explainable_score(self):
        report = self.create_report()
        self.assertEqual(report["overall_score"], 100.0)
        self.assertTrue(all(item["score"] == 100.0 for item in report["feature_scores"]))
        self.assertEqual(report["improvements"], [])
        self.assertEqual(report["alignment"]["path_length"], 4)

    def test_localised_error_lowers_the_matching_feature(self):
        self.customer_angles[:, :, 0] = 30.0
        report = self.create_report()
        left_arm = report["feature_scores"][0]
        self.assertLess(left_arm["score"], 50.0)
        self.assertLess(report["overall_score"], 100.0)
        self.assertEqual(report["improvements"][0]["feature_id"], "left_upper_arm")

    def test_profile_weight_is_applied_to_dtw_sequence(self):
        angles = np.ones((2, 3, len(self.profile.features)), dtype=np.float64)
        sequence = assessment.weighted_sequence(angles, self.profile)
        expected_width = sum(len(feature.axes) for feature in self.profile.features)
        self.assertEqual(sequence.shape, (2, expected_width))
        first_scale = np.sqrt(self.profile.features[0].weight / 3.0)
        self.assertAlmostEqual(sequence[0, 0], first_scale)


if __name__ == "__main__":
    unittest.main()
