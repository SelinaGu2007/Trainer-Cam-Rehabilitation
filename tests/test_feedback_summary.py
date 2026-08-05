import copy
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "test_exe"
sys.path.insert(0, str(ANALYSIS_DIR))

import feedback_summary  # noqa: E402


def assessment(score=82.0, improvements=None):
    return {
        "format": "trainercam.assessment-report",
        "schema_version": 1,
        "overall_score": score,
        "improvements": improvements or [],
        "quality": {
            "tutor": {"required_joint_coverage": 1.0},
            "customer": {
                "required_joint_coverage": 1.0,
                "subject_tracking": {"gate_passed": True, "warnings": []},
            },
        },
    }


class FeedbackSummaryTests(unittest.TestCase):
    def test_score_maps_to_non_clinical_rating(self):
        self.assertEqual(
            feedback_summary.create_feedback_summary(assessment(94))["rating"]["id"],
            "excellent",
        )
        self.assertEqual(
            feedback_summary.create_feedback_summary(assessment(52))["rating"]["id"],
            "review",
        )

    def test_improvements_are_limited_and_spoken(self):
        values = [
            {"feature_id": f"feature_{index}", "label": f"Part {index}", "message": "Review it."}
            for index in range(5)
        ]
        summary = feedback_summary.create_feedback_summary(assessment(70, values))
        self.assertEqual(len(summary["improvements"]), 3)
        self.assertIn("Part 0", summary["spoken_text"])

    def test_no_improvements_produces_positive_plain_language(self):
        summary = feedback_summary.create_feedback_summary(assessment(100))
        self.assertIn("No persistent movement issue", summary["spoken_text"])

    def test_tracking_warning_adds_quality_caution(self):
        report = assessment()
        report["quality"]["customer"]["subject_tracking"]["warnings"] = ["multiple bodies"]
        summary = feedback_summary.create_feedback_summary(report)
        self.assertIsNotNone(summary["quality_notice"])
        self.assertIn(summary["quality_notice"], summary["spoken_text"])

    def test_chinese_locale_is_supported(self):
        summary = feedback_summary.create_feedback_summary(assessment(88), "zh-CN")
        self.assertEqual(summary["locale"], "zh-CN")
        self.assertIn("得分", summary["spoken_text"])

    def test_invalid_assessment_is_rejected(self):
        report = copy.deepcopy(assessment())
        report["format"] = "unknown"
        with self.assertRaises(feedback_summary.FeedbackSummaryError):
            feedback_summary.create_feedback_summary(report)


if __name__ == "__main__":
    unittest.main()
