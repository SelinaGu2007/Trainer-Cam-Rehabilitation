"""Create a portable, user-facing timeline for post-session motion review."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

import numpy as np

from assessment import AXIS_INDEX, REPORT_FORMAT
from exercise_profile import ExerciseProfile


REVIEW_FORMAT = "trainercam.session-review"
REVIEW_SCHEMA_VERSION = 1


def _timestamp(value: float) -> int | None:
    return int(value) if np.isfinite(value) else None


def _image_name(value: Any) -> str | None:
    if value is None:
        return None
    name = Path(str(value).replace("\\", "/")).name
    return name or None


def _feature_error(
    customer_angles: np.ndarray,
    tutor_angles: np.ndarray,
    customer_index: int,
    tutor_index: int,
    feature_index: int,
    axes: Sequence[str],
) -> float:
    axis_indices = [AXIS_INDEX[axis] for axis in axes]
    difference = (
        customer_angles[customer_index, axis_indices, feature_index]
        - tutor_angles[tutor_index, axis_indices, feature_index]
    )
    return float(np.sqrt(np.mean(difference * difference)))


def create_session_review(
    customer_angles: np.ndarray,
    tutor_angles: np.ndarray,
    path: Sequence[Tuple[int, int]],
    profile: ExerciseProfile,
    customer_motion,
    tutor_motion,
    assessment_report: Dict[str, Any],
) -> Dict[str, Any]:
    if assessment_report.get("format") != REPORT_FORMAT:
        raise ValueError("Session review requires a supported assessment report")
    if not path:
        raise ValueError("Session review requires a non-empty alignment path")

    weights = np.asarray([feature.weight for feature in profile.features], dtype=np.float64)
    items = []
    for alignment_index, (customer_index, tutor_index) in enumerate(path):
        if not (0 <= customer_index < len(customer_angles)):
            raise ValueError("Alignment contains an invalid customer frame index")
        if not (0 <= tutor_index < len(tutor_angles)):
            raise ValueError("Alignment contains an invalid tutor frame index")

        errors = np.asarray(
            [
                _feature_error(
                    customer_angles,
                    tutor_angles,
                    customer_index,
                    tutor_index,
                    feature_index,
                    feature.axes,
                )
                for feature_index, feature in enumerate(profile.features)
            ],
            dtype=np.float64,
        )
        normalised = np.asarray(
            [
                (error - feature.good_error_deg)
                / max(feature.bad_error_deg - feature.good_error_deg, 1e-9)
                for error, feature in zip(errors, profile.features)
            ]
        )
        issue_index = int(np.argmax(normalised))
        issue_feature = profile.features[issue_index]
        issue_error = float(errors[issue_index])
        severity = (
            "good"
            if issue_error <= issue_feature.good_error_deg
            else "adjust"
            if issue_error <= issue_feature.bad_error_deg
            else "review"
        )
        combined_error = float(np.sqrt(np.average(errors * errors, weights=weights)))
        items.append(
            {
                "alignment_index": alignment_index,
                "customer": {
                    "sequence_index": int(customer_index),
                    "frame_index": int(customer_motion.frame_indices[customer_index]),
                    "timestamp_usec": _timestamp(
                        customer_motion.timestamps_usec[customer_index]
                    ),
                    "image": _image_name(customer_motion.images[customer_index]),
                },
                "tutor": {
                    "sequence_index": int(tutor_index),
                    "frame_index": int(tutor_motion.frame_indices[tutor_index]),
                    "timestamp_usec": _timestamp(tutor_motion.timestamps_usec[tutor_index]),
                    "image": _image_name(tutor_motion.images[tutor_index]),
                },
                "difference_deg": round(combined_error, 2),
                "issue": {
                    "feature_id": issue_feature.feature_id,
                    "label": issue_feature.label,
                    "joints": list(issue_feature.joints),
                    "error_deg": round(issue_error, 2),
                    "severity": severity,
                    "message": issue_feature.feedback if severity != "good" else None,
                },
            }
        )

    worst = assessment_report["worst_segment"]
    focus_index = next(
        (
            index
            for index, pair in enumerate(path)
            if int(pair[0]) == int(worst["customer_sequence_index"])
            and int(pair[1]) == int(worst["tutor_sequence_index"])
        ),
        int(worst["path_start"]),
    )
    worst_segment = {
        "start_index": int(worst["path_start"]),
        "end_index": int(worst["path_end"]),
        "focus_index": int(focus_index),
        "mean_error_deg": float(worst["mean_error_deg"]),
    }
    for index in range(worst_segment["start_index"], worst_segment["end_index"] + 1):
        if 0 <= index < len(items):
            items[index]["in_worst_segment"] = True

    return {
        "format": REVIEW_FORMAT,
        "schema_version": REVIEW_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "profile": {
            "id": profile.profile_id,
            "display_name": profile.display_name,
        },
        "item_count": len(items),
        "worst_segment": worst_segment,
        "items": items,
        "disclaimer": (
            "Frame differences are engineering feedback for exercise review, "
            "not a medical diagnosis."
        ),
    }
