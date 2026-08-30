# Engineering acceptance and release evidence

## Purpose

TrainerCam's engineering acceptance suite turns the repository's public synthetic sessions into repeatable release evidence. It verifies that the current source can still produce the assessment, feedback and movement-review artifacts expected by the Qt application.

Run it from the repository root:

```powershell
python scripts\run_acceptance.py `
  --output artifacts\acceptance-report.json
```

The command exits non-zero if any required check fails. Its versioned output conforms to `schemas/acceptance-report-v1.schema.json`; thresholds and sample paths come from `config/acceptance.json`.

## Automated checks

The suite currently verifies:

1. every committed default configuration and JSON Schema can be parsed;
2. the public sample directory exactly matches an allow-list of synthetic data paths and its privacy declaration remains present;
3. a complete CLI run writes version 1 assessment, feedback and review artifacts;
4. a second independent run produces the same canonical SHA-256 values after volatile creation timestamps are removed;
5. overall score, DTW path length, subject gates and required-joint coverage match the committed regression baseline;
6. patient-facing result artifacts do not expose absolute local paths;
7. feedback and review artifacts retain an explicit non-diagnostic boundary statement;
8. both small offline sample runs stay within the configured engineering time budget.

The performance check is for regression detection on a four-frame synthetic fixture. It is not the approximately 200 ms live-feedback measurement and is not a hardware performance guarantee.

The release gate is complemented by `python scripts/run_robustness_evaluation.py`, which exercises ten deterministic tracking/filter scenarios and writes `trainercam.robustness-report` version 1. The robustness report remains synthetic evidence and does not change the hardware or clinical limitations below.

## Release build integration

`scripts/build_release.ps1` now requires the complete baseline/unit-test script and the acceptance suite to pass before compiling native Release targets. By default it also requires a clean Git worktree, so the source revision in the evidence is meaningful.

```powershell
.\scripts\build_release.ps1 `
  -QtRoot "D:\Qt\6.6.2\msvc2019_64" `
  -OpenCvRoot "D:\opencv\build" `
  -PythonCommand "python"
```

`-AllowDirty` exists only for development verification. A distributable build should not use it.

After the Kinect recorder and both Qt clients build and Qt runtime deployment completes, `scripts/create_release_manifest.py` inventories every file in the three Release directories. It writes relative paths, byte sizes and SHA-256 values to `artifacts/release-manifest.json`, conforming to `schemas/release-manifest-v1.schema.json`. The manifest also records the acceptance report hash and Git revision.

The `artifacts/` directory is intentionally ignored because acceptance timestamps, platform details and local build inventories are machine-specific evidence, not source.

## What passing does not mean

A passing engineering report explicitly records both of these limitations:

- clinical validation status: `not_performed`;
- target hardware/room validation status: `not_run_by_offline_acceptance`.

Before patient deployment, a release owner must separately document professional review of exercise profiles and wording, real Kinect tests in the target room, multi-person behaviour, speech-engine privacy, recording retention/deletion, accessibility and representative-user usability. Engineering acceptance must not be relabelled as medical-device approval or clinical accuracy evidence.
