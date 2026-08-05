import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "test_exe"
sys.path.insert(0, str(ANALYSIS_DIR))

import DTW  # noqa: E402
import main as analysis  # noqa: E402
import motion_data  # noqa: E402


class ConfigurationTests(unittest.TestCase):
    def test_default_configuration_has_required_sections(self):
        config = json.loads((PROJECT_ROOT / "config" / "app.json").read_text(encoding="utf-8"))
        self.assertIn("paths", config)
        self.assertIn("network", config)
        self.assertGreater(config["network"]["port"], 0)
        for key in ("tutor_recordings", "customer_recordings", "logs", "recorder", "video_player", "analyzer", "exercise_profile", "subject_tracking"):
            self.assertTrue(config["paths"][key])


class AnalysisUnitTests(unittest.TestCase):
    def test_zero_length_vector_angle_is_safe(self):
        self.assertEqual(analysis.GetAngle([0, 0, 0], [1, 0, 0]), 0.0)

    def test_score_is_bounded_and_monotonic(self):
        self.assertEqual(analysis.getScore([]), 0.0)
        self.assertGreater(analysis.getScore([25.0, 25.0]), analysis.getScore([14400.0, 14400.0]))
        self.assertGreaterEqual(analysis.getScore([25.0]), 0.0)
        self.assertLessEqual(analysis.getScore([25.0]), 100.0)

    def test_gaussian_filter_preserves_shape_without_requiring_opencv(self):
        values = np.arange(54, dtype=np.float32).reshape(2, 3, 9)
        filtered = analysis.GaussianFilter(values, sigma=1)
        self.assertEqual(filtered.shape, values.shape)
        self.assertTrue(np.isfinite(filtered).all())

    def test_dtw_path_connects_both_sequences(self):
        first = np.array([[0.0], [1.0], [2.0]], dtype=np.float64)
        second = np.array([[0.0], [0.5], [1.0], [2.0]], dtype=np.float64)
        path = DTW.getPath(first, second, window=3)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (2, 3))

    def test_element_distances_collapse_all_feature_dimensions(self):
        first = np.zeros((2, 3, 9), dtype=np.float32)
        second = np.ones((2, 3, 9), dtype=np.float32)
        distances = DTW.get_elementwise_distances(first, second, [(0, 0), (1, 1)])
        self.assertEqual(distances, [27.0, 27.0])

    def test_public_sample_can_be_parsed(self):
        sample = PROJECT_ROOT / "data" / "samples" / "tutor_session" / "output2.txt"
        bodies = analysis.getBodiesFromFile(str(sample))
        self.assertEqual(len(bodies), 4)
        self.assertEqual(len(bodies[0]["joints"]), 32)


class MotionDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = PROJECT_ROOT / ".test-motion-data" / self._testMethodName
        self.temporary.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temporary, ignore_errors=True)

    def test_versioned_public_sample_is_preferred_and_valid(self):
        folder = PROJECT_ROOT / "data" / "samples" / "tutor_session"
        frames = motion_data.load_session_frames(folder)
        bodies = motion_data.load_session_bodies(folder)
        self.assertEqual(len(frames), 4)
        self.assertEqual(len(bodies), 4)
        self.assertEqual(frames[0]["frame_index"], 0)
        self.assertEqual(len(bodies[0]["joints"]), 32)

    def test_session_loader_falls_back_to_legacy_text(self):
        source = PROJECT_ROOT / "data" / "samples" / "tutor_session" / "output2.txt"
        shutil.copyfile(source, self.temporary / "output2.txt")
        frames = motion_data.load_session_frames(self.temporary)
        self.assertEqual(len(frames), 4)
        self.assertEqual(frames[0]["bodies"][0]["body_id"], 1)

    def test_legacy_parser_preserves_orientation_confidence_and_frame_boundary(self):
        contents = """Frame Index: 7; Timestamp (usec): 12345
Body ID: 42
Joint[0]: Position[mm] ( 1, 2, 3 ); Orientation ( 1, 0, 0, 0); Confidence Level (2)
Body ID: 99
Joint[0]: Position[mm] ( 4, 5, 6 ); Orientation ( 0.5, 0.5, 0.5, 0.5); Confidence Level (1)
"""
        path = self.temporary / "output2.txt"
        path.write_text(contents, encoding="utf-8")
        frames = motion_data.load_legacy_frames(path)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["frame_index"], 7)
        self.assertEqual(frames[0]["timestamp_usec"], 12345)
        self.assertEqual(len(frames[0]["bodies"]), 2)
        joint = frames[0]["bodies"][0]["joints"][0]
        self.assertEqual(joint["orientation_wxyz"], [1.0, 0.0, 0.0, 0.0])
        self.assertEqual(joint["confidence_level"], 2)

    def test_round_trip_and_stable_primary_body_selection(self):
        joint = {
            "joint_index": 0,
            "position_mm": [1.0, 2.0, 1800.0],
            "orientation_wxyz": [1.0, 0.0, 0.0, 0.0],
            "confidence_level": 2,
        }
        frames = [
            {
                "frame_index": 0,
                "timestamp_usec": 100,
                "image": "image_idx_0.jpg",
                "bodies": [
                    {"body_id": 10, "joints": [joint]},
                    {"body_id": 20, "joints": [joint]},
                ],
            },
            {
                "frame_index": 1,
                "timestamp_usec": 200,
                "image": "image_idx_1.jpg",
                "bodies": [{"body_id": 20, "joints": [joint]}],
            },
        ]
        motion_data.write_session(self.temporary, frames)
        loaded = motion_data.load_session_frames(self.temporary)
        selected = motion_data.load_session_bodies(self.temporary)
        self.assertEqual(len(loaded), 2)
        self.assertEqual([body["body_id"] for body in selected], [20, 20])
        self.assertEqual(selected[1]["timestamp_usec"], 200)

    def test_unsupported_schema_version_is_rejected(self):
        manifest = motion_data.create_manifest()
        manifest["schema_version"] = 999
        (self.temporary / "session.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(motion_data.MotionDataError):
            motion_data.load_manifest(self.temporary)


class AnalysisIntegrationTests(unittest.TestCase):
    def test_public_samples_pass_subject_tracking_gates(self):
        command = [
            sys.executable,
            str(ANALYSIS_DIR / "main.py"),
            "--folder_tutor",
            str(PROJECT_ROOT / "data" / "samples" / "tutor_session"),
            "--folder_customer",
            str(PROJECT_ROOT / "data" / "samples" / "customer_session"),
            "--function",
            "tracking",
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        report = json.loads(completed.stdout)
        self.assertTrue(report["tutor"]["gate_passed"])
        self.assertTrue(report["customer"]["gate_passed"])
        self.assertEqual(report["tutor"]["selected_body_id"], 1)
        self.assertEqual(report["customer"]["selected_body_id"], 7)

    def test_public_samples_produce_a_numeric_score(self):
        command = [
            sys.executable,
            str(ANALYSIS_DIR / "main.py"),
            "--folder_tutor",
            str(PROJECT_ROOT / "data" / "samples" / "tutor_session"),
            "--folder_customer",
            str(PROJECT_ROOT / "data" / "samples" / "customer_session"),
            "--function",
            "score",
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        score = float(completed.stdout.strip().splitlines()[-1])
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_public_samples_produce_a_quality_report(self):
        command = [
            sys.executable,
            str(ANALYSIS_DIR / "main.py"),
            "--folder_tutor",
            str(PROJECT_ROOT / "data" / "samples" / "tutor_session"),
            "--folder_customer",
            str(PROJECT_ROOT / "data" / "samples" / "customer_session"),
            "--function",
            "quality",
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        report = json.loads(completed.stdout)
        self.assertEqual(report["tutor"]["usable_frame_count"], 4)
        self.assertEqual(report["customer"]["usable_frame_count"], 4)
        self.assertEqual(report["tutor"]["required_joint_coverage"], 1.0)

    def test_public_samples_produce_an_explainable_assessment_report(self):
        output_folder = PROJECT_ROOT / ".test-motion-data" / "assessment-integration"
        output_folder.mkdir(parents=True, exist_ok=True)
        output_path = output_folder / "assessment.json"
        command = [
            sys.executable,
            str(ANALYSIS_DIR / "main.py"),
            "--folder_tutor",
            str(PROJECT_ROOT / "data" / "samples" / "tutor_session"),
            "--folder_customer",
            str(PROJECT_ROOT / "data" / "samples" / "customer_session"),
            "--profile",
            "arm_raise",
            "--function",
            "report",
            "--report-output",
            str(output_path),
        ]
        try:
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
            report = json.loads(completed.stdout)
            saved_report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["format"], "trainercam.assessment-report")
            self.assertEqual(report["profile"]["id"], "arm_raise")
            self.assertEqual(len(report["feature_scores"]), 9)
            self.assertTrue(report["quality"]["tutor"]["subject_tracking"]["gate_passed"])
            self.assertTrue(report["quality"]["customer"]["subject_tracking"]["gate_passed"])
            self.assertEqual(saved_report["overall_score"], report["overall_score"])
            self.assertGreaterEqual(report["overall_score"], 0.0)
            self.assertLessEqual(report["overall_score"], 100.0)
        finally:
            shutil.rmtree(output_folder, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
