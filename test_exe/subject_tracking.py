"""Persistent subject selection and session gates for multi-person recordings."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


TRACKING_FORMAT = "trainercam.subject-tracking-config"
TRACKING_SCHEMA_VERSION = 1


class SubjectTrackingError(ValueError):
    pass


@dataclass(frozen=True)
class SubjectTrackingConfig:
    anchor_joint: int
    lock_window_frames: int
    min_anchor_confidence: int
    roi_x_mm: Tuple[float, float]
    roi_z_mm: Tuple[float, float]
    min_track_coverage: float
    min_in_roi_fraction: float
    max_consecutive_missing_frames: int
    max_anchor_jump_mm: float
    reassociation_max_distance_mm: float
    reassociation_max_scale_ratio: float
    reassociation_confirmation_frames: int
    temporary_loss_frames: int
    reinitialize_after_frames: int
    ambiguity_margin: float
    velocity_smoothing: float
    source_path: str


def resolve_tracking_config_path(value: str | None = None) -> Path:
    candidates: List[Path] = []
    if value:
        candidates.append(Path(value))
    else:
        configured = os.environ.get("TRAINER_CAM_SUBJECT_TRACKING_CONFIG")
        if configured:
            candidates.append(Path(configured))
        candidates.extend(
            (
                Path.cwd() / "config" / "subject_tracking.json",
                Path(__file__).resolve().parents[1] / "config" / "subject_tracking.json",
            )
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "Subject tracking configuration was not found. Checked: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def _bounded_fraction(raw: Dict[str, Any], key: str) -> float:
    try:
        value = float(raw[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise SubjectTrackingError(f"{key} must be numeric") from exc
    if not 0.0 <= value <= 1.0:
        raise SubjectTrackingError(f"{key} must be between 0 and 1")
    return value


def _range(raw: Any, name: str) -> Tuple[float, float]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise SubjectTrackingError(f"{name} must contain [minimum, maximum]")
    try:
        values = (float(raw[0]), float(raw[1]))
    except (TypeError, ValueError) as exc:
        raise SubjectTrackingError(f"{name} must contain finite numbers") from exc
    if not all(math.isfinite(value) for value in values) or values[0] >= values[1]:
        raise SubjectTrackingError(f"{name} requires a finite minimum < maximum")
    return values


def parse_tracking_config(
    raw: Dict[str, Any], source_path: str = "<memory>"
) -> SubjectTrackingConfig:
    if raw.get("format") != TRACKING_FORMAT:
        raise SubjectTrackingError(f"Unsupported tracking format: {raw.get('format')!r}")
    if raw.get("schema_version") != TRACKING_SCHEMA_VERSION:
        raise SubjectTrackingError(
            f"Unsupported tracking schema version: {raw.get('schema_version')!r}"
        )
    selection = raw.get("selection", {})
    roi = raw.get("region_of_interest_mm", {})
    gates = raw.get("session_gates", {})
    reassociation = raw.get("reassociation", {})
    anchor_joint = int(selection.get("anchor_joint", 0))
    lock_window = int(selection.get("lock_window_frames", 30))
    min_confidence = int(selection.get("min_anchor_confidence", 1))
    max_missing = int(gates.get("max_consecutive_missing_frames", 30))
    max_jump = float(gates.get("max_anchor_jump_mm", 800.0))
    if not 0 <= anchor_joint < 32:
        raise SubjectTrackingError("anchor_joint must be between 0 and 31")
    if lock_window < 1:
        raise SubjectTrackingError("lock_window_frames must be at least 1")
    if not 0 <= min_confidence <= 3:
        raise SubjectTrackingError("min_anchor_confidence must be between 0 and 3")
    if max_missing < 0:
        raise SubjectTrackingError("max_consecutive_missing_frames cannot be negative")
    if not math.isfinite(max_jump) or max_jump <= 0:
        raise SubjectTrackingError("max_anchor_jump_mm must be positive")
    max_distance = float(reassociation.get("reassociation_max_distance_mm", 450.0))
    max_scale_ratio = float(reassociation.get("reassociation_max_scale_ratio", 1.35))
    confirmation_frames = int(reassociation.get("reassociation_confirmation_frames", 3))
    temporary_loss_frames = int(reassociation.get("temporary_loss_frames", 5))
    reinitialize_after_frames = int(reassociation.get("reinitialize_after_frames", 90))
    ambiguity_margin = float(reassociation.get("ambiguity_margin", 0.2))
    velocity_smoothing = float(reassociation.get("velocity_smoothing", 0.5))
    if not math.isfinite(max_distance) or max_distance <= 0:
        raise SubjectTrackingError("reassociation_max_distance_mm must be positive")
    if not math.isfinite(max_scale_ratio) or max_scale_ratio < 1:
        raise SubjectTrackingError("reassociation_max_scale_ratio must be at least 1")
    if confirmation_frames < 1 or temporary_loss_frames < 0 or reinitialize_after_frames < 1:
        raise SubjectTrackingError("reassociation frame thresholds are invalid")
    if not math.isfinite(ambiguity_margin) or ambiguity_margin < 0:
        raise SubjectTrackingError("ambiguity_margin cannot be negative")
    if not 0 <= velocity_smoothing <= 1:
        raise SubjectTrackingError("velocity_smoothing must be between 0 and 1")
    return SubjectTrackingConfig(
        anchor_joint=anchor_joint,
        lock_window_frames=lock_window,
        min_anchor_confidence=min_confidence,
        roi_x_mm=_range(roi.get("x", [-900, 900]), "region_of_interest_mm.x"),
        roi_z_mm=_range(roi.get("z", [700, 4000]), "region_of_interest_mm.z"),
        min_track_coverage=_bounded_fraction(gates, "min_track_coverage"),
        min_in_roi_fraction=_bounded_fraction(gates, "min_in_roi_fraction"),
        max_consecutive_missing_frames=max_missing,
        max_anchor_jump_mm=max_jump,
        reassociation_max_distance_mm=max_distance,
        reassociation_max_scale_ratio=max_scale_ratio,
        reassociation_confirmation_frames=confirmation_frames,
        temporary_loss_frames=temporary_loss_frames,
        reinitialize_after_frames=reinitialize_after_frames,
        ambiguity_margin=ambiguity_margin,
        velocity_smoothing=velocity_smoothing,
        source_path=source_path,
    )


def load_tracking_config(value: str | None = None) -> SubjectTrackingConfig:
    path = resolve_tracking_config_path(value)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SubjectTrackingError(f"Invalid tracking configuration JSON: {path}") from exc
    return parse_tracking_config(raw, source_path=str(path))


def _joint(body: Dict[str, Any], index: int) -> Dict[str, Any] | None:
    return next(
        (
            joint
            for fallback, joint in enumerate(body.get("joints", []))
            if int(joint.get("joint_index", joint.get("index", fallback))) == index
        ),
        None,
    )


def _valid_position(
    joint: Dict[str, Any] | None,
    min_confidence: int,
    confidence_available: bool,
) -> List[float] | None:
    if joint is None:
        return None
    values = joint.get("position_mm", joint.get("position"))
    if not isinstance(values, list) or len(values) != 3:
        return None
    position = [float(value) for value in values]
    if not all(math.isfinite(value) for value in position) or not any(abs(value) > 1e-6 for value in position):
        return None
    confidence = int(joint.get("confidence_level", 0))
    if confidence_available and confidence < min_confidence:
        return None
    return position


def body_anchor(body: Dict[str, Any], config: SubjectTrackingConfig) -> List[float] | None:
    confidence_available = any(
        int(joint.get("confidence_level", 0)) > 0 for joint in body.get("joints", [])
    )
    preferred = _valid_position(
        _joint(body, config.anchor_joint),
        config.min_anchor_confidence,
        confidence_available,
    )
    if preferred is not None:
        return preferred
    # Some migrated legacy sessions have no pelvis value. A median of observed
    # landmarks gives a stable fallback without pretending that (0, 0, 0) is real.
    positions = []
    for joint in body.get("joints", []):
        candidate = _valid_position(
            joint, config.min_anchor_confidence, confidence_available
        )
        if candidate is not None:
            positions.append(candidate)
    if not positions:
        return None
    return [float(sorted(axis)[len(axis) // 2]) for axis in zip(*positions)]


def _in_roi(anchor: Sequence[float] | None, config: SubjectTrackingConfig) -> bool:
    return bool(
        anchor is not None
        and config.roi_x_mm[0] <= anchor[0] <= config.roi_x_mm[1]
        and config.roi_z_mm[0] <= anchor[2] <= config.roi_z_mm[1]
    )


def _maximum_missing_run(frames: Sequence[Dict[str, Any]], body_id: int) -> int:
    maximum = current = 0
    for frame in frames:
        present = any(int(body["body_id"]) == body_id for body in frame.get("bodies", []))
        current = 0 if present else current + 1
        maximum = max(maximum, current)
    return maximum


def _body_scale(body: Dict[str, Any], config: SubjectTrackingConfig) -> float | None:
    confidence_available = any(
        int(joint.get("confidence_level", 0)) > 0 for joint in body.get("joints", [])
    )
    left = _valid_position(_joint(body, 5), config.min_anchor_confidence, confidence_available)
    right = _valid_position(_joint(body, 12), config.min_anchor_confidence, confidence_available)
    if left is None or right is None:
        return None
    value = math.dist(left, right)
    return value if math.isfinite(value) and value > 1e-6 else None


def _initial_body_id(
    frames: Sequence[Dict[str, Any]], config: SubjectTrackingConfig
) -> int | None:
    stats: Dict[int, Dict[str, float]] = {}
    for frame in frames[: config.lock_window_frames]:
        for body in frame.get("bodies", []):
            identifier = int(body["body_id"])
            anchor = body_anchor(body, config)
            item = stats.setdefault(
                identifier, {"seen": 0, "in_roi": 0, "confidence": 0, "distance": 0}
            )
            item["seen"] += 1
            item["confidence"] += sum(
                int(joint.get("confidence_level", 0)) for joint in body.get("joints", [])
            )
            if _in_roi(anchor, config):
                item["in_roi"] += 1
                center_x = (config.roi_x_mm[0] + config.roi_x_mm[1]) * 0.5
                center_z = (config.roi_z_mm[0] + config.roi_z_mm[1]) * 0.5
                item["distance"] += math.hypot(anchor[0] - center_x, anchor[2] - center_z)
    eligible = [identifier for identifier, value in stats.items() if value["in_roi"] > 0]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda identifier: (
            stats[identifier]["in_roi"],
            stats[identifier]["seen"],
            stats[identifier]["confidence"],
            -stats[identifier]["distance"],
            -identifier,
        ),
    )


class ActiveUserTracker:
    """Stateful body-ID tracker with conservative spatial reassociation."""

    def __init__(self, config: SubjectTrackingConfig, body_id: int | None = None) -> None:
        self.config = config
        self.initial_body_id = body_id
        self.current_body_id = body_id
        self.state = "LOCKED" if body_id is not None else "UNINITIALIZED"
        self.last_anchor: List[float] | None = None
        self.velocity = [0.0, 0.0, 0.0]
        self.last_scale: float | None = None
        self.lost_frames = 0
        self.candidate_id: int | None = None
        self.candidate_streak = 0
        self.known_bystanders: set[int] = set()
        self.body_id_history: List[int] = [] if body_id is None else [body_id]
        self.transitions: List[Dict[str, Any]] = []
        self.reassociation_count = 0
        self.successful_recovery_count = 0
        self.ambiguous_candidate_count = 0
        self.rejected_switch_count = 0
        self.lost_frame_count = 0
        self.maximum_recovery_latency_frames = 0

    def _transition(self, state: str, frame_index: int, reason: str) -> str | None:
        if state == self.state:
            return None
        previous = self.state
        self.state = state
        self.transitions.append(
            {"frame_index": int(frame_index), "from": previous, "to": state, "reason": reason}
        )
        return state.lower()

    def _accept(self, body: Dict[str, Any], frame_index: int, recovered: bool) -> None:
        anchor = body_anchor(body, self.config)
        if anchor is not None:
            if self.last_anchor is not None and not recovered:
                delta = [right - left for left, right in zip(self.last_anchor, anchor)]
                weight = self.config.velocity_smoothing
                self.velocity = [
                    weight * current + (1.0 - weight) * previous
                    for current, previous in zip(delta, self.velocity)
                ]
            else:
                self.velocity = [0.0, 0.0, 0.0]
            self.last_anchor = anchor
        scale = _body_scale(body, self.config)
        if scale is not None:
            self.last_scale = scale if self.last_scale is None else 0.8 * self.last_scale + 0.2 * scale
        if recovered:
            previous_id = self.current_body_id
            self.current_body_id = int(body["body_id"])
            self.reassociation_count += 1
            self.successful_recovery_count += 1
            self.maximum_recovery_latency_frames = max(
                self.maximum_recovery_latency_frames, self.lost_frames
            )
            if previous_id != self.current_body_id:
                self.body_id_history.append(self.current_body_id)
        self.lost_frames = 0
        self.candidate_id = None
        self.candidate_streak = 0
        self._transition("LOCKED", frame_index, "subject recovered" if recovered else "body ID observed")

    def _candidate_cost(self, body: Dict[str, Any]) -> float | None:
        anchor = body_anchor(body, self.config)
        if anchor is None or not _in_roi(anchor, self.config) or self.last_anchor is None:
            return None
        predicted = [
            value + velocity * min(self.lost_frames, self.config.temporary_loss_frames)
            for value, velocity in zip(self.last_anchor, self.velocity)
        ]
        distance = math.dist(predicted, anchor)
        if distance > self.config.reassociation_max_distance_mm:
            return None
        scale_penalty = 0.0
        scale = _body_scale(body, self.config)
        if self.last_scale is not None and scale is not None:
            ratio = max(scale, self.last_scale) / min(scale, self.last_scale)
            if ratio > self.config.reassociation_max_scale_ratio:
                return None
            scale_penalty = abs(math.log(ratio))
        confidence = sum(int(joint.get("confidence_level", 0)) for joint in body.get("joints", []))
        confidence_bonus = min(confidence / (32.0 * 3.0), 1.0) * 0.05
        return distance / self.config.reassociation_max_distance_mm + scale_penalty - confidence_bonus

    def update(self, frame: Dict[str, Any]) -> tuple[Dict[str, Any] | None, str | None]:
        frame_index = int(frame.get("frame_index", 0))
        bodies = frame.get("bodies", [])
        if self.current_body_id is None:
            return None, None
        direct = next(
            (body for body in bodies if int(body.get("body_id", -1)) == self.current_body_id),
            None,
        )
        if direct is not None:
            self.known_bystanders.update(
                int(body.get("body_id", -1))
                for body in bodies
                if int(body.get("body_id", -1)) != self.current_body_id
            )
            recovered = self.lost_frames > 0
            if recovered:
                self.successful_recovery_count += 1
                self.maximum_recovery_latency_frames = max(
                    self.maximum_recovery_latency_frames, self.lost_frames
                )
            self._accept(direct, frame_index, recovered=False)
            return direct, "tracking_recovered" if recovered else None

        self.lost_frames += 1
        self.lost_frame_count += 1
        state = "TEMPORARILY_LOST"
        if self.lost_frames > self.config.temporary_loss_frames:
            state = "REASSOCIATING"
        if self.lost_frames > self.config.reinitialize_after_frames:
            state = "LOST"
        transition = self._transition(state, frame_index, "locked body ID missing")

        if self.lost_frames <= self.config.temporary_loss_frames:
            return None, transition

        candidates = []
        for body in bodies:
            identifier = int(body.get("body_id", -1))
            if identifier in self.known_bystanders:
                self.rejected_switch_count += 1
                continue
            cost = self._candidate_cost(body)
            if cost is not None:
                candidates.append((cost, identifier, body))
        candidates.sort(key=lambda item: (item[0], item[1]))
        if len(candidates) > 1 and candidates[1][0] - candidates[0][0] < self.config.ambiguity_margin:
            self.ambiguous_candidate_count += 1
            self.candidate_id = None
            self.candidate_streak = 0
            return None, transition or "ambiguous_candidate"
        if not candidates:
            self.candidate_id = None
            self.candidate_streak = 0
            return None, transition
        _, identifier, candidate = candidates[0]
        if identifier == self.candidate_id:
            self.candidate_streak += 1
        else:
            self.candidate_id = identifier
            self.candidate_streak = 1
        if self.candidate_streak < self.config.reassociation_confirmation_frames:
            return None, transition
        self._accept(candidate, frame_index, recovered=True)
        return candidate, "tracking_recovered"

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "initial_body_id": self.initial_body_id,
            "current_body_id": self.current_body_id,
            "final_body_id": self.current_body_id,
            "body_id_history": self.body_id_history,
            "reassociation_count": self.reassociation_count,
            "successful_recovery_count": self.successful_recovery_count,
            "ambiguous_candidate_count": self.ambiguous_candidate_count,
            "rejected_switch_count": self.rejected_switch_count,
            "lost_frame_count": self.lost_frame_count,
            "maximum_recovery_latency_frames": self.maximum_recovery_latency_frames,
            "tracker_state": self.state,
            "state_transitions": self.transitions,
        }


def select_subject_track(
    frames: Sequence[Dict[str, Any]],
    config: SubjectTrackingConfig,
    body_id: int | None = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not frames:
        return [], {"gate_passed": False, "gate_failures": ["recording has no frames"]}
    selection_reason = "explicit-body-id" if body_id is not None else "initial-roi-lock"
    if body_id is None:
        body_id = _initial_body_id(frames, config)
    tracker = ActiveUserTracker(config, body_id)

    selected: List[Dict[str, Any]] = []
    anchors: List[List[float]] = []
    in_roi_count = 0
    frames_with_multiple = 0
    max_bodies_in_roi = 0
    for frame in frames:
        bodies = frame.get("bodies", [])
        if len(bodies) > 1:
            frames_with_multiple += 1
        bodies_in_roi = sum(_in_roi(body_anchor(body, config), config) for body in bodies)
        max_bodies_in_roi = max(max_bodies_in_roi, bodies_in_roi)
        match, _ = tracker.update(frame)
        if match is None:
            continue
        anchor = body_anchor(match, config)
        if _in_roi(anchor, config):
            in_roi_count += 1
        if anchor is not None:
            anchors.append(anchor)
        value = dict(match)
        value.update(
            frame_index=frame["frame_index"],
            timestamp_usec=frame.get("timestamp_usec"),
            image=frame.get("image"),
        )
        selected.append(value)

    frame_count = len(frames)
    track_coverage = len(selected) / frame_count
    in_roi_fraction = in_roi_count / len(selected) if selected else 0.0
    present_indices = {int(body["frame_index"]) for body in selected}
    missing_run = maximum = 0
    for frame in frames:
        missing_run = 0 if int(frame["frame_index"]) in present_indices else missing_run + 1
        maximum = max(maximum, missing_run)
    missing_run = maximum
    jumps = [math.dist(left, right) for left, right in zip(anchors[:-1], anchors[1:])]
    max_jump = max(jumps, default=0.0)
    failures = []
    if body_id is None:
        failures.append("no body was found inside the training region during subject lock")
    if track_coverage < config.min_track_coverage:
        failures.append(
            f"locked subject coverage {track_coverage:.1%} is below {config.min_track_coverage:.1%}"
        )
    if in_roi_fraction < config.min_in_roi_fraction:
        failures.append(
            f"subject in-region fraction {in_roi_fraction:.1%} is below {config.min_in_roi_fraction:.1%}"
        )
    if missing_run > config.max_consecutive_missing_frames:
        failures.append(
            f"subject was missing for {missing_run} consecutive frames (limit {config.max_consecutive_missing_frames})"
        )
    if max_jump > config.max_anchor_jump_mm:
        failures.append(
            f"subject anchor jumped {max_jump:.0f} mm (limit {config.max_anchor_jump_mm:.0f} mm)"
        )
    warnings = []
    if max_bodies_in_roi > 1:
        warnings.append("multiple bodies entered the training region; the locked body ID was retained")

    report = {
        "config_file": Path(config.source_path).name,
        "selection_reason": selection_reason,
        "selected_body_id": body_id,
        "total_frame_count": frame_count,
        "track_frame_count": len(selected),
        "track_coverage": round(track_coverage, 6),
        "in_roi_frame_count": in_roi_count,
        "in_roi_fraction": round(in_roi_fraction, 6),
        "max_consecutive_missing_frames": missing_run,
        "max_anchor_jump_mm": round(max_jump, 2),
        "frames_with_multiple_bodies": frames_with_multiple,
        "max_bodies_in_roi": max_bodies_in_roi,
        "gate_passed": not failures,
        "gate_failures": failures,
        "warnings": warnings,
    }
    report.update(tracker.diagnostics())
    return selected, report
