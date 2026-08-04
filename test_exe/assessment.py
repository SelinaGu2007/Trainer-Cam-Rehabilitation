"""Explainable, profile-driven scoring over an existing DTW alignment."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

import numpy as np

from exercise_profile import ExerciseProfile, FeatureSpec


AXIS_INDEX = {"z": 0, "y": 1, "x": 2}
REPORT_FORMAT = "trainercam.assessment-report"
REPORT_SCHEMA_VERSION = 1


def score_errors(
    errors_deg: Sequence[float],
    good_error_deg: float,
    bad_error_deg: float,
    outlier_penalty: float = 15.0,
) -> float:
    errors = np.asarray(errors_deg, dtype=np.float64)
    errors = errors[np.isfinite(errors)]
    if errors.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(errors * errors)))
    position = (rms - good_error_deg) / max(bad_error_deg - good_error_deg, 1e-9)
    score = 100.0 * (1.0 - float(np.clip(position, 0.0, 1.0)))
    outlier_fraction = float(np.mean(errors > bad_error_deg))
    score -= outlier_penalty * outlier_fraction
    return float(np.clip(score, 0.0, 100.0))


def weighted_sequence(angles: np.ndarray, profile: ExerciseProfile) -> np.ndarray:
    """Flatten configured angle channels and apply sqrt weights for DTW."""
    values = []
    for feature_index, feature in enumerate(profile.features):
        axis_indices = [AXIS_INDEX[axis] for axis in feature.axes]
        scale = np.sqrt(feature.weight / len(axis_indices))
        values.append(angles[:, axis_indices, feature_index] * scale)
    return np.concatenate(values, axis=1).astype(np.float64)


def _aligned_feature_errors(
    customer_angles: np.ndarray,
    tutor_angles: np.ndarray,
    path: Sequence[Tuple[int, int]],
    feature: FeatureSpec,
    feature_index: int,
) -> np.ndarray:
    pairs = np.asarray(path, dtype=np.int64)
    axes = [AXIS_INDEX[axis] for axis in feature.axes]
    customer = customer_angles[pairs[:, 0]][:, axes, feature_index]
    tutor = tutor_angles[pairs[:, 1]][:, axes, feature_index]
    difference = customer - tutor
    return np.sqrt(np.mean(difference * difference, axis=1))


def _timestamp_range(values: np.ndarray) -> Dict[str, Any]:
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return {"start_usec": None, "end_usec": None, "duration_sec": None}
    return {
        "start_usec": int(finite[0]),
        "end_usec": int(finite[-1]),
        "duration_sec": float((finite[-1] - finite[0]) / 1_000_000.0),
    }


def create_assessment_report(
    customer_angles: np.ndarray,
    tutor_angles: np.ndarray,
    path: Sequence[Tuple[int, int]],
    profile: ExerciseProfile,
    customer_motion,
    tutor_motion,
    customer_quality: Dict[str, Any],
    tutor_quality: Dict[str, Any],
) -> Dict[str, Any]:
    if not path:
        raise ValueError("Cannot score an empty DTW path")
    feature_reports = []
    feature_errors = []
    raw_feature_scores = []
    weights = np.asarray([feature.weight for feature in profile.features], dtype=np.float64)
    for index, feature in enumerate(profile.features):
        errors = _aligned_feature_errors(
            customer_angles, tutor_angles, path, feature, index
        )
        feature_errors.append(errors)
        rms = float(np.sqrt(np.mean(errors * errors)))
        score = score_errors(
            errors,
            feature.good_error_deg,
            feature.bad_error_deg,
            profile.outlier_penalty,
        )
        raw_feature_scores.append(score)
        feature_reports.append(
            {
                "id": feature.feature_id,
                "label": feature.label,
                "joints": list(feature.joints),
                "axes": list(feature.axes),
                "weight": feature.weight,
                "score": round(score, 2),
                "rms_error_deg": round(rms, 2),
                "p95_error_deg": round(float(np.percentile(errors, 95)), 2),
                "feedback": feature.feedback
                if score < profile.feedback_below_score
                else None,
            }
        )

    overall_score = float(np.average(np.asarray(raw_feature_scores), weights=weights))
    errors_by_pair = np.stack(feature_errors, axis=1)
    combined_error = np.sqrt(np.average(errors_by_pair * errors_by_pair, axis=1, weights=weights))
    window = min(profile.worst_window_frames, len(combined_error))
    window_errors = np.convolve(combined_error, np.ones(window) / window, mode="valid")
    worst_start = int(np.argmax(window_errors))
    worst_end = worst_start + window - 1
    worst_pair = worst_start + int(np.argmax(combined_error[worst_start : worst_end + 1]))
    customer_index, tutor_index = path[worst_pair]
    improvement = [
        {"feature_id": report["id"], "label": report["label"], "message": report["feedback"]}
        for report in sorted(feature_reports, key=lambda item: item["score"])
        if report["feedback"] is not None
    ][:3]

    return {
        "format": REPORT_FORMAT,
        "schema_version": REPORT_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "profile": {
            "id": profile.profile_id,
            "display_name": profile.display_name,
            "source_file": Path(profile.source_path).name,
        },
        "overall_score": round(overall_score, 2),
        "feature_scores": feature_reports,
        "improvements": improvement,
        "worst_segment": {
            "path_start": worst_start,
            "path_end": worst_end,
            "mean_error_deg": round(float(window_errors[worst_start]), 2),
            "customer_sequence_index": int(customer_index),
            "tutor_sequence_index": int(tutor_index),
            "customer_frame_index": int(customer_motion.frame_indices[customer_index]),
            "tutor_frame_index": int(tutor_motion.frame_indices[tutor_index]),
        },
        "alignment": {
            "path_length": len(path),
            "customer_frame_count": int(customer_angles.shape[0]),
            "tutor_frame_count": int(tutor_angles.shape[0]),
        },
        "timing": {
            "customer": _timestamp_range(customer_motion.timestamps_usec),
            "tutor": _timestamp_range(tutor_motion.timestamps_usec),
        },
        "quality": {"customer": customer_quality, "tutor": tutor_quality},
    }
