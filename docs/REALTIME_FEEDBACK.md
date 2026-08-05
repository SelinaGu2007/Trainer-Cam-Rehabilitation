# Streaming real-time feedback

## Purpose and boundary

TrainerCam can now analyse a customer recording while Azure Kinect is still writing it. The analyser tails `frames.jsonl`, locks the trainee using the phase 5 rules, compares each usable pose with a nearby stage of the tutor reference, and emits stable corrective messages.

This is an engineering feedback aid, not a medical alarm or a clinically validated rehabilitation decision system. The default thresholds come from the selected exercise profile and still require professional calibration.

## Runtime flow

1. The customer selects a tutor demonstration and starts recording.
2. CustomerClient starts the recorder, tutor playback, and real-time analyser together.
3. The analyser prepares the tutor trajectory once.
4. It waits for the initial subject-lock window, then retains one Azure Kinect body ID.
5. Each new customer pose searches only a small forward/backward window of the tutor trajectory. This online alignment avoids rerunning full DTW for every frame.
6. Per-feature angular errors use the same exercise profile, weights, tolerances, and messages as the post-session report.
7. A correction is emitted only after the same problem persists for several frames. A cooldown prevents repeated message spam, and several good frames clear an active warning.
8. The recorder writes `recording.complete` after all motion data is flushed. The analyser then writes its summary and exits.

## Outputs

The customer session receives:

- `live_feedback.jsonl`: versioned `trainercam.realtime-feedback-event` records;
- `live_feedback_summary.json`: selected body ID, processed-frame count, event counts, and measured processing latency;
- `recording.complete`: recorder completion marker.

Event statuses are:

- `adjust`: a persistent named feature error needs correction;
- `correct`: a previous error returned to the configured range;
- `tracking`: the locked trainee or required joints are not visible.

Events and summaries conform to `schemas/realtime-feedback-event-v1.schema.json` and `schemas/realtime-feedback-summary-v1.schema.json`.

When `--live-display` is enabled, the latest message is drawn over the current customer image in a separate feedback window.

## Command line

```powershell
python test_exe\main.py `
  --folder_tutor "PATH_TO_TUTOR_SESSION" `
  --folder_customer "PATH_TO_GROWING_CUSTOMER_SESSION" `
  --profile arm_raise `
  --tracking-config config\subject_tracking.json `
  --realtime-config config\realtime_feedback.json `
  --live-display `
  --function realtime
```

The default tuning is in `config/realtime_feedback.json`. It controls the online alignment window, initial smoothing, number of persistent bad/good frames, message cooldown, tracking warning delay, polling interval and completion marker.

## Latency interpretation

Every event and the final summary record measured analyser processing latency. Automated tests require the small online comparison step to remain below a 200 ms per-frame engineering budget on the development machine.

That number is not an end-to-end hardware guarantee. Kinect capture, body tracking, image and disk I/O, Qt/OpenCV rendering, and machine load add latency. A real Kinect timing run is still required before quoting deployment latency.
