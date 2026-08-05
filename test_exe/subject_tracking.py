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


def select_subject_track(
    frames: Sequence[Dict[str, Any]],
    config: SubjectTrackingConfig,
    body_id: int | None = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not frames:
        return [], {"gate_passed": False, "gate_failures": ["recording has no frames"]}
    lock_frames = frames[: config.lock_window_frames]
    stats: Dict[int, Dict[str, float]] = {}
    for frame in lock_frames:
        for body in frame.get("bodies", []):
            identifier = int(body["body_id"])
            anchor = body_anchor(body, config)
            item = stats.setdefault(identifier, {"seen": 0, "in_roi": 0, "confidence": 0, "distance": 0})
            item["seen"] += 1
            item["confidence"] += sum(int(joint.get("confidence_level", 0)) for joint in body.get("joints", []))
            if _in_roi(anchor, config):
                item["in_roi"] += 1
                center_x = (config.roi_x_mm[0] + config.roi_x_mm[1]) * 0.5
                center_z = (config.roi_z_mm[0] + config.roi_z_mm[1]) * 0.5
                item["distance"] += math.hypot(anchor[0] - center_x, anchor[2] - center_z)

    selection_reason = "explicit-body-id" if body_id is not None else "initial-roi-lock"
    if body_id is None and stats:
        eligible = [identifier for identifier, value in stats.items() if value["in_roi"] > 0]
        if eligible:
            body_id = max(
                eligible,
                key=lambda identifier: (
                    stats[identifier]["in_roi"],
                    stats[identifier]["seen"],
                    stats[identifier]["confidence"],
                    -stats[identifier]["distance"],
                    -identifier,
                ),
            )

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
        match = next(
            (body for body in bodies if body_id is not None and int(body["body_id"]) == body_id),
            None,
        )
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
    missing_run = _maximum_missing_run(frames, body_id) if body_id is not None else frame_count
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
    return selected, report
