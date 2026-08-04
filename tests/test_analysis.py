import json
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


class ConfigurationTests(unittest.TestCase):
    def test_default_configuration_has_required_sections(self):
        config = json.loads((PROJECT_ROOT / "config" / "app.json").read_text(encoding="utf-8"))
        self.assertIn("paths", config)
        self.assertIn("network", config)
        self.assertGreater(config["network"]["port"], 0)
        for key in ("tutor_recordings", "customer_recordings", "logs", "recorder", "video_player", "analyzer"):
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


class AnalysisIntegrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
