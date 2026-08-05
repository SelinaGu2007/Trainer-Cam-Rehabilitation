import contextlib
import dataclasses
import io
import shutil
import sys
import time
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "test_exe"
sys.path.insert(0, str(ANALYSIS_DIR))

import exercise_profile  # noqa: E402
import realtime_feedback  # noqa: E402
import subject_tracking  # noqa: E402


class RealtimeFeedbackEngineTests(unittest.TestCase):
    def setUp(self):
        self.profile = exercise_profile.load_profile("arm_raise")
        self.config = realtime_feedback.load_realtime_config()
        self.reference = np.zeros((12, 3, len(self.profile.features)), dtype=np.float64)

    def test_default_configuration_is_valid(self):
        self.assertGreater(self.config.lookahead_frames, 0)
        self.assertGreaterEqual(self.config.cooldown_ms, 0)
        self.assertGreaterEqual(self.config.minimum_bad_frames, 2)

    def test_single_bad_frame_does_not_trigger_feedback(self):
        engine = realtime_feedback.RealtimeFeedbackEngine(
            self.reference, self.profile, self.config
        )
        bad = np.zeros_like(self.reference[0])
        bad[:, 0] = 30.0
        self.assertIsNone(engine.evaluate(bad, 0, now_ms=0))
        self.assertIsNone(engine.evaluate(self.reference[0], 1, now_ms=33))

    def test_repeated_local_error_identifies_matching_feature(self):
        engine = realtime_feedback.RealtimeFeedbackEngine(
            self.reference, self.profile, self.config
        )
        bad = np.zeros_like(self.reference[0])
        bad[:, 0] = 30.0
        event = None
        for frame in range(self.config.minimum_bad_frames):
            event = engine.evaluate(bad, frame, now_ms=frame * 33)
        self.assertIsNotNone(event)
        self.assertEqual(event["status"], "adjust")
        self.assertEqual(event["format"], "trainercam.realtime-feedback-event")
        self.assertEqual(event["feature_id"], "left_upper_arm")
        self.assertLess(event["score"], 80)

    def test_cooldown_prevents_repeated_message_spam(self):
        engine = realtime_feedback.RealtimeFeedbackEngine(
            self.reference, self.profile, self.config
        )
        bad = np.zeros_like(self.reference[0])
        bad[:, 0] = 30.0
        first = None
        for frame in range(self.config.minimum_bad_frames):
            first = engine.evaluate(bad, frame, now_ms=frame * 33)
        self.assertIsNotNone(first)
        self.assertIsNone(engine.evaluate(bad, 4, now_ms=200))
        repeated = engine.evaluate(bad, 5, now_ms=self.config.cooldown_ms + 100)
        self.assertIsNotNone(repeated)
        self.assertEqual(repeated["status"], "adjust")

    def test_good_frames_clear_an_active_warning(self):
        engine = realtime_feedback.RealtimeFeedbackEngine(
            self.reference, self.profile, self.config
        )
        bad = np.zeros_like(self.reference[0])
        bad[:, 0] = 30.0
        for frame in range(self.config.minimum_bad_frames):
            engine.evaluate(bad, frame, now_ms=frame * 33)
        event = None
        for offset in range(self.config.minimum_good_frames):
            event = engine.evaluate(
                self.reference[0], 10 + offset, now_ms=2000 + offset * 33
            )
        self.assertIsNotNone(event)
        self.assertEqual(event["status"], "correct")

    def test_online_alignment_searches_forward_reference_window(self):
        reference = self.reference.copy()
        for frame in range(len(reference)):
            reference[frame, :, 0] = frame * 5.0
        engine = realtime_feedback.RealtimeFeedbackEngine(reference, self.profile, self.config)
        engine.evaluate(reference[5], 0, now_ms=0)
        self.assertEqual(engine.reference_index, 5)

    def test_per_frame_processing_is_below_feedback_latency_budget(self):
        engine = realtime_feedback.RealtimeFeedbackEngine(
            self.reference, self.profile, self.config
        )
        started = time.perf_counter()
        for frame in range(100):
            engine.evaluate(self.reference[frame % len(self.reference)], frame, now_ms=frame * 33)
        elapsed_ms = (time.perf_counter() - started) * 1000.0 / 100.0
        self.assertLess(elapsed_ms, 200.0)


class RealtimeFeedbackRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = PROJECT_ROOT / ".test-realtime-data" / self._testMethodName
        self.customer = self.temporary / "customer"
        shutil.copytree(PROJECT_ROOT / "data" / "samples" / "customer_session", self.customer)
        (self.customer / "recording.complete").write_text("complete\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.temporary, ignore_errors=True)

    def test_completed_session_generates_a_latency_summary(self):
        profile = exercise_profile.load_profile("arm_raise")
        tracking = subject_tracking.load_tracking_config()
        config = realtime_feedback.load_realtime_config()
        output = self.customer / "feedback.jsonl"
        summary_path = self.customer / "summary.json"
        with contextlib.redirect_stdout(io.StringIO()):
            summary = realtime_feedback.run_realtime_feedback(
                PROJECT_ROOT / "data" / "samples" / "tutor_session",
                self.customer,
                profile,
                tracking,
                config,
                output_path=output,
                summary_path=summary_path,
                max_wait_seconds=2,
            )
        self.assertEqual(summary["format"], "trainercam.realtime-feedback-summary")
        self.assertEqual(summary["selected_body_id"], 7)
        self.assertEqual(summary["processed_frame_count"], 4)
        self.assertLess(summary["processing_latency_ms"]["p95"], 200.0)
        self.assertTrue(output.is_file())
        self.assertTrue(summary_path.is_file())


if __name__ == "__main__":
    unittest.main()
