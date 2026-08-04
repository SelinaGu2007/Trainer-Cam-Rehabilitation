"""Loading and validation for configurable TrainerCam exercise profiles."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


PROFILE_FORMAT = "trainercam.exercise-profile"
PROFILE_SCHEMA_VERSION = 1
SUPPORTED_AXES = ("x", "y", "z")


class ExerciseProfileError(ValueError):
    pass


@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    label: str
    joints: Tuple[int, int]
    axes: Tuple[str, ...]
    weight: float
    good_error_deg: float
    bad_error_deg: float
    feedback: str


@dataclass(frozen=True)
class ExerciseProfile:
    profile_id: str
    display_name: str
    description: str
    features: Tuple[FeatureSpec, ...]
    worst_window_frames: int
    outlier_penalty: float
    feedback_below_score: float
    source_path: str

    @property
    def feature_pairs(self) -> List[Tuple[int, int]]:
        return [feature.joints for feature in self.features]

    @property
    def required_joints(self) -> set[int]:
        return {joint for feature in self.features for joint in feature.joints}


def _default_profile_candidates() -> Sequence[Path]:
    candidates: List[Path] = []
    configured = os.environ.get("TRAINER_CAM_EXERCISE_PROFILE")
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path.cwd() / "config" / "exercises" / "arm_raise.json")
    candidates.append(Path(__file__).resolve().parents[1] / "config" / "exercises" / "arm_raise.json")
    return candidates


def resolve_profile_path(value: str | None = None) -> Path:
    if value:
        supplied = Path(value)
        candidates = [supplied]
        if supplied.suffix.lower() != ".json":
            candidates.extend(
                (
                    Path.cwd() / "config" / "exercises" / f"{value}.json",
                    Path(__file__).resolve().parents[1]
                    / "config"
                    / "exercises"
                    / f"{value}.json",
                )
            )
    else:
        candidates = list(_default_profile_candidates())
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Exercise profile was not found. Checked: {searched}")


def _positive_number(raw: Dict[str, Any], key: str, feature_id: str) -> float:
    try:
        value = float(raw[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ExerciseProfileError(f"Feature {feature_id!r} requires numeric {key}") from exc
    if value <= 0:
        raise ExerciseProfileError(f"Feature {feature_id!r} requires {key} > 0")
    return value


def parse_profile(raw: Dict[str, Any], source_path: str = "<memory>") -> ExerciseProfile:
    if raw.get("format") != PROFILE_FORMAT:
        raise ExerciseProfileError(f"Unsupported profile format: {raw.get('format')!r}")
    if raw.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ExerciseProfileError(
            f"Unsupported profile schema version: {raw.get('schema_version')!r}"
        )
    profile_id = str(raw.get("id", "")).strip()
    if not profile_id:
        raise ExerciseProfileError("Profile id cannot be empty")
    feature_values = raw.get("features")
    if not isinstance(feature_values, list) or not feature_values:
        raise ExerciseProfileError("Profile must define at least one feature")

    features: List[FeatureSpec] = []
    identifiers = set()
    for value in feature_values:
        feature_id = str(value.get("id", "")).strip()
        if not feature_id or feature_id in identifiers:
            raise ExerciseProfileError(f"Feature id is empty or duplicated: {feature_id!r}")
        identifiers.add(feature_id)
        joints = value.get("joints")
        if (
            not isinstance(joints, list)
            or len(joints) != 2
            or any(not isinstance(joint, int) or not 0 <= joint < 32 for joint in joints)
            or joints[0] == joints[1]
        ):
            raise ExerciseProfileError(
                f"Feature {feature_id!r} must contain two different joint indices in [0, 31]"
            )
        axes = tuple(str(axis).lower() for axis in value.get("axes", SUPPORTED_AXES))
        if not axes or len(set(axes)) != len(axes) or any(axis not in SUPPORTED_AXES for axis in axes):
            raise ExerciseProfileError(f"Feature {feature_id!r} has invalid axes")
        good = _positive_number(value, "good_error_deg", feature_id)
        bad = _positive_number(value, "bad_error_deg", feature_id)
        if good >= bad:
            raise ExerciseProfileError(
                f"Feature {feature_id!r} requires good_error_deg < bad_error_deg"
            )
        features.append(
            FeatureSpec(
                feature_id=feature_id,
                label=str(value.get("label", feature_id)),
                joints=(joints[0], joints[1]),
                axes=axes,
                weight=_positive_number(value, "weight", feature_id),
                good_error_deg=good,
                bad_error_deg=bad,
                feedback=str(value.get("feedback", "Review this body segment.")),
            )
        )

    scoring = raw.get("scoring", {})
    worst_window = int(scoring.get("worst_window_frames", 10))
    outlier_penalty = float(scoring.get("outlier_penalty", 15.0))
    feedback_below_score = float(scoring.get("feedback_below_score", 80.0))
    if worst_window < 1:
        raise ExerciseProfileError("worst_window_frames must be at least 1")
    if not 0.0 <= outlier_penalty <= 100.0:
        raise ExerciseProfileError("outlier_penalty must be between 0 and 100")
    if not 0.0 <= feedback_below_score <= 100.0:
        raise ExerciseProfileError("feedback_below_score must be between 0 and 100")
    return ExerciseProfile(
        profile_id=profile_id,
        display_name=str(raw.get("display_name", profile_id)),
        description=str(raw.get("description", "")),
        features=tuple(features),
        worst_window_frames=worst_window,
        outlier_penalty=outlier_penalty,
        feedback_below_score=feedback_below_score,
        source_path=source_path,
    )


def load_profile(value: str | None = None) -> ExerciseProfile:
    path = resolve_profile_path(value)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExerciseProfileError(f"Invalid profile JSON: {path}") from exc
    return parse_profile(raw, source_path=str(path))
