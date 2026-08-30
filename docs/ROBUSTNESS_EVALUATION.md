# Synthetic robustness evaluation

## Purpose

`scripts/run_robustness_evaluation.py` provides a deterministic regression harness for active-user continuity and noisy live joints. It uses generated skeleton dictionaries only; no RGB frames, patient recordings or private motion data are stored.

Run from the repository root:

```powershell
python scripts\run_robustness_evaluation.py `
  --output artifacts\robustness-report.json
```

The command exits non-zero when any scenario fails. The versioned output conforms to `schemas/robustness-report-v1.schema.json`.

`scripts/verify_baseline.ps1` runs this command explicitly, and `scripts/build_release.ps1` invokes that baseline before native compilation. A failed robustness scenario therefore blocks Release. A successful report is included in the release manifest as hashed `robustness-evidence`.

## Scenarios

The harness covers:

1. one continuous subject;
2. a bystander entering without a user switch;
3. short loss followed by the same body ID;
4. short loss followed by a compatible new body ID;
5. a previously observed bystander moving closer to the expected position;
6. two ambiguous reassociation candidates;
7. deterministic joint jitter;
8. an implausible joint jump;
9. a short low-confidence joint gap;
10. a joint unavailable beyond the configured hold window.

## Metrics

The report contains user-switch errors, correct and incorrect reassociations, tracking recovery rate, recovery latency in frames, lost frames, ambiguous candidates, raw and filtered variance, variance reduction, outlier rejections and valid-frame retention. Scenario pass/fail values are deterministic so the harness can run in CI and release checks.

## Interpretation and limits

The default thresholds are engineering baselines. Synthetic skeletons are useful for repeatable edge cases but do not reproduce Azure Kinect depth noise, SDK identity behaviour, room geometry, clothing, assistive devices, occlusion patterns or representative user movement. A passing report is not evidence of target-room hardware performance, clinical accuracy or medical-device validation. Those require separate Kinect recordings, representative-user studies and qualified professional review.
