# Persistent subject tracking and session gates

## Purpose

TrainerCam recordings preserve every body reported by Azure Kinect. The analysis pipeline locks one subject during the first part of the recording and then follows an explicit state machine. A person who walks into view later cannot silently replace the trainee, while a compatible new Kinect body ID can be recovered after a short loss.

This is a conservative continuity tracker, not biometric identity recognition. Reassociation uses recent position, velocity, shoulder scale, ROI membership and joint confidence. Ambiguous candidates are rejected rather than guessed.

## Tracker states

```text
UNINITIALIZED -> LOCKED -> TEMPORARILY_LOST -> REASSOCIATING -> LOCKED / LOST
```

The original body ID always has priority. A different ID must be spatially and physically compatible for several consecutive frames. IDs already observed as bystanders while the trainee was visible are not eligible for recovery. The offline selector and streaming feedback share the same `ActiveUserTracker` implementation.

## Selection flow

The default rules are stored in `config/subject_tracking.json` and conform to `schemas/subject-tracking-config-v1.schema.json`.

1. Inspect the first `lock_window_frames` frames.
2. Estimate each body's anchor from the configured joint. If that joint is unavailable, use the median of visible landmarks for migrated legacy recordings.
3. Ignore candidates outside the configured X/Z training region.
4. Prefer the body observed in the most lock-window frames, then confidence and proximity to the region centre.
5. Prefer the selected body ID for the rest of the session.
6. If that ID disappears, wait through the temporary-loss window.
7. Confirm one unambiguous, position/scale-compatible new ID over multiple frames before reassociation.

An operator can override automatic selection when investigating a recording:

```powershell
python test_exe\main.py `
  --folder_tutor "PATH_TO_TUTOR_SESSION" `
  --folder_customer "PATH_TO_CUSTOMER_SESSION" `
  --tutor-body-id 12 `
  --customer-body-id 34 `
  --function report
```

## Session gates

Before motion scoring, TrainerCam checks:

- how much of the recording contains the locked body;
- how often that body remains inside the training region;
- the longest continuous period where the body is missing;
- whether the anchor position makes an implausibly large jump.

If a hard gate fails, scoring stops rather than turning tracking failure into an incorrect rehabilitation score. Multiple people in the region generate a warning, but do not replace the locked body.

The tracking diagnostics are included under `quality.*.subject_tracking` in quality and assessment reports. They include initial/current/final body IDs, body-ID history, state transitions, reassociations, successful recoveries, ambiguous candidates, rejected switches, lost frames, recovery latency, track coverage, region coverage, missing-frame run, maximum position jump, multi-body counts, failures and warnings.

Use `--function tracking` to print these diagnostics even when a session gate fails. Other analysis modes stop before scoring when a hard gate fails.

## Configuration

The Qt clients read `paths.subject_tracking` from `config/app.json` and pass it to the analyzer. Deployments can also set `TRAINER_CAM_SUBJECT_TRACKING_CONFIG`, or use `--tracking-config PATH` directly.

The default millimetre region is deliberately an engineering baseline. Camera placement and room layout must be checked before changing the region or gates. Real Kinect hardware tests are required to validate appropriate limits for a deployment.

The `reassociation` section controls maximum spatial distance and scale ratio, confirmation duration, temporary-loss and terminal-loss timing, ambiguity margin and velocity smoothing. Defaults are deliberately conservative and require target-room tuning.
