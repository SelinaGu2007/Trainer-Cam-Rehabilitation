"""Stateful confidence-aware filtering for live Azure Kinect joints."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np


@dataclass(frozen=True)
class JointFilterConfig:
    ema_alpha_high_confidence: float = 0.65
    ema_alpha_low_confidence: float = 0.25
    maximum_hold_frames: int = 3
    maximum_joint_speed_body_scales_per_second: float = 8.0
    recovery_blend_frames: int = 3


@dataclass
class _JointState:
    position: np.ndarray
    velocity: np.ndarray
    timestamp_usec: int | None
    missing_frames: int = 0
    recovery_frames: int = 0


class JointFilterBank:
    """One conservative temporal filter per joint in raw millimetre coordinates."""

    def __init__(self, config: JointFilterConfig, joint_count: int = 32) -> None:
        if not 0 < config.ema_alpha_low_confidence <= config.ema_alpha_high_confidence <= 1:
            raise ValueError("joint filter EMA alpha values must satisfy 0 < low <= high <= 1")
        if config.maximum_hold_frames < 0 or config.recovery_blend_frames < 0:
            raise ValueError("joint filter frame thresholds cannot be negative")
        if config.maximum_joint_speed_body_scales_per_second <= 0:
            raise ValueError("maximum joint speed must be positive")
        self.config = config
        self.joint_count = joint_count
        self.states: List[_JointState | None] = [None] * joint_count
        self.body_scale_mm = 400.0
        self.outlier_rejection_count = 0

    @staticmethod
    def _position(joint: Dict[str, Any]) -> np.ndarray | None:
        raw = joint.get("position_mm", joint.get("position"))
        if not isinstance(raw, list) or len(raw) != 3:
            return None
        value = np.asarray(raw, dtype=np.float64)
        if not np.all(np.isfinite(value)) or np.linalg.norm(value) <= 1e-8:
            return None
        return value

    def _update_scale(self, joints: Dict[int, Dict[str, Any]]) -> None:
        if 5 not in joints or 12 not in joints:
            return
        left, right = self._position(joints[5]), self._position(joints[12])
        if left is None or right is None:
            return
        scale = float(np.linalg.norm(right - left))
        if 100.0 <= scale <= 1000.0:
            self.body_scale_mm = 0.9 * self.body_scale_mm + 0.1 * scale

    def update(
        self, body: Dict[str, Any], timestamp_usec: int | None = None
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        indexed = {
            int(joint.get("joint_index", joint.get("index", fallback))): joint
            for fallback, joint in enumerate(body.get("joints", []))
        }
        self._update_scale(indexed)
        output = []
        valid_indices, predicted_indices, rejected_indices = [], [], []
        for index in range(self.joint_count):
            source = indexed.get(index, {"joint_index": index, "confidence_level": 0})
            confidence = int(source.get("confidence_level", 0))
            observation = self._position(source) if confidence > 0 else None
            state = self.states[index]
            rejected = False
            if observation is not None and state is not None:
                dt = 1.0 / 30.0
                if timestamp_usec is not None and state.timestamp_usec is not None:
                    dt = max((timestamp_usec - state.timestamp_usec) / 1_000_000.0, 1.0 / 120.0)
                speed = float(np.linalg.norm(observation - state.position)) / dt
                maximum = self.config.maximum_joint_speed_body_scales_per_second * self.body_scale_mm
                if speed > maximum:
                    observation = None
                    rejected = True
                    self.outlier_rejection_count += 1
                    rejected_indices.append(index)

            predicted = False
            if observation is None:
                if state is not None:
                    state.missing_frames += 1
                    if state.missing_frames <= self.config.maximum_hold_frames:
                        dt = 1.0 / 30.0
                        position = state.position + state.velocity * dt
                        state.position = position
                        state.timestamp_usec = timestamp_usec
                        predicted = True
                    else:
                        position = np.zeros(3, dtype=np.float64)
                else:
                    position = np.zeros(3, dtype=np.float64)
            elif state is None:
                position = observation
                self.states[index] = _JointState(
                    position.copy(), np.zeros(3, dtype=np.float64), timestamp_usec
                )
                state = self.states[index]
            else:
                was_missing = state.missing_frames > 0
                if was_missing:
                    state.recovery_frames = self.config.recovery_blend_frames
                fraction = max(0.0, min(confidence / 3.0, 1.0))
                alpha = self.config.ema_alpha_low_confidence + fraction * (
                    self.config.ema_alpha_high_confidence
                    - self.config.ema_alpha_low_confidence
                )
                if state.recovery_frames > 0:
                    alpha = min(alpha, 1.0 / (state.recovery_frames + 1.0))
                    state.recovery_frames -= 1
                dt = 1.0 / 30.0
                if timestamp_usec is not None and state.timestamp_usec is not None:
                    dt = max((timestamp_usec - state.timestamp_usec) / 1_000_000.0, 1.0 / 120.0)
                previous = state.position.copy()
                position = (1.0 - alpha) * state.position + alpha * observation
                state.velocity = 0.7 * state.velocity + 0.3 * ((position - previous) / dt)
                state.position = position
                state.timestamp_usec = timestamp_usec
                state.missing_frames = 0

            current = self.states[index]
            usable = observation is not None or predicted
            if current is not None and (observation is not None or predicted):
                current.position = position.copy()
                current.timestamp_usec = timestamp_usec
            if usable:
                valid_indices.append(index)
            if predicted:
                predicted_indices.append(index)
            joint = dict(source)
            joint["joint_index"] = index
            joint["position_mm"] = position.tolist()
            joint["filter_valid"] = usable
            joint["filter_predicted"] = predicted
            joint["filter_rejected"] = rejected
            if predicted:
                joint["confidence_level"] = max(1, confidence)
            output.append(joint)

        filtered = dict(body)
        filtered["joints"] = output
        quality = {
            "valid_joint_indices": valid_indices,
            "predicted_joint_indices": predicted_indices,
            "rejected_joint_indices": rejected_indices,
            "outlier_rejection_count": self.outlier_rejection_count,
            "body_scale_mm": round(self.body_scale_mm, 3),
        }
        return filtered, quality
