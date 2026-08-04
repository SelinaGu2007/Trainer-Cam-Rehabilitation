# Motion preprocessing and body normalisation

Raw joint coordinates are not compared directly. The same exercise can be recorded at a different place, distance, body size, or camera-facing angle, and Azure Kinect may briefly lose a joint. The preprocessing layer converts one selected body track into a stable comparison sequence before feature extraction and DTW.

## Pipeline

```text
versioned or legacy session
        ↓
stable body track
        ↓
confidence and finite-value mask
        ↓
short-gap interpolation
        ↓
body-relative coordinate system
        ↓
body-scale normalisation
        ↓
incomplete-frame filtering
        ↓
angle features, smoothing and DTW
```

## Confidence handling

For recordings with confidence metadata, a joint is observed when:

- its position contains three finite, nonzero values; and
- `confidence_level` meets `--min-confidence` (default `1`, Azure Kinect low confidence).

Legacy fixtures that never recorded confidence are detected automatically and use finite, nonzero positions. This preserves old recordings instead of rejecting every joint as confidence level zero.

## Short missing gaps

A joint missing between two valid observations is linearly interpolated when the gap is no longer than `--max-interpolation-gap` frames (default `3`). Longer gaps remain invalid. Interpolated samples are marked internally and reported in the quality summary; they are not presented as newly observed measurements.

## Body-relative coordinates

Each frame is translated to the pelvis. If the pelvis is unavailable, the hip midpoint and then the shoulder midpoint are used as fallbacks.

The local axes are estimated from the shoulder and hip geometry:

- local X follows left shoulder to right shoulder;
- local Y follows shoulder midpoint toward hip midpoint;
- local Z is perpendicular to the torso plane.

Coordinates are divided by the median shoulder width across the session. Hip width is a fallback when shoulder width cannot be measured. The resulting values are dimensionless, reducing differences caused by camera position, user distance, body size, and sensor-facing rotation.

## Quality gates

The feature joints used by the current scorer must meet the session coverage threshold (`--min-required-coverage`, default `0.8`). After short-gap repair, individual frames that do not contain the requested fraction of feature joints are removed (`--min-frame-joint-fraction`, default `1.0`). A recording with no usable frames fails clearly instead of producing a misleading score.

Print a quality report without running DTW:

```powershell
python test_exe\main.py `
  --folder_tutor "PATH_TO_TUTOR_SESSION" `
  --folder_customer "PATH_TO_CUSTOMER_SESSION" `
  --function quality
```

The report includes total joint coverage, feature-joint coverage, interpolation ratio, estimated body scale, selected body ID, and usable frame count.

## Main tuning options

| Option | Default | Purpose |
| --- | ---: | --- |
| `--min-confidence` | `1` | Lowest accepted Azure Kinect confidence level |
| `--max-interpolation-gap` | `3` | Largest missing gap repaired per joint |
| `--min-required-coverage` | `0.8` | Minimum feature-joint coverage for a session |
| `--min-frame-joint-fraction` | `1.0` | Required feature-joint fraction in each retained frame |
| `--smoothing-sigma` | `3.0` | Temporal Gaussian smoothing strength |
| `--no-normalize` | off | Diagnostic switch to keep raw millimetre coordinates |

These are engineering defaults, not clinically validated thresholds. Exercise-specific tolerances and weights belong in configurable exercise profiles in a later stage.
