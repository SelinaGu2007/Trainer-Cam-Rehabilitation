"""Versioned TrainerCam motion-session data loading, writing, and migration."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from subject_tracking import (
    SubjectTrackingConfig,
    load_tracking_config,
    select_subject_track,
)


FORMAT_NAME = "trainercam.motion-session"
SCHEMA_VERSION = 1
MANIFEST_NAME = "session.json"
FRAMES_NAME = "frames.jsonl"
LEGACY_NAME = "output2.txt"
JOINT_COUNT = 32

_BODY_PATTERN = re.compile(r"^Body ID:\s*(\d+)")
_FRAME_PATTERN = re.compile(
    r"^Frame Index:\s*(\d+)(?:\s*;\s*Timestamp \(usec\):\s*(\d+))?"
)
_JOINT_PATTERN = re.compile(r"^Joint\[(\d+)\]:")
_POSITION_PATTERN = re.compile(r"Position(?:\[[^\]]*\])?\s*\(([^)]*)\)")
_ORIENTATION_PATTERN = re.compile(r"Orientation\s*\(([^)]*)\)")
_CONFIDENCE_PATTERN = re.compile(r"Confidence Level\s*\((\d+)\)")


class MotionDataError(ValueError):
    """Raised when a motion session does not conform to the supported format."""


def _default_joint(index: int) -> Dict[str, Any]:
    return {
        "joint_index": index,
        "position_mm": [0.0, 0.0, 0.0],
        "orientation_wxyz": [1.0, 0.0, 0.0, 0.0],
        "confidence_level": 0,
    }


def _numbers(value: str, count: int, field: str) -> List[float]:
    try:
        result = [float(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise MotionDataError(f"Invalid {field}: {value}") from exc
    if len(result) != count or not all(math.isfinite(item) for item in result):
        raise MotionDataError(f"{field} must contain {count} finite numbers")
    return result


def _normalise_joint(joint: Dict[str, Any], fallback_index: int) -> Dict[str, Any]:
    index = int(joint.get("joint_index", joint.get("index", fallback_index)))
    position = joint.get("position_mm", joint.get("position", [0.0, 0.0, 0.0]))
    orientation = joint.get("orientation_wxyz", [1.0, 0.0, 0.0, 0.0])
    confidence = int(joint.get("confidence_level", 0))
    if len(position) != 3 or not all(math.isfinite(float(value)) for value in position):
        raise MotionDataError(f"Joint {index} has an invalid position_mm")
    if len(orientation) != 4 or not all(math.isfinite(float(value)) for value in orientation):
        raise MotionDataError(f"Joint {index} has an invalid orientation_wxyz")
    if not 0 <= confidence <= 3:
        raise MotionDataError(f"Joint {index} has an invalid confidence_level")
    return {
        "joint_index": index,
        "index": index,
        "position_mm": [float(value) for value in position],
        "position": [float(value) for value in position],
        "orientation_wxyz": [float(value) for value in orientation],
        "confidence_level": confidence,
    }


def _normalise_body(body: Dict[str, Any], joint_count: int = JOINT_COUNT) -> Dict[str, Any]:
    result = {"body_id": int(body.get("body_id", body.get("id", 0)))}
    result["id"] = result["body_id"]
    joints = [_default_joint(index) for index in range(joint_count)]
    for fallback_index, joint in enumerate(body.get("joints", [])):
        normalised = _normalise_joint(joint, fallback_index)
        index = normalised["joint_index"]
        if 0 <= index < joint_count:
            joints[index] = normalised
    result["joints"] = [_normalise_joint(joint, index) for index, joint in enumerate(joints)]
    return result


def load_manifest(session_folder: str | Path) -> Dict[str, Any]:
    path = Path(session_folder) / MANIFEST_NAME
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MotionDataError(f"Unable to read motion manifest: {path}") from exc
    if manifest.get("format") != FORMAT_NAME:
        raise MotionDataError(f"Unsupported motion format: {manifest.get('format')!r}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise MotionDataError(
            f"Unsupported schema version: {manifest.get('schema_version')!r}"
        )
    return manifest


def load_jsonl_frames(session_folder: str | Path) -> List[Dict[str, Any]]:
    folder = Path(session_folder)
    manifest = load_manifest(folder)
    relative_path = manifest.get("files", {}).get("frames", FRAMES_NAME)
    frames_path = folder / relative_path
    frames: List[Dict[str, Any]] = []
    previous_index = -1
    try:
        with frames_path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise MotionDataError(
                        f"Invalid JSON in {frames_path} at line {line_number}"
                    ) from exc
                index = int(raw.get("frame_index", -1))
                if index <= previous_index:
                    raise MotionDataError("frame_index values must be strictly increasing")
                timestamp = raw.get("timestamp_usec")
                if timestamp is not None and int(timestamp) < 0:
                    raise MotionDataError("timestamp_usec cannot be negative")
                frame = {
                    "frame_index": index,
                    "timestamp_usec": None if timestamp is None else int(timestamp),
                    "image": raw.get("image"),
                    "bodies": [_normalise_body(body) for body in raw.get("bodies", [])],
                }
                frames.append(frame)
                previous_index = index
    except OSError as exc:
        raise MotionDataError(f"Unable to read motion frames: {frames_path}") from exc
    return frames


def load_legacy_frames(path: str | Path, joint_count: int = JOINT_COUNT) -> List[Dict[str, Any]]:
    """Parse output2.txt, including optional frame markers written by the v1 recorder."""
    legacy_path = Path(path)
    try:
        lines = legacy_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as exc:
        raise MotionDataError(f"Unable to read legacy motion data: {legacy_path}") from exc

    frames: List[Dict[str, Any]] = []
    current_frame: Optional[Dict[str, Any]] = None
    current_body: Optional[Dict[str, Any]] = None
    has_frame_markers = False

    def flush_body() -> None:
        nonlocal current_body, current_frame
        if current_body is None:
            return
        if current_frame is None:
            current_frame = {
                "frame_index": len(frames),
                "timestamp_usec": None,
                "image": f"image_idx_{len(frames)}.jpg",
                "bodies": [],
            }
        current_frame["bodies"].append(_normalise_body(current_body, joint_count))
        current_body = None

    def flush_frame() -> None:
        nonlocal current_frame
        flush_body()
        if current_frame is not None and current_frame["bodies"]:
            frames.append(current_frame)
        current_frame = None

    for raw_line in lines:
        line = raw_line.strip()
        frame_match = _FRAME_PATTERN.match(line)
        if frame_match:
            has_frame_markers = True
            flush_frame()
            index = int(frame_match.group(1))
            current_frame = {
                "frame_index": index,
                "timestamp_usec": int(frame_match.group(2)) if frame_match.group(2) else None,
                "image": f"image_idx_{index}.jpg",
                "bodies": [],
            }
            continue

        body_match = _BODY_PATTERN.match(line)
        if body_match:
            if current_body is not None:
                flush_body()
                if not has_frame_markers:
                    flush_frame()
            current_body = {"body_id": int(body_match.group(1)), "joints": []}
            continue

        joint_match = _JOINT_PATTERN.match(line)
        if joint_match and current_body is not None:
            position_match = _POSITION_PATTERN.search(line)
            if not position_match:
                continue
            index = int(joint_match.group(1))
            orientation_match = _ORIENTATION_PATTERN.search(line)
            confidence_match = _CONFIDENCE_PATTERN.search(line)
            current_body["joints"].append(
                {
                    "joint_index": index,
                    "position_mm": _numbers(position_match.group(1), 3, "position"),
                    "orientation_wxyz": _numbers(orientation_match.group(1), 4, "orientation")
                    if orientation_match
                    else [1.0, 0.0, 0.0, 0.0],
                    "confidence_level": int(confidence_match.group(1)) if confidence_match else 0,
                }
            )

    flush_frame()
    return frames


def load_session_frames(session_folder: str | Path) -> List[Dict[str, Any]]:
    folder = Path(session_folder)
    if (folder / MANIFEST_NAME).is_file():
        return load_jsonl_frames(folder)
    legacy_path = folder / LEGACY_NAME
    if legacy_path.is_file():
        return load_legacy_frames(legacy_path)
    raise FileNotFoundError(f"No {MANIFEST_NAME} or {LEGACY_NAME} in {folder}")


def select_primary_bodies(
    frames: Sequence[Dict[str, Any]], body_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Return one stable body track, preferring the body present in most frames."""
    if body_id is None:
        appearances: Dict[int, int] = defaultdict(int)
        confidence: Dict[int, int] = defaultdict(int)
        for frame in frames:
            for body in frame.get("bodies", []):
                identifier = int(body["body_id"])
                appearances[identifier] += 1
                confidence[identifier] += sum(
                    int(joint.get("confidence_level", 0)) for joint in body.get("joints", [])
                )
        if not appearances:
            return []
        body_id = max(appearances, key=lambda item: (appearances[item], confidence[item], -item))

    selected: List[Dict[str, Any]] = []
    for frame in frames:
        match = next(
            (body for body in frame.get("bodies", []) if int(body["body_id"]) == body_id),
            None,
        )
        if match is not None:
            body = dict(match)
            body["frame_index"] = frame["frame_index"]
            body["timestamp_usec"] = frame.get("timestamp_usec")
            body["image"] = frame.get("image")
            selected.append(body)
    return selected


def load_session_bodies(
    session_folder: str | Path,
    body_id: Optional[int] = None,
    tracking_config: SubjectTrackingConfig | None = None,
) -> List[Dict[str, Any]]:
    bodies, _ = load_session_track(
        session_folder, body_id=body_id, tracking_config=tracking_config
    )
    return bodies


def load_session_track(
    session_folder: str | Path,
    body_id: Optional[int] = None,
    tracking_config: SubjectTrackingConfig | None = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load one locked subject and return its session-gating diagnostics."""
    config = tracking_config or load_tracking_config()
    return select_subject_track(load_session_frames(session_folder), config, body_id=body_id)


def create_manifest(
    source_type: str = "legacy-output2",
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source_metadata = dict(source) if source is not None else {"type": source_type}
    if not str(source_metadata.get("type", "")).strip():
        raise MotionDataError("Motion session source.type is required")
    return {
        "format": FORMAT_NAME,
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source_metadata,
        "coordinate_system": {
            "unit": "millimeter",
            "x_axis": "sensor-right",
            "y_axis": "sensor-down",
            "z_axis": "sensor-forward",
            "orientation_order": "wxyz",
        },
        "skeleton": {"model": "azure-kinect-body-tracking", "joint_count": JOINT_COUNT},
        "files": {
            "frames": FRAMES_NAME,
            "image_pattern": "image_idx_{frame_index}.jpg",
            "legacy_frames": LEGACY_NAME,
        },
    }


def _serialisable_frame(frame: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "frame_index": int(frame["frame_index"]),
        "timestamp_usec": frame.get("timestamp_usec"),
        "image": frame.get("image"),
        "bodies": [
            {
                "body_id": int(body.get("body_id", body.get("id", 0))),
                "joints": [
                    {
                        "joint_index": int(joint.get("joint_index", joint.get("index", index))),
                        "position_mm": joint.get("position_mm", joint.get("position")),
                        "orientation_wxyz": joint.get(
                            "orientation_wxyz", [1.0, 0.0, 0.0, 0.0]
                        ),
                        "confidence_level": int(joint.get("confidence_level", 0)),
                    }
                    for index, joint in enumerate(body.get("joints", []))
                ],
            }
            for body in frame.get("bodies", [])
        ],
    }


def write_session(
    session_folder: str | Path,
    frames: Iterable[Dict[str, Any]],
    manifest: Optional[Dict[str, Any]] = None,
    overwrite: bool = False,
) -> None:
    folder = Path(session_folder)
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / MANIFEST_NAME
    frames_path = folder / FRAMES_NAME
    if not overwrite and (manifest_path.exists() or frames_path.exists()):
        raise FileExistsError("Versioned motion files already exist; use overwrite=True")
    manifest_value = manifest or create_manifest()
    manifest_path.write_text(
        json.dumps(manifest_value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with frames_path.open("w", encoding="utf-8", newline="\n") as stream:
        for frame in frames:
            stream.write(json.dumps(_serialisable_frame(frame), separators=(",", ":")))
            stream.write("\n")


def migrate_legacy_session(session_folder: str | Path, overwrite: bool = False) -> int:
    folder = Path(session_folder)
    frames = load_legacy_frames(folder / LEGACY_NAME)
    write_session(folder, frames, create_manifest(), overwrite=overwrite)
    return len(frames)
