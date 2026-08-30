"""Low-latency, profile-driven feedback over a growing motion session."""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np

from assessment import AXIS_INDEX, score_errors, weighted_sequence
from exercise_profile import ExerciseProfile
from joint_filter import JointFilterBank, JointFilterConfig
from motion_data import FRAMES_NAME, load_session_track
from motion_preprocessing import prepare_motion, retain_usable_frames
from subject_tracking import ActiveUserTracker, SubjectTrackingConfig, body_anchor, select_subject_track


CONFIG_FORMAT = "trainercam.realtime-feedback-config"
CONFIG_SCHEMA_VERSION = 1
EVENT_FORMAT = "trainercam.realtime-feedback-event"
EVENT_SCHEMA_VERSION = 1
SUMMARY_FORMAT = "trainercam.realtime-feedback-summary"


class RealtimeFeedbackError(ValueError):
    pass


@dataclass(frozen=True)
class RealtimeFeedbackConfig:
    lookahead_frames: int
    backtrack_frames: int
    reference_smoothing_sigma: float
    minimum_bad_frames: int
    minimum_good_frames: int
    cooldown_ms: int
    tracking_warning_frames: int
    joint_filter: JointFilterConfig
    poll_interval_ms: int
    startup_timeout_sec: float
    completion_marker: str
    source_path: str


def resolve_realtime_config_path(value: str | None = None) -> Path:
    candidates: List[Path] = []
    if value:
        candidates.append(Path(value))
    else:
        configured = os.environ.get("TRAINER_CAM_REALTIME_FEEDBACK_CONFIG")
        if configured:
            candidates.append(Path(configured))
        candidates.extend(
            (
                Path.cwd() / "config" / "realtime_feedback.json",
                Path(__file__).resolve().parents[1] / "config" / "realtime_feedback.json",
            )
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "Real-time feedback configuration was not found. Checked: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def _integer(raw: Dict[str, Any], key: str, minimum: int) -> int:
    try:
        value = int(raw[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise RealtimeFeedbackError(f"{key} must be an integer") from exc
    if value < minimum:
        raise RealtimeFeedbackError(f"{key} must be at least {minimum}")
    return value


def parse_realtime_config(
    raw: Dict[str, Any], source_path: str = "<memory>"
) -> RealtimeFeedbackConfig:
    if raw.get("format") != CONFIG_FORMAT:
        raise RealtimeFeedbackError(f"Unsupported feedback format: {raw.get('format')!r}")
    if raw.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise RealtimeFeedbackError(
            f"Unsupported feedback schema version: {raw.get('schema_version')!r}"
        )
    alignment = raw.get("alignment", {})
    feedback = raw.get("feedback", {})
    runtime = raw.get("runtime", {})
    filtering = raw.get("joint_filter", {})
    smoothing = float(alignment.get("reference_smoothing_sigma", 0.0))
    startup_timeout = float(runtime.get("startup_timeout_sec", 30.0))
    marker = str(runtime.get("completion_marker", "")).strip()
    if not math.isfinite(smoothing) or smoothing < 0:
        raise RealtimeFeedbackError("reference_smoothing_sigma cannot be negative")
    if not math.isfinite(startup_timeout) or startup_timeout <= 0:
        raise RealtimeFeedbackError("startup_timeout_sec must be positive")
    if not marker or Path(marker).name != marker:
        raise RealtimeFeedbackError("completion_marker must be a file name")
    joint_filter = JointFilterConfig(
        ema_alpha_high_confidence=float(filtering.get("ema_alpha_high_confidence", 0.65)),
        ema_alpha_low_confidence=float(filtering.get("ema_alpha_low_confidence", 0.25)),
        maximum_hold_frames=int(filtering.get("maximum_hold_frames", 3)),
        maximum_joint_speed_body_scales_per_second=float(
            filtering.get("maximum_joint_speed_body_scales_per_second", 8.0)
        ),
        recovery_blend_frames=int(filtering.get("recovery_blend_frames", 3)),
    )
    try:
        JointFilterBank(joint_filter)
    except ValueError as exc:
        raise RealtimeFeedbackError(str(exc)) from exc
    return RealtimeFeedbackConfig(
        lookahead_frames=_integer(alignment, "lookahead_frames", 1),
        backtrack_frames=_integer(alignment, "backtrack_frames", 0),
        reference_smoothing_sigma=smoothing,
        minimum_bad_frames=_integer(feedback, "minimum_bad_frames", 1),
        minimum_good_frames=_integer(feedback, "minimum_good_frames", 1),
        cooldown_ms=_integer(feedback, "cooldown_ms", 0),
        tracking_warning_frames=_integer(feedback, "tracking_warning_frames", 1),
        joint_filter=joint_filter,
        poll_interval_ms=_integer(runtime, "poll_interval_ms", 10),
        startup_timeout_sec=startup_timeout,
        completion_marker=marker,
        source_path=source_path,
    )


def load_realtime_config(value: str | None = None) -> RealtimeFeedbackConfig:
    path = resolve_realtime_config_path(value)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RealtimeFeedbackError(f"Invalid feedback configuration JSON: {path}") from exc
    return parse_realtime_config(raw, source_path=str(path))


def angles_from_positions(positions: np.ndarray, profile: ExerciseProfile) -> np.ndarray:
    """Return segment-to-axis angles with shape [frame, Z/Y/X, feature]."""
    result = np.zeros((positions.shape[0], 3, len(profile.features)), dtype=np.float64)
    axes = np.asarray(((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)))
    for feature_index, feature in enumerate(profile.features):
        vectors = positions[:, feature.joints[1]] - positions[:, feature.joints[0]]
        norms = np.linalg.norm(vectors, axis=1)
        safe = norms > 1e-12
        if np.any(safe):
            cosine = np.zeros((positions.shape[0], 3), dtype=np.float64)
            cosine[safe] = (vectors[safe] @ axes.T) / norms[safe, None]
            result[:, :, feature_index] = np.degrees(
                np.arccos(np.clip(cosine, -1.0, 1.0))
            )
    return result


def smooth_angles(values: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0 or values.shape[0] < 2:
        return values.copy()
    radius = max(1, int(round(3 * sigma)))
    samples = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(samples * samples) / (2 * sigma * sigma))
    kernel /= np.sum(kernel)
    result = np.empty_like(values)
    for axis in range(values.shape[1]):
        for feature in range(values.shape[2]):
            padded = np.pad(values[:, axis, feature], radius, mode="edge")
            result[:, axis, feature] = np.convolve(padded, kernel, mode="valid")
    return result


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RealtimeFeedbackEngine:
    def __init__(
        self,
        reference_angles: np.ndarray,
        profile: ExerciseProfile,
        config: RealtimeFeedbackConfig,
    ) -> None:
        if reference_angles.ndim != 3 or reference_angles.shape[0] == 0:
            raise RealtimeFeedbackError("Reference motion must contain angle frames")
        self.reference_angles = reference_angles.astype(np.float64)
        self.reference_sequence = weighted_sequence(self.reference_angles, profile)
        self.profile = profile
        self.config = config
        self.reference_index = 0
        self.bad_feature_id: str | None = None
        self.bad_streak = 0
        self.good_streak = 0
        self.active_feature_id: str | None = None
        self.last_emit_ms = -math.inf
        self.latencies_ms: List[float] = []

    def _event(
        self,
        status: str,
        frame_index: int,
        timestamp_usec: int | None,
        message: str,
        started: float,
        feature=None,
        score: float | None = None,
        error: float | None = None,
    ) -> Dict[str, Any]:
        latency = (time.perf_counter() - started) * 1000.0
        self.latencies_ms.append(latency)
        return {
            "format": EVENT_FORMAT,
            "schema_version": EVENT_SCHEMA_VERSION,
            "created_at": _created_at(),
            "status": status,
            "frame_index": int(frame_index),
            "timestamp_usec": timestamp_usec,
            "reference_frame_index": self.reference_index if status != "tracking" else None,
            "feature_id": feature.feature_id if feature is not None else None,
            "feature_label": feature.label if feature is not None else None,
            "score": None if score is None else round(float(score), 2),
            "error_deg": None if error is None else round(float(error), 2),
            "message": message,
            "processing_latency_ms": round(latency, 3),
        }

    def tracking_event(
        self,
        frame_index: int,
        timestamp_usec: int | None,
        message: str,
        event_type: str = "tracking_temporarily_lost",
    ) -> Dict[str, Any]:
        event = self._event(
            "tracking", frame_index, timestamp_usec, message, time.perf_counter()
        )
        event["event_type"] = event_type
        return event

    def evaluate(
        self,
        customer_angles: np.ndarray,
        frame_index: int,
        timestamp_usec: int | None = None,
        now_ms: float | None = None,
    ) -> Dict[str, Any] | None:
        started = time.perf_counter()
        values = np.asarray(customer_angles, dtype=np.float64)
        if values.shape != self.reference_angles.shape[1:]:
            raise RealtimeFeedbackError("Customer angle frame has an unexpected shape")
        sequence = weighted_sequence(values[None, :, :], self.profile)[0]
        start = max(0, self.reference_index - self.config.backtrack_frames)
        end = min(
            len(self.reference_sequence),
            self.reference_index + self.config.lookahead_frames + 1,
        )
        distances = np.sum((self.reference_sequence[start:end] - sequence) ** 2, axis=1)
        self.reference_index = start + int(np.argmin(distances))

        feature_results = []
        for feature_index, feature in enumerate(self.profile.features):
            axes = [AXIS_INDEX[axis] for axis in feature.axes]
            difference = (
                values[axes, feature_index]
                - self.reference_angles[self.reference_index, axes, feature_index]
            )
            error = float(np.sqrt(np.mean(difference * difference)))
            score = score_errors(
                [error],
                feature.good_error_deg,
                feature.bad_error_deg,
                self.profile.outlier_penalty,
            )
            feature_results.append((score, error, feature))
        score, error, worst = min(feature_results, key=lambda item: item[0])
        clock_ms = now_ms if now_ms is not None else time.monotonic() * 1000.0

        if score < self.profile.feedback_below_score:
            self.good_streak = 0
            if self.bad_feature_id == worst.feature_id:
                self.bad_streak += 1
            else:
                self.bad_feature_id = worst.feature_id
                self.bad_streak = 1
            ready = self.bad_streak >= self.config.minimum_bad_frames
            cooled = clock_ms - self.last_emit_ms >= self.config.cooldown_ms
            changed = self.active_feature_id != worst.feature_id
            if ready and (cooled or changed):
                self.active_feature_id = worst.feature_id
                self.last_emit_ms = clock_ms
                return self._event(
                    "adjust", frame_index, timestamp_usec, worst.feedback,
                    started, worst, score, error
                )
        else:
            self.bad_feature_id = None
            self.bad_streak = 0
            self.good_streak += 1
            if (
                self.active_feature_id is not None
                and self.good_streak >= self.config.minimum_good_frames
            ):
                self.active_feature_id = None
                self.last_emit_ms = clock_ms
                return self._event(
                    "correct", frame_index, timestamp_usec,
                    "Movement is back within the configured range.", started
                )
        self.latencies_ms.append((time.perf_counter() - started) * 1000.0)
        return None


def _normalise_live_frame(raw: Dict[str, Any]) -> Dict[str, Any]:
    # The recorder already writes the v1 frame shape. Keep only a small amount
    # of defensive conversion so a partially flushed line is retried, not scored.
    return {
        "frame_index": int(raw["frame_index"]),
        "timestamp_usec": raw.get("timestamp_usec"),
        "image": raw.get("image"),
        "bodies": raw.get("bodies", []),
    }


class _LiveOverlay:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.cv2 = None
        self.last_event: Dict[str, Any] | None = None
        if enabled:
            try:
                import cv2
            except ImportError as exc:
                raise RealtimeFeedbackError("--live-display requires OpenCV") from exc
            self.cv2 = cv2

    def update(self, folder: Path, frame: Dict[str, Any], event: Dict[str, Any] | None) -> None:
        if not self.enabled:
            return
        if event is not None:
            self.last_event = event
        image_name = frame.get("image")
        if not image_name:
            return
        image = self.cv2.imread(str(folder / image_name))
        if image is None:
            return
        current = self.last_event
        if current:
            colours = {"adjust": (0, 80, 255), "correct": (0, 180, 0), "tracking": (0, 180, 255)}
            colour = colours.get(current["status"], (255, 255, 255))
            self.cv2.rectangle(image, (10, 10), (image.shape[1] - 10, 90), (20, 20, 20), -1)
            self.cv2.putText(image, current["status"].upper(), (25, 42), self.cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2)
            self.cv2.putText(image, current["message"][:80], (25, 75), self.cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 1)
        self.cv2.namedWindow("TrainerCam Live Feedback", self.cv2.WINDOW_NORMAL)
        self.cv2.imshow("TrainerCam Live Feedback", image)
        self.cv2.waitKey(1)

    def close(self) -> None:
        if self.enabled:
            self.cv2.destroyWindow("TrainerCam Live Feedback")


def _write_event(stream, event: Dict[str, Any]) -> None:
    encoded = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    stream.write(encoded + "\n")
    stream.flush()
    print(encoded, flush=True)


def run_realtime_feedback(
    tutor_folder: str | Path,
    customer_folder: str | Path,
    profile: ExerciseProfile,
    tracking_config: SubjectTrackingConfig,
    realtime_config: RealtimeFeedbackConfig,
    output_path: str | Path | None = None,
    summary_path: str | Path | None = None,
    display: bool = False,
    max_wait_seconds: float = 3600.0,
) -> Dict[str, Any]:
    tutor_bodies, tutor_tracking = load_session_track(
        tutor_folder, tracking_config=tracking_config
    )
    if not tutor_tracking.get("gate_passed"):
        raise RealtimeFeedbackError(
            "Tutor reference failed subject tracking gates: "
            + "; ".join(tutor_tracking.get("gate_failures", []))
        )
    tutor_motion = prepare_motion(tutor_bodies)
    tutor_motion = retain_usable_frames(tutor_motion, profile.required_joints)
    tutor_angles = angles_from_positions(tutor_motion.positions, profile)
    tutor_angles = smooth_angles(tutor_angles, realtime_config.reference_smoothing_sigma)
    engine = RealtimeFeedbackEngine(tutor_angles, profile, realtime_config)

    customer = Path(customer_folder)
    frames_path = customer / FRAMES_NAME
    completion_path = customer / realtime_config.completion_marker
    output = Path(output_path) if output_path else customer / "live_feedback.jsonl"
    summary = Path(summary_path) if summary_path else customer / "live_feedback_summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    overlay = _LiveOverlay(display)
    started = time.monotonic()
    while not frames_path.is_file():
        if time.monotonic() - started > realtime_config.startup_timeout_sec:
            raise TimeoutError(f"Live motion frames did not appear: {frames_path}")
        time.sleep(realtime_config.poll_interval_ms / 1000.0)

    buffer: List[Dict[str, Any]] = []
    tracker: ActiveUserTracker | None = None
    joint_filter = JointFilterBank(realtime_config.joint_filter)
    processed_indices = set()
    last_tracking_warning = -1
    last_multiple_warning = -1
    distance_state = "inside"
    event_counts = {"adjust": 0, "correct": 0, "tracking": 0}

    def process_frame(frame: Dict[str, Any], stream) -> None:
        nonlocal last_tracking_warning, last_multiple_warning, distance_state
        if frame["frame_index"] in processed_indices or tracker is None:
            return
        processed_indices.add(frame["frame_index"])
        body, tracking_change = tracker.update(frame)
        event = None
        if len(frame.get("bodies", [])) > 1 and (
            frame["frame_index"] - last_multiple_warning >= realtime_config.tracking_warning_frames
        ):
            event = engine.tracking_event(
                frame["frame_index"], frame.get("timestamp_usec"),
                "Multiple people are visible. The current trainee remains locked.",
                "multiple_people",
            )
            last_multiple_warning = frame["frame_index"]
        if body is None:
            if (
                tracker.lost_frames >= realtime_config.tracking_warning_frames
                and frame["frame_index"] - last_tracking_warning >= realtime_config.tracking_warning_frames
            ):
                event_type = "tracking_lost" if tracker.state == "LOST" else "tracking_temporarily_lost"
                event = engine.tracking_event(
                    frame["frame_index"], frame.get("timestamp_usec"),
                    "The locked trainee is not visible. Return to the training region.",
                    event_type,
                )
                last_tracking_warning = frame["frame_index"]
        else:
            if tracking_change == "tracking_recovered":
                event = engine.tracking_event(
                    frame["frame_index"], frame.get("timestamp_usec"),
                    "Trainee tracking recovered.", "tracking_recovered"
                )
            value = dict(body)
            value.update(
                frame_index=frame["frame_index"],
                timestamp_usec=frame.get("timestamp_usec"),
                image=frame.get("image"),
            )
            filtered, filter_quality = joint_filter.update(value, frame.get("timestamp_usec"))
            prepared = prepare_motion([filtered], max_interpolation_gap=0)
            coverage = prepared.coverage(profile.required_joints)
            if coverage < 1.0:
                event = engine.tracking_event(
                    frame["frame_index"], frame.get("timestamp_usec"),
                    "Keep the configured body joints visible to continue feedback.",
                    "required_joints_occluded",
                )
            else:
                anchor = body_anchor(body, tracking_config)
                next_distance_state = distance_state
                if anchor is not None and distance_state == "inside" and anchor[2] < tracking_config.roi_z_mm[0]:
                    next_distance_state = "too_close"
                elif anchor is not None and distance_state == "inside" and anchor[2] > tracking_config.roi_z_mm[1]:
                    next_distance_state = "too_far"
                elif anchor is not None and distance_state == "too_close" and anchor[2] >= tracking_config.roi_z_mm[0] + 100:
                    next_distance_state = "inside"
                elif anchor is not None and distance_state == "too_far" and anchor[2] <= tracking_config.roi_z_mm[1] - 100:
                    next_distance_state = "inside"
                if next_distance_state == "too_close" and next_distance_state != distance_state:
                    event = engine.tracking_event(
                        frame["frame_index"], frame.get("timestamp_usec"),
                        "Step back to remain inside the training region.", "step_back"
                    )
                elif next_distance_state == "too_far" and next_distance_state != distance_state:
                    event = engine.tracking_event(
                        frame["frame_index"], frame.get("timestamp_usec"),
                        "Move closer to remain inside the training region.", "move_closer"
                    )
                distance_state = next_distance_state
                angles = angles_from_positions(prepared.positions, profile)[0]
                if event is None:
                    event = engine.evaluate(
                        angles, frame["frame_index"], frame.get("timestamp_usec")
                    )
        if event is not None:
            event_counts[event["status"]] += 1
            _write_event(stream, event)
        overlay.update(customer, frame, event)

    try:
        with frames_path.open("r", encoding="utf-8") as source, output.open(
            "w", encoding="utf-8", newline="\n"
        ) as event_stream:
            while True:
                line_start = source.tell()
                line = source.readline()
                if line:
                    try:
                        frame = _normalise_live_frame(json.loads(line))
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        source.seek(line_start)
                        time.sleep(realtime_config.poll_interval_ms / 1000.0)
                        continue
                    buffer.append(frame)
                    if tracker is None and len(buffer) >= tracking_config.lock_window_frames:
                        lock_candidates = buffer[-tracking_config.lock_window_frames :]
                        _, report = select_subject_track(lock_candidates, tracking_config)
                        initial_body_id = report.get("selected_body_id")
                        if initial_body_id is not None:
                            tracker = ActiveUserTracker(tracking_config, initial_body_id)
                            for buffered in buffer:
                                process_frame(buffered, event_stream)
                        elif (
                            frame["frame_index"] - last_tracking_warning
                            >= realtime_config.tracking_warning_frames
                        ):
                            event = engine.tracking_event(
                                frame["frame_index"], frame.get("timestamp_usec"),
                                "Stand inside the configured training region to start feedback.",
                                "stand_in_training_region",
                            )
                            event_counts["tracking"] += 1
                            _write_event(event_stream, event)
                            overlay.update(customer, frame, event)
                            last_tracking_warning = frame["frame_index"]
                    elif tracker is not None:
                        process_frame(frame, event_stream)
                    continue

                completed = completion_path.is_file()
                if completed:
                    if tracker is None and buffer:
                        lock_candidates = buffer[-tracking_config.lock_window_frames :]
                        _, report = select_subject_track(lock_candidates, tracking_config)
                        initial_body_id = report.get("selected_body_id")
                        if initial_body_id is not None:
                            tracker = ActiveUserTracker(tracking_config, initial_body_id)
                            for buffered in buffer:
                                process_frame(buffered, event_stream)
                        else:
                            event = engine.tracking_event(
                                buffer[-1]["frame_index"],
                                buffer[-1].get("timestamp_usec"),
                                "No trainee could be locked inside the training region.",
                                "stand_in_training_region",
                            )
                            event_counts["tracking"] += 1
                            _write_event(event_stream, event)
                            overlay.update(customer, buffer[-1], event)
                    break
                if time.monotonic() - started > max_wait_seconds:
                    raise TimeoutError("Real-time feedback exceeded its maximum session duration")
                time.sleep(realtime_config.poll_interval_ms / 1000.0)
    finally:
        overlay.close()

    latencies = np.asarray(engine.latencies_ms, dtype=np.float64)
    result = {
        "format": SUMMARY_FORMAT,
        "schema_version": 1,
        "created_at": _created_at(),
        "selected_body_id": tracker.current_body_id if tracker is not None else None,
        "subject_locked": tracker is not None and tracker.current_body_id is not None,
        "processed_frame_count": len(processed_indices),
        "event_counts": event_counts,
        "processing_latency_ms": {
            "mean": round(float(np.mean(latencies)), 3) if latencies.size else None,
            "p95": round(float(np.percentile(latencies, 95)), 3) if latencies.size else None,
            "maximum": round(float(np.max(latencies)), 3) if latencies.size else None,
        },
        "output_file": output.name,
        "subject_tracking": tracker.diagnostics() if tracker is not None else None,
        "joint_filter": {
            "outlier_rejection_count": joint_filter.outlier_rejection_count,
        },
    }
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
