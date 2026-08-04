"""Confidence-aware preparation of raw skeleton tracks for motion comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np


PELVIS = 0
SPINE_CHEST = 2
SHOULDER_LEFT = 5
SHOULDER_RIGHT = 12
HIP_LEFT = 18
HIP_RIGHT = 22


@dataclass
class PreparedMotion:
    """A single body track in a body-relative, dimensionless coordinate system."""

    positions: np.ndarray
    confidence: np.ndarray
    valid: np.ndarray
    interpolated: np.ndarray
    frame_indices: np.ndarray
    timestamps_usec: np.ndarray
    images: List[Any]
    body_id: int
    scale_mm: float
    confidence_metadata_available: bool

    def coverage(self, joint_indices: Iterable[int] | None = None) -> float:
        mask = self.valid
        if joint_indices is not None:
            indices = sorted(set(int(index) for index in joint_indices))
            mask = mask[:, indices]
        return float(np.mean(mask)) if mask.size else 0.0

    def quality_summary(self, required_joints: Iterable[int] | None = None) -> Dict[str, Any]:
        return {
            "frame_count": int(self.positions.shape[0]),
            "body_id": self.body_id,
            "scale_mm": self.scale_mm,
            "joint_coverage": self.coverage(),
            "required_joint_coverage": self.coverage(required_joints),
            "interpolated_ratio": float(np.mean(self.interpolated))
            if self.interpolated.size
            else 0.0,
            "confidence_metadata_available": self.confidence_metadata_available,
        }


def _safe_unit(vector: np.ndarray) -> np.ndarray | None:
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm < 1e-8:
        return None
    return vector / norm


def _extract_arrays(bodies: Sequence[Dict[str, Any]], joint_count: int):
    frame_count = len(bodies)
    positions = np.zeros((frame_count, joint_count, 3), dtype=np.float64)
    confidence = np.zeros((frame_count, joint_count), dtype=np.int8)
    frame_indices = np.zeros(frame_count, dtype=np.int64)
    timestamps = np.full(frame_count, np.nan, dtype=np.float64)
    images: List[Any] = []

    for frame, body in enumerate(bodies):
        frame_indices[frame] = int(body.get("frame_index", frame))
        timestamp = body.get("timestamp_usec")
        if timestamp is not None:
            timestamps[frame] = float(timestamp)
        images.append(body.get("image"))
        for fallback_index, joint in enumerate(body.get("joints", [])):
            index = int(joint.get("joint_index", joint.get("index", fallback_index)))
            if not 0 <= index < joint_count:
                continue
            position = joint.get("position_mm", joint.get("position", [0.0, 0.0, 0.0]))
            if len(position) == 3:
                positions[frame, index] = np.asarray(position, dtype=np.float64)
            confidence[frame, index] = int(joint.get("confidence_level", 0))

    body_id = int(bodies[0].get("body_id", bodies[0].get("id", 0))) if bodies else 0
    return positions, confidence, frame_indices, timestamps, images, body_id


def _interpolate_short_gaps(
    positions: np.ndarray, observed: np.ndarray, max_gap: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    repaired = positions.copy()
    valid = observed.copy()
    interpolated = np.zeros_like(observed, dtype=bool)
    if max_gap <= 0:
        repaired[~valid] = 0.0
        return repaired, valid, interpolated

    for joint in range(positions.shape[1]):
        known = np.flatnonzero(observed[:, joint])
        for left, right in zip(known[:-1], known[1:]):
            gap = int(right - left - 1)
            if gap <= 0 or gap > max_gap:
                continue
            for frame in range(left + 1, right):
                weight = (frame - left) / (right - left)
                repaired[frame, joint] = (
                    positions[left, joint] * (1.0 - weight)
                    + positions[right, joint] * weight
                )
                valid[frame, joint] = True
                interpolated[frame, joint] = True
    repaired[~valid] = 0.0
    return repaired, valid, interpolated


def _body_scale(positions: np.ndarray, valid: np.ndarray) -> float:
    candidates: List[float] = []
    for frame in range(positions.shape[0]):
        if valid[frame, SHOULDER_LEFT] and valid[frame, SHOULDER_RIGHT]:
            candidates.append(
                float(
                    np.linalg.norm(
                        positions[frame, SHOULDER_RIGHT] - positions[frame, SHOULDER_LEFT]
                    )
                )
            )
    candidates = [value for value in candidates if np.isfinite(value) and value > 1e-6]
    if not candidates:
        for frame in range(positions.shape[0]):
            if valid[frame, HIP_LEFT] and valid[frame, HIP_RIGHT]:
                width = float(
                    np.linalg.norm(positions[frame, HIP_RIGHT] - positions[frame, HIP_LEFT])
                )
                if np.isfinite(width) and width > 1e-6:
                    candidates.append(width * 2.0)
    return float(np.median(candidates)) if candidates else 1.0


def _frame_origin(positions: np.ndarray, valid: np.ndarray, frame: int) -> np.ndarray:
    if valid[frame, PELVIS]:
        return positions[frame, PELVIS]
    if valid[frame, HIP_LEFT] and valid[frame, HIP_RIGHT]:
        return (positions[frame, HIP_LEFT] + positions[frame, HIP_RIGHT]) * 0.5
    if valid[frame, SHOULDER_LEFT] and valid[frame, SHOULDER_RIGHT]:
        return (positions[frame, SHOULDER_LEFT] + positions[frame, SHOULDER_RIGHT]) * 0.5
    available = positions[frame, valid[frame]]
    return np.mean(available, axis=0) if available.size else np.zeros(3, dtype=np.float64)


def _frame_basis(
    positions: np.ndarray, valid: np.ndarray, frame: int, previous: np.ndarray
) -> np.ndarray:
    torso_joints = (SHOULDER_LEFT, SHOULDER_RIGHT, HIP_LEFT, HIP_RIGHT)
    if not all(valid[frame, joint] for joint in torso_joints):
        return previous
    shoulder_mid = (positions[frame, SHOULDER_LEFT] + positions[frame, SHOULDER_RIGHT]) * 0.5
    hip_mid = (positions[frame, HIP_LEFT] + positions[frame, HIP_RIGHT]) * 0.5
    x_axis = _safe_unit(positions[frame, SHOULDER_RIGHT] - positions[frame, SHOULDER_LEFT])
    down_hint = _safe_unit(hip_mid - shoulder_mid)
    if x_axis is None or down_hint is None:
        return previous
    z_axis = _safe_unit(np.cross(x_axis, down_hint))
    if z_axis is None:
        return previous
    y_axis = _safe_unit(np.cross(z_axis, x_axis))
    if y_axis is None:
        return previous
    return np.column_stack((x_axis, y_axis, z_axis))


def _normalise_body_coordinates(
    positions: np.ndarray, valid: np.ndarray, scale_mm: float
) -> np.ndarray:
    normalised = np.zeros_like(positions, dtype=np.float64)
    previous_basis = np.eye(3, dtype=np.float64)
    for frame in range(positions.shape[0]):
        basis = _frame_basis(positions, valid, frame, previous_basis)
        previous_basis = basis
        origin = _frame_origin(positions, valid, frame)
        normalised[frame] = ((positions[frame] - origin) @ basis) / scale_mm
        normalised[frame, ~valid[frame]] = 0.0
    return normalised


def prepare_motion(
    bodies: Sequence[Dict[str, Any]],
    joint_count: int = 32,
    min_confidence: int = 1,
    max_interpolation_gap: int = 3,
    normalise: bool = True,
) -> PreparedMotion:
    if not bodies:
        raise ValueError("Cannot prepare an empty body track")
    if not 0 <= min_confidence <= 3:
        raise ValueError("min_confidence must be between 0 and 3")
    if max_interpolation_gap < 0:
        raise ValueError("max_interpolation_gap cannot be negative")

    positions, confidence, frame_indices, timestamps, images, body_id = _extract_arrays(
        bodies, joint_count
    )
    finite = np.all(np.isfinite(positions), axis=2)
    nonzero = np.linalg.norm(positions, axis=2) > 1e-8
    confidence_available = bool(np.any(confidence > 0))
    if confidence_available:
        observed = finite & nonzero & (confidence >= min_confidence)
    else:
        # Migrated legacy files did not record confidence. Their nonzero positions
        # remain usable instead of being discarded as confidence level zero.
        observed = finite & nonzero

    repaired, valid, interpolated = _interpolate_short_gaps(
        positions, observed, max_interpolation_gap
    )
    scale_mm = _body_scale(repaired, valid)
    prepared_positions = (
        _normalise_body_coordinates(repaired, valid, scale_mm) if normalise else repaired
    )
    return PreparedMotion(
        positions=prepared_positions,
        confidence=confidence,
        valid=valid,
        interpolated=interpolated,
        frame_indices=frame_indices,
        timestamps_usec=timestamps,
        images=images,
        body_id=body_id,
        scale_mm=scale_mm,
        confidence_metadata_available=confidence_available,
    )


def prepared_to_bodies(prepared: PreparedMotion) -> List[Dict[str, Any]]:
    """Adapt prepared arrays to the dictionaries used by the legacy angle code."""
    bodies: List[Dict[str, Any]] = []
    for frame in range(prepared.positions.shape[0]):
        timestamp = prepared.timestamps_usec[frame]
        bodies.append(
            {
                "id": prepared.body_id,
                "body_id": prepared.body_id,
                "frame_index": int(prepared.frame_indices[frame]),
                "timestamp_usec": None if np.isnan(timestamp) else int(timestamp),
                "image": prepared.images[frame],
                "joints": [
                    {
                        "index": joint,
                        "joint_index": joint,
                        "position": prepared.positions[frame, joint].tolist(),
                        "confidence_level": int(prepared.confidence[frame, joint]),
                        "valid": bool(prepared.valid[frame, joint]),
                        "interpolated": bool(prepared.interpolated[frame, joint]),
                    }
                    for joint in range(prepared.positions.shape[1])
                ],
            }
        )
    return bodies


def retain_usable_frames(
    prepared: PreparedMotion,
    required_joints: Iterable[int],
    minimum_fraction: float = 1.0,
) -> PreparedMotion:
    """Remove frames that remain too incomplete after short-gap interpolation."""
    if not 0.0 < minimum_fraction <= 1.0:
        raise ValueError("minimum_fraction must be in (0, 1]")
    indices = sorted(set(int(index) for index in required_joints))
    if not indices:
        return prepared
    usable = np.mean(prepared.valid[:, indices], axis=1) >= minimum_fraction
    if not np.any(usable):
        raise ValueError("No usable frames remain after joint quality filtering")
    return PreparedMotion(
        positions=prepared.positions[usable],
        confidence=prepared.confidence[usable],
        valid=prepared.valid[usable],
        interpolated=prepared.interpolated[usable],
        frame_indices=prepared.frame_indices[usable],
        timestamps_usec=prepared.timestamps_usec[usable],
        images=[image for image, keep in zip(prepared.images, usable) if keep],
        body_id=prepared.body_id,
        scale_mm=prepared.scale_mm,
        confidence_metadata_available=prepared.confidence_metadata_available,
    )
