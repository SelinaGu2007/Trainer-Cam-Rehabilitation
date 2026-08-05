# Persistent subject tracking and session gates

## Purpose

TrainerCam recordings preserve every body reported by Azure Kinect. The analysis pipeline then locks one body ID during the first part of the recording and keeps that ID for the whole session. A person who walks into view later cannot silently replace the trainee.

This is an offline robustness layer over Azure Kinect body IDs. It does not claim biometric identity recognition. If the SDK assigns the trainee a new ID, TrainerCam treats the original subject as missing instead of guessing that another body is the same person.

## Selection flow

The default rules are stored in `config/subject_tracking.json` and conform to `schemas/subject-tracking-config-v1.schema.json`.

1. Inspect the first `lock_window_frames` frames.
2. Estimate each body's anchor from the configured joint. If that joint is unavailable, use the median of visible landmarks for migrated legacy recordings.
3. Ignore candidates outside the configured X/Z training region.
4. Prefer the body observed in the most lock-window frames, then confidence and proximity to the region centre.
5. Keep only the selected body ID for the rest of the session. Never switch to a later bystander.

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

The tracking diagnostics are included under `quality.*.subject_tracking` in quality and assessment reports. They include the selected body ID, track coverage, region coverage, missing-frame run, maximum position jump, multi-body counts, failures and warnings.

Use `--function tracking` to print these diagnostics even when a session gate fails. Other analysis modes stop before scoring when a hard gate fails.

## Configuration

The Qt clients read `paths.subject_tracking` from `config/app.json` and pass it to the analyzer. Deployments can also set `TRAINER_CAM_SUBJECT_TRACKING_CONFIG`, or use `--tracking-config PATH` directly.

The default millimetre region is deliberately an engineering baseline. Camera placement and room layout must be checked before changing the region or gates. Real Kinect hardware tests are required to validate appropriate limits for a deployment.
