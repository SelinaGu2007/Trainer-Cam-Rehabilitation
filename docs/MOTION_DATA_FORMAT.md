# TrainerCam motion-session format v1

## Goals

The v1 format makes frame timing, coordinate units, body identity, joint confidence, and file relationships explicit. It is streamable during recording and remains readable without Azure Kinect SDK libraries.

A session directory contains:

```text
session_folder/
├── session.json
├── frames.jsonl
├── output2.txt                 # transitional legacy export
├── image_idx_0.jpg
├── image_idx_1.jpg
└── ...
```

The recorder also writes the misspelled legacy image names (`imamge_idx_*.jpg`) while older visualization code is being retired.

## Manifest: `session.json`

The manifest identifies the format and describes properties shared by every frame:

```json
{
  "format": "trainercam.motion-session",
  "schema_version": 1,
  "created_at": "2026-08-04T12:00:00Z",
  "source": { "type": "azure-kinect", "mode": "live" },
  "coordinate_system": {
    "unit": "millimeter",
    "x_axis": "sensor-right",
    "y_axis": "sensor-down",
    "z_axis": "sensor-forward",
    "orientation_order": "wxyz"
  },
  "skeleton": { "model": "azure-kinect-body-tracking", "joint_count": 32 },
  "files": {
    "frames": "frames.jsonl",
    "image_pattern": "image_idx_{frame_index}.jpg",
    "legacy_frames": "output2.txt"
  }
}
```

Consumers must reject unsupported `format` or `schema_version` values instead of silently guessing.

## Frames: `frames.jsonl`

Each line is an independent JSON object. This lets the recorder append a frame immediately without retaining a complete session in memory. A frame contains every detected body rather than treating each body as a separate moment in time.

```json
{"frame_index":0,"timestamp_usec":104233,"image":"image_idx_0.jpg","bodies":[{"body_id":7,"joints":[{"joint_index":0,"position_mm":[12.4,103.0,1842.1],"orientation_wxyz":[0.99,0.01,0.02,0.03],"confidence_level":2}]}]}
```

Field rules:

- `frame_index` is zero-based and strictly increasing.
- `timestamp_usec` is the Azure Kinect device timestamp in microseconds; migrated legacy data uses `null` because the original value cannot be recovered.
- `image` is relative to the session directory and may be `null` when no color frame exists.
- `body_id` is the SDK tracking ID, not a patient identifier.
- `position_mm` is the raw sensor-space position in millimetres.
- `orientation_wxyz` is the normalized Azure Kinect joint quaternion.
- `confidence_level` uses Azure Kinect values: `0` none, `1` low, `2` medium, `3` high.

The normative JSON Schemas are stored in `schemas/motion-session-v1.schema.json` and `schemas/motion-frame-v1.schema.json`.

## Body selection

The storage format preserves all detected bodies. During analysis, TrainerCam locks one `body_id` from the initial configured time window and training region, then retains that ID for the full recording. It does not switch to a later bystander. Tracking coverage, region membership, target loss, position jumps and multi-person warnings are reported before scoring; see [SUBJECT_TRACKING.md](SUBJECT_TRACKING.md).

## Backward compatibility and migration

Analysis checks for `session.json` first and falls back to `output2.txt`. New recorder sessions write both formats during the transition.

Convert an existing session in place:

```powershell
python scripts\migrate_motion_data.py "C:\recordings\session-001"
```

Use `--overwrite` only when intentionally regenerating `session.json` and `frames.jsonl`. Migration preserves all information available in the legacy file, but old recordings generally have no frame timestamps and may not have orientation or confidence values. Legacy recordings also cannot recover multi-body frame grouping unless they contain the new `Frame Index` markers.

## Compatibility policy

- Readers support motion-session v1 and the legacy text export.
- Writers produce v1 plus the legacy export for the current transition period.
- Future incompatible changes increment `schema_version` and require an explicit migration.
- Derived features, DTW paths, scores, and feedback are analysis results and should not be mixed into raw `frames.jsonl` records.
