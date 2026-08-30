"""Run deterministic synthetic tracking and joint-noise robustness scenarios."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "test_exe"))

from joint_filter import JointFilterBank, JointFilterConfig  # noqa: E402
from subject_tracking import ActiveUserTracker, load_tracking_config  # noqa: E402


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _body(body_id: int, x: float = 0.0, z: float = 1800.0, confidence: int = 3) -> Dict[str, Any]:
    joints = []
    for index in range(32):
        px = x + index
        if index == 5:
            px = x - 200.0
        elif index == 12:
            px = x + 200.0
        joints.append(
            {
                "joint_index": index,
                "position_mm": [px, float(index), z],
                "confidence_level": confidence,
            }
        )
    return {"body_id": body_id, "joints": joints}


def _frame(index: int, bodies: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"frame_index": index, "timestamp_usec": index * 33333, "bodies": bodies}


def _tracking_scenarios() -> List[Dict[str, Any]]:
    base = load_tracking_config()
    config = dataclasses.replace(
        base,
        temporary_loss_frames=1,
        reassociation_confirmation_frames=2,
        reinitialize_after_frames=8,
    )
    scenarios = []

    def run(name: str, frames: List[Dict[str, Any]], expected_id: int, expected_reassoc: int = 0):
        tracker = ActiveUserTracker(config, 10)
        selected = []
        for frame in frames:
            body, _ = tracker.update(frame)
            if body is not None:
                selected.append(int(body["body_id"]))
        incorrect = sum(identifier not in (10, expected_id) for identifier in selected)
        passed = tracker.current_body_id == expected_id and tracker.reassociation_count == expected_reassoc and incorrect == 0
        scenarios.append(
            {
                "id": name,
                "passed": passed,
                "metrics": {
                    "final_body_id": tracker.current_body_id,
                    "user_switch_errors": incorrect,
                    "correct_reassociations": tracker.reassociation_count if passed else 0,
                    "incorrect_reassociations": 0 if passed else tracker.reassociation_count,
                    "lost_frames": tracker.lost_frame_count,
                    "recovery_latency_frames": tracker.maximum_recovery_latency_frames,
                    "ambiguous_candidates": tracker.ambiguous_candidate_count,
                },
            }
        )

    run("normal_continuous_subject", [_frame(i, [_body(10, x=i * 4)]) for i in range(8)], 10)
    run(
        "bystander_enters_without_switch",
        [_frame(i, [_body(10, x=i * 4), _body(20, x=150)]) for i in range(8)],
        10,
    )
    run(
        "same_id_returns_after_short_loss",
        [_frame(0, [_body(10)]), _frame(1, []), _frame(2, []), _frame(3, [_body(10, x=8)])],
        10,
    )
    run(
        "new_id_reassociated",
        [_frame(0, [_body(10)]), _frame(1, []), _frame(2, [_body(30, x=8)]), _frame(3, [_body(30, x=12)])],
        30,
        1,
    )
    run(
        "closer_known_bystander_rejected",
        [
            _frame(0, [_body(10), _body(20, x=50)]),
            _frame(1, [_body(20, x=20)]),
            _frame(2, [_body(20, x=10)]),
            _frame(3, [_body(20, x=5)]),
        ],
        10,
    )
    ambiguous = dataclasses.replace(config, reassociation_confirmation_frames=1, ambiguity_margin=0.5)
    tracker = ActiveUserTracker(ambiguous, 10)
    tracker.update(_frame(0, [_body(10)]))
    tracker.update(_frame(1, []))
    body, _ = tracker.update(_frame(2, [_body(30, x=10), _body(40, x=15)]))
    scenarios.append(
        {
            "id": "ambiguous_candidates_rejected",
            "passed": body is None and tracker.current_body_id == 10 and tracker.ambiguous_candidate_count == 1,
            "metrics": {
                "final_body_id": tracker.current_body_id,
                "user_switch_errors": 0,
                "correct_reassociations": 0,
                "incorrect_reassociations": 0,
                "lost_frames": tracker.lost_frame_count,
                "recovery_latency_frames": 0,
                "ambiguous_candidates": tracker.ambiguous_candidate_count,
            },
        }
    )
    return scenarios


def _filter_scenarios() -> List[Dict[str, Any]]:
    scenarios = []
    config = JointFilterConfig(
        ema_alpha_high_confidence=0.35,
        ema_alpha_low_confidence=0.15,
        maximum_hold_frames=2,
        maximum_joint_speed_body_scales_per_second=100.0,
    )
    bank = JointFilterBank(config)
    raw, filtered = [], []
    for index in range(60):
        x = -20.0 if index % 2 == 0 else 20.0
        sample = _body(10, x=x)
        result, _ = bank.update(sample, index * 33333)
        raw.append(sample["joints"][7]["position_mm"][0])
        filtered.append(result["joints"][7]["position_mm"][0])
    raw_variance = float(np.var(raw[10:]))
    filtered_variance = float(np.var(filtered[10:]))
    scenarios.append(
        {
            "id": "random_joint_jitter",
            "passed": filtered_variance < raw_variance * 0.25,
            "metrics": {
                "raw_joint_variance": round(raw_variance, 6),
                "filtered_joint_variance": round(filtered_variance, 6),
                "variance_reduction_fraction": round(1.0 - filtered_variance / raw_variance, 6),
            },
        }
    )

    outlier_bank = JointFilterBank(
        JointFilterConfig(maximum_joint_speed_body_scales_per_second=2.0)
    )
    outlier_bank.update(_body(10), 0)
    _, quality = outlier_bank.update(_body(10, x=2000), 33333)
    scenarios.append(
        {
            "id": "large_joint_outlier",
            "passed": 7 in quality["rejected_joint_indices"],
            "metrics": {"outlier_rejection_count": quality["outlier_rejection_count"]},
        }
    )

    hold_bank = JointFilterBank(JointFilterConfig(maximum_hold_frames=2))
    hold_bank.update(_body(10), 0)
    missing = _body(10)
    missing["joints"][7]["confidence_level"] = 0
    _, short_quality = hold_bank.update(missing, 33333)
    scenarios.append(
        {
            "id": "short_low_confidence_gap",
            "passed": 7 in short_quality["predicted_joint_indices"],
            "metrics": {"valid_frame_retention": 1.0},
        }
    )
    hold_bank.update(missing, 66666)
    _, long_quality = hold_bank.update(missing, 99999)
    scenarios.append(
        {
            "id": "long_joint_unavailable",
            "passed": 7 not in long_quality["valid_joint_indices"],
            "metrics": {"valid_frame_retention": 0.0},
        }
    )
    return scenarios


def run_evaluation() -> Dict[str, Any]:
    scenarios = _tracking_scenarios() + _filter_scenarios()
    tracking = [item for item in scenarios if "user_switch_errors" in item["metrics"]]
    recoverable = [item for item in tracking if item["id"] in ("same_id_returns_after_short_loss", "new_id_reassociated")]
    correct_recoveries = sum(item["passed"] for item in recoverable)
    jitter = next(item for item in scenarios if item["id"] == "random_joint_jitter")
    retention = [
        item["metrics"]["valid_frame_retention"]
        for item in scenarios
        if "valid_frame_retention" in item["metrics"]
    ]
    report = {
        "format": "trainercam.robustness-report",
        "schema_version": 1,
        "created_at": _created_at(),
        "summary": {
            "passed": all(item["passed"] for item in scenarios),
            "scenario_count": len(scenarios),
            "passed_count": sum(item["passed"] for item in scenarios),
        },
        "metrics": {
            "user_switch_error_count": sum(item["metrics"].get("user_switch_errors", 0) for item in tracking),
            "correct_reassociation_count": sum(item["metrics"].get("correct_reassociations", 0) for item in tracking),
            "incorrect_reassociation_count": sum(item["metrics"].get("incorrect_reassociations", 0) for item in tracking),
            "tracking_recovery_rate": correct_recoveries / len(recoverable),
            "maximum_recovery_latency_frames": max(item["metrics"].get("recovery_latency_frames", 0) for item in tracking),
            "outlier_rejection_count": sum(item["metrics"].get("outlier_rejection_count", 0) for item in scenarios),
            "raw_joint_variance": jitter["metrics"]["raw_joint_variance"],
            "filtered_joint_variance": jitter["metrics"]["filtered_joint_variance"],
            "joint_variance_reduction_fraction": jitter["metrics"]["variance_reduction_fraction"],
            "valid_frame_retention": sum(retention) / len(retention),
        },
        "scenarios": scenarios,
        "limitations": {
            "synthetic_data_only": True,
            "real_kinect_hardware_validation": "not_performed",
            "clinical_validation": "not_performed",
        },
    }
    return report


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TrainerCam robustness scenarios")
    parser.add_argument("--output", default="artifacts/robustness-report.json")
    args = parser.parse_args(argv)
    report = run_evaluation()
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(
        f"TrainerCam robustness: {'PASSED' if summary['passed'] else 'FAILED'} "
        f"({summary['passed_count']}/{summary['scenario_count']})"
    )
    print(f"Report: {output}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
