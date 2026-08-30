import dataclasses
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "test_exe"
sys.path.insert(0, str(ANALYSIS_DIR))

import subject_tracking  # noqa: E402


def make_body(body_id, x=0.0, z=1800.0, confidence=2):
    return {
        "body_id": body_id,
        "joints": [
            {
                "joint_index": index,
                "position_mm": [x + index, float(index), z],
                "orientation_wxyz": [1.0, 0.0, 0.0, 0.0],
                "confidence_level": confidence,
            }
            for index in range(32)
        ],
    }


def make_frame(index, bodies):
    return {
        "frame_index": index,
        "timestamp_usec": index * 33333,
        "image": f"image_idx_{index}.jpg",
        "bodies": bodies,
    }


class SubjectTrackingTests(unittest.TestCase):
    def setUp(self):
        self.config = subject_tracking.load_tracking_config()

    def test_default_tracking_configuration_is_valid(self):
        self.assertEqual(self.config.anchor_joint, 0)
        self.assertLess(self.config.roi_x_mm[0], self.config.roi_x_mm[1])
        self.assertGreater(self.config.min_track_coverage, 0)

    def test_initial_lock_does_not_switch_to_late_bystander(self):
        config = dataclasses.replace(self.config, lock_window_frames=3)
        frames = []
        for index in range(10):
            bodies = []
            if index < 6:
                bodies.append(make_body(10, x=0))
            if index >= 3:
                bodies.append(make_body(20, x=300))
            frames.append(make_frame(index, bodies))
        selected, report = subject_tracking.select_subject_track(frames, config)
        self.assertEqual(report["selected_body_id"], 10)
        self.assertTrue(all(body["body_id"] == 10 for body in selected))
        self.assertFalse(report["gate_passed"])
        self.assertIn("coverage", " ".join(report["gate_failures"]))

    def test_bystander_in_training_region_creates_warning_without_switch(self):
        frames = [
            make_frame(index, [make_body(10), make_body(20, x=500)])
            for index in range(5)
        ]
        selected, report = subject_tracking.select_subject_track(frames, self.config)
        self.assertTrue(report["gate_passed"])
        self.assertEqual(report["selected_body_id"], 10)
        self.assertEqual(len(selected), 5)
        self.assertTrue(report["warnings"])

    def test_long_subject_loss_fails_session_gate(self):
        config = dataclasses.replace(
            self.config,
            min_track_coverage=0.5,
            max_consecutive_missing_frames=2,
        )
        frames = [make_frame(index, [make_body(10)] if index < 3 else []) for index in range(7)]
        _, report = subject_tracking.select_subject_track(frames, config)
        self.assertFalse(report["gate_passed"])
        self.assertEqual(report["max_consecutive_missing_frames"], 4)

    def test_subject_outside_roi_is_rejected(self):
        frames = [make_frame(index, [make_body(10, x=2000)]) for index in range(5)]
        selected, report = subject_tracking.select_subject_track(frames, self.config)
        self.assertEqual(selected, [])
        self.assertFalse(report["gate_passed"])
        self.assertIn("no body was found", report["gate_failures"][0])

    def test_explicit_body_id_is_honoured(self):
        frames = [make_frame(index, [make_body(10), make_body(20, x=300)]) for index in range(5)]
        selected, report = subject_tracking.select_subject_track(
            frames, self.config, body_id=20
        )
        self.assertTrue(report["gate_passed"])
        self.assertEqual({body["body_id"] for body in selected}, {20})
        self.assertEqual(report["selection_reason"], "explicit-body-id")

    def test_new_id_is_reassociated_after_spatial_confirmation(self):
        config = dataclasses.replace(
            self.config,
            lock_window_frames=2,
            temporary_loss_frames=1,
            reassociation_confirmation_frames=2,
        )
        frames = [
            make_frame(0, [make_body(10, x=0)]),
            make_frame(1, [make_body(10, x=10)]),
            make_frame(2, []),
            make_frame(3, [make_body(30, x=20)]),
            make_frame(4, [make_body(30, x=25)]),
        ]
        selected, report = subject_tracking.select_subject_track(frames, config)
        self.assertEqual([body["body_id"] for body in selected], [10, 10, 30])
        self.assertEqual(report["body_id_history"], [10, 30])
        self.assertEqual(report["reassociation_count"], 1)

    def test_single_frame_candidate_does_not_trigger_reassociation(self):
        config = dataclasses.replace(
            self.config,
            lock_window_frames=2,
            temporary_loss_frames=0,
            reassociation_confirmation_frames=2,
        )
        frames = [
            make_frame(0, [make_body(10)]),
            make_frame(1, [make_body(10)]),
            make_frame(2, [make_body(30, x=20)]),
            make_frame(3, []),
        ]
        selected, report = subject_tracking.select_subject_track(frames, config)
        self.assertEqual({body["body_id"] for body in selected}, {10})
        self.assertEqual(report["reassociation_count"], 0)

    def test_ambiguous_new_ids_are_rejected(self):
        config = dataclasses.replace(
            self.config,
            lock_window_frames=2,
            temporary_loss_frames=0,
            reassociation_confirmation_frames=1,
            ambiguity_margin=0.5,
        )
        frames = [
            make_frame(0, [make_body(10)]),
            make_frame(1, [make_body(10)]),
            make_frame(2, [make_body(30, x=20), make_body(40, x=25)]),
        ]
        selected, report = subject_tracking.select_subject_track(frames, config)
        self.assertEqual({body["body_id"] for body in selected}, {10})
        self.assertGreater(report["ambiguous_candidate_count"], 0)

    def test_distant_new_id_is_rejected(self):
        config = dataclasses.replace(
            self.config,
            lock_window_frames=2,
            temporary_loss_frames=0,
            reassociation_confirmation_frames=1,
        )
        tracker = subject_tracking.ActiveUserTracker(config, 10)
        tracker.update(make_frame(0, [make_body(10, x=0)]))
        body, _ = tracker.update(make_frame(1, [make_body(30, x=850)]))
        self.assertIsNone(body)
        self.assertEqual(tracker.reassociation_count, 0)


if __name__ == "__main__":
    unittest.main()
