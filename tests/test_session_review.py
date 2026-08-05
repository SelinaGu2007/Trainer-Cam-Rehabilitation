import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "test_exe"
sys.path.insert(0, str(ANALYSIS_DIR))

from exercise_profile import load_profile  # noqa: E402
from session_review import create_session_review  # noqa: E402


class SessionReviewTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile("arm_raise")
        count = 4
        feature_count = len(self.profile.features)
        self.tutor = np.zeros((count, 3, feature_count), dtype=np.float64)
        self.customer = self.tutor.copy()
        self.customer[2, :, 0] = 45.0
        self.path = [(index, index) for index in range(count)]
        self.customer_motion = SimpleNamespace(
            frame_indices=np.arange(count) + 10,
            timestamps_usec=np.arange(count, dtype=float) * 33333.0,
            images=["image_idx_10.jpg", None, "../../private.jpg", "image_idx_13.jpg"],
        )
        self.tutor_motion = SimpleNamespace(
            frame_indices=np.arange(count) + 20,
            timestamps_usec=np.full(count, np.nan),
            images=[f"image_idx_{index + 20}.jpg" for index in range(count)],
        )
        self.report = {
            "format": "trainercam.assessment-report",
            "worst_segment": {
                "path_start": 1,
                "path_end": 3,
                "mean_error_deg": 25.0,
                "customer_sequence_index": 2,
                "tutor_sequence_index": 2,
            },
        }

    def test_review_identifies_worst_aligned_frame_and_feature(self):
        review = create_session_review(
            self.customer,
            self.tutor,
            self.path,
            self.profile,
            self.customer_motion,
            self.tutor_motion,
            self.report,
        )
        self.assertEqual(review["format"], "trainercam.session-review")
        self.assertEqual(review["item_count"], 4)
        self.assertEqual(review["worst_segment"]["focus_index"], 2)
        self.assertEqual(review["items"][2]["issue"]["feature_id"], "left_upper_arm")
        self.assertEqual(review["items"][2]["issue"]["severity"], "review")
        self.assertTrue(review["items"][2]["in_worst_segment"])

    def test_review_keeps_only_safe_relative_image_names(self):
        review = create_session_review(
            self.customer,
            self.tutor,
            self.path,
            self.profile,
            self.customer_motion,
            self.tutor_motion,
            self.report,
        )
        self.assertEqual(review["items"][2]["customer"]["image"], "private.jpg")
        self.assertIsNone(review["items"][0]["tutor"]["timestamp_usec"])

    def test_empty_alignment_is_rejected(self):
        with self.assertRaises(ValueError):
            create_session_review(
                self.customer,
                self.tutor,
                [],
                self.profile,
                self.customer_motion,
                self.tutor_motion,
                self.report,
            )


if __name__ == "__main__":
    unittest.main()
