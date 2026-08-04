import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "test_exe"
sys.path.insert(0, str(ANALYSIS_DIR))

import motion_preprocessing as preprocessing  # noqa: E402


def make_body(frame_index, transform=None, low_confidence=None):
    positions = np.zeros((32, 3), dtype=np.float64)
    values = {
        0: [0, 500, 2000],
        2: [0, 100, 2000],
        5: [-200, 100, 2000],
        6: [-350, 150, 2000],
        7: [-500, 200, 2000],
        12: [200, 100, 2000],
        13: [350, 150, 2000],
        14: [500, 200, 2000],
        18: [-100, 500, 2000],
        19: [-110, 900, 2010],
        20: [-120, 1250, 2030],
        22: [100, 500, 2000],
        23: [110, 900, 2010],
        24: [120, 1250, 2030],
    }
    for index, value in values.items():
        positions[index] = value
    if transform is not None:
        scale, rotation, translation = transform
        populated = np.linalg.norm(positions, axis=1) > 0
        positions[populated] = (positions[populated] @ rotation.T) * scale + translation
    low_confidence = set(low_confidence or [])
    return {
        "body_id": 7,
        "frame_index": frame_index,
        "timestamp_usec": frame_index * 33333,
        "image": f"image_idx_{frame_index}.jpg",
        "joints": [
            {
                "joint_index": index,
                "position_mm": positions[index].tolist(),
                "confidence_level": 0 if index in low_confidence else 2,
            }
            for index in range(32)
        ],
    }


class MotionPreprocessingTests(unittest.TestCase):
    def test_normalisation_removes_translation_scale_and_sensor_rotation(self):
        angle = np.deg2rad(32.0)
        rotation = np.array(
            [
                [np.cos(angle), 0.0, np.sin(angle)],
                [0.0, 1.0, 0.0],
                [-np.sin(angle), 0.0, np.cos(angle)],
            ]
        )
        original = preprocessing.prepare_motion([make_body(0)])
        transformed = preprocessing.prepare_motion(
            [make_body(0, transform=(1.7, rotation, np.array([450.0, -80.0, 300.0])))]
        )
        required = [5, 6, 7, 12, 13, 14, 18, 19, 20, 22, 23, 24]
        np.testing.assert_allclose(
            original.positions[:, required], transformed.positions[:, required], atol=1e-6
        )

    def test_short_low_confidence_gap_is_interpolated(self):
        bodies = [make_body(index) for index in range(3)]
        bodies[0]["joints"][6]["position_mm"] = [0.0, 0.0, 100.0]
        bodies[1]["joints"][6]["position_mm"] = [50.0, 50.0, 50.0]
        bodies[1]["joints"][6]["confidence_level"] = 0
        bodies[2]["joints"][6]["position_mm"] = [20.0, 40.0, 200.0]
        prepared = preprocessing.prepare_motion(
            bodies, max_interpolation_gap=1, normalise=False
        )
        np.testing.assert_allclose(prepared.positions[1, 6], [10.0, 20.0, 150.0])
        self.assertTrue(prepared.valid[1, 6])
        self.assertTrue(prepared.interpolated[1, 6])

    def test_long_gap_remains_invalid(self):
        bodies = [make_body(index) for index in range(4)]
        for frame in (1, 2):
            bodies[frame]["joints"][6]["confidence_level"] = 0
        prepared = preprocessing.prepare_motion(
            bodies, max_interpolation_gap=1, normalise=False
        )
        self.assertFalse(prepared.valid[1, 6])
        self.assertFalse(prepared.valid[2, 6])
        np.testing.assert_allclose(prepared.positions[1, 6], [0.0, 0.0, 0.0])

    def test_legacy_track_without_confidence_uses_nonzero_positions(self):
        body = make_body(0)
        for joint in body["joints"]:
            joint["confidence_level"] = 0
        prepared = preprocessing.prepare_motion([body])
        self.assertFalse(prepared.confidence_metadata_available)
        self.assertTrue(prepared.valid[0, 5])
        self.assertFalse(prepared.valid[0, 1])

    def test_unusable_frames_are_removed_without_losing_original_index(self):
        bodies = [make_body(index) for index in range(3)]
        for joint in (5, 6, 7, 12, 13, 14):
            bodies[1]["joints"][joint]["confidence_level"] = 0
        prepared = preprocessing.prepare_motion(
            bodies, max_interpolation_gap=0, normalise=False
        )
        retained = preprocessing.retain_usable_frames(
            prepared, [5, 6, 7, 12, 13, 14]
        )
        self.assertEqual(retained.frame_indices.tolist(), [0, 2])
        self.assertEqual(retained.timestamps_usec.tolist(), [0.0, 66666.0])


if __name__ == "__main__":
    unittest.main()
