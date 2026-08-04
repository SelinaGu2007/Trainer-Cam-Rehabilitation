# Exercise profiles and explainable scoring

## Purpose

Different exercises depend on different body segments. An arm raise should emphasize the shoulders, elbows, and wrists; a squat should emphasize the hips, knees, and ankles. TrainerCam therefore stores comparison rules in versioned exercise profiles instead of hard-coding one universal set of weights and tolerances.

The included `config/exercises/arm_raise.json` is an engineering example. Its thresholds and feedback have not been clinically validated and must not be presented as medical advice.

## Profile structure

Each profile declares:

- an ID and display name;
- the joint pair used by each motion feature;
- which body-relative axes are compared;
- the importance weight of each feature;
- an error considered close to the reference;
- an error considered substantially different;
- the feedback message used when that feature scores below the configured limit;
- the window size used to find the worst continuous motion segment.

Example feature:

```json
{
  "id": "left_upper_arm",
  "label": "Left upper arm",
  "joints": [5, 6],
  "axes": ["x", "y", "z"],
  "weight": 1.5,
  "good_error_deg": 8,
  "bad_error_deg": 35,
  "feedback": "Review the direction and range of the left upper arm."
}
```

Profiles conform to `schemas/exercise-profile-v1.schema.json` and also pass semantic checks such as unique feature IDs, valid Azure Kinect joint indices, positive weights, and `good_error_deg < bad_error_deg`.

Select a profile by ID or path:

```powershell
python test_exe\main.py `
  --folder_tutor "PATH_TO_TUTOR_SESSION" `
  --folder_customer "PATH_TO_CUSTOMER_SESSION" `
  --profile arm_raise `
  --function report
```

`TRAINER_CAM_EXERCISE_PROFILE` can provide the default profile path for deployments. Without an override, TrainerCam uses `config/exercises/arm_raise.json`.

## Scoring flow

1. Stage 3 prepares and normalizes both body tracks.
2. Each configured joint pair is converted into angles to the selected body axes.
3. Feature weights are applied before DTW so important segments influence temporal alignment.
4. DTW aligns corresponding motion stages even when the user moves faster or slower.
5. For every feature, the aligned angular error is reduced to an RMS error in degrees.
6. The feature score maps the profile's good-to-bad error range onto 100-to-0 and applies a limited outlier penalty.
7. The overall score is the weighted average of the feature scores.

This makes the origin of the total score visible. A low score can be traced to a named body segment, its measured error, its weight, and its configured tolerance.

## Assessment report

`--function report` prints a versioned JSON report containing:

- the profile used;
- the overall score;
- score, RMS error, 95th-percentile error, and feedback for every feature;
- up to three highest-priority improvement messages;
- the worst continuous motion segment and its original tutor/customer frame indices;
- DTW alignment size;
- available timing information;
- the stage 3 data-quality report.

Save the same report to a file with:

```powershell
python test_exe\main.py `
  --folder_tutor "PATH_TO_TUTOR_SESSION" `
  --folder_customer "PATH_TO_CUSTOMER_SESSION" `
  --function report `
  --report-output ".\assessment.json"
```

Reports conform to `schemas/assessment-report-v1.schema.json`.

## Backward compatibility

`--function score` still prints only one numeric value, so the existing Qt process integration continues to work. `showVideos` and `showMaxDiffetence` use the same profile-weighted DTW alignment and report-derived worst segment.

## Adding another exercise

Copy `config/exercises/arm_raise.json`, give the profile a new ID, then update its feature list, weights, tolerances, and messages. Add synthetic fixtures and tests before making it selectable in the user interface. Clinical exercises require review and calibration by qualified rehabilitation professionals before real-world use.
