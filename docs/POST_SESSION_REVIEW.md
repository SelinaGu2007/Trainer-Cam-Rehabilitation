# Post-session movement review

## User flow

After assessment, CustomerClient opens the existing score and voice-feedback window. `Review movement comparison` opens a native Qt review window instead of relying on an OpenCV playback window.

The review window provides:

- the tutor and customer colour frames side by side;
- a slider over the Dynamic Time Warping alignment rather than raw frame number;
- previous, next, play and pause controls;
- a direct jump to the highest-error part of the exercise;
- zoom from 50% to 300% with scrollable enlarged images;
- the original frame numbers, combined angle difference and highest-priority feature at each aligned position;
- a visible marker while the timeline is inside the worst assessment segment.

This answers three different questions without requiring the user to interpret a technical plot: where the issue occurred, which body segment differed most at that point, and how the user's visible posture compared with the demonstration.

## Review data

The analyzer writes `session_review.json` using `trainercam.session-review` schema version 1. It contains alignment indices, original customer/tutor frame references, timestamps, the aggregate angular difference and the most significant configured feature for every aligned pair.

The artifact conforms to `schemas/session-review-v1.schema.json`. It contains relative image file names only; it does not copy images, absolute local paths, skeleton coordinates or audio. CustomerClient resolves each image inside its known session directory and rejects path traversal outside that directory.

The review severity labels are engineering categories based on the exercise profile's configured good/bad angle thresholds. They are not clinical severity grades.

## Command line

Generate the assessment, feedback and review artifacts together:

```powershell
python test_exe\main.py `
  --folder_tutor "PATH_TO_TUTOR_SESSION" `
  --folder_customer "PATH_TO_CUSTOMER_SESSION" `
  --function artifacts `
  --report-output assessment.json `
  --feedback-output feedback_summary.json `
  --review-output session_review.json
```

Preview the Qt review window without signing in:

```powershell
CustomerClient.exe `
  --review-preview session_review.json CUSTOMER_SESSION TUTOR_SESSION `
  --locale en-US
```

The result-window preview can expose the same entry point with `--feedback-preview`, `--review`, `--customer-folder` and `--tutor-folder` arguments. Add `--no-voice` during silent UI checks.

The older `showVideos` and `showMaxDiffetence` analyzer modes remain available for engineering diagnostics. They are no longer the normal CustomerClient result flow.

## Data limitations

If a session does not contain a colour image for an aligned frame, the timeline and error description remain available and the corresponding panel shows an explicit missing-image message. Interpolated or removed low-confidence frames are not presented as newly observed camera frames; the review references only the retained assessment sequence.
