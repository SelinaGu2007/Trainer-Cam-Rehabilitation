# TrainerCam: Human Motion Assessment for Rehabilitation

TrainerCam is a rehabilitation exercise coaching prototype that records human motion with Azure Kinect, extracts 3D skeleton joints, compares a user's movement with a tutor demonstration, and visualizes motion differences.

![Motion analysis visualization](docs/motion_analysis.png)

*Motion comparison visualization. Left: Dynamic Time Warping alignment between tutor and user joint-angle trajectories. Right: a 3D skeleton reconstructed from Azure Kinect body-tracking data.*

## Overview

The system provides an end-to-end workflow for recording and comparing rehabilitation exercises:

```text
Tutor demonstration
        ↓
Azure Kinect body tracking
        ↓
3D skeleton extraction
        ↓
Joint-angle feature computation
        ↓
User exercise recording
        ↓
Temporal alignment with Dynamic Time Warping
        ↓
Motion score and frame-level visualization
```

The project includes:

- C++ programs for Azure Kinect body tracking and data recording
- Qt desktop interfaces for tutor and customer workflows
- Python scripts for skeleton processing, motion alignment, scoring, and visualization
- Playback utilities for recorded image sequences

## Method

The motion-comparison pipeline consists of the following steps:

1. Capture RGB frames and 3D body-joint coordinates using Azure Kinect Body Tracking.
2. Extract angle-based motion features from selected body joints.
3. Smooth motion trajectories using a Gaussian filter.
4. Align tutor and user sequences with Dynamic Time Warping.
5. Compute distances between aligned frames.
6. Produce either an aggregate motion score or frame-level comparison visualizations.

Dynamic Time Warping allows exercises performed at different speeds to be compared by aligning corresponding stages of the motion.

## Repository Structure

### `simple_3d_viewer/`

**C++ · Azure Kinect Body Tracking · OpenCV**

Records a body-tracking session to a folder supplied as a command-line argument.

Generated files include:

- `output2.txt`: per-frame coordinates for 32 body joints
- `imamge_idx_<frame>.jpg`: RGB frames captured during the session

> The `imamge` spelling is retained because it is used by the current recording and analysis pipeline.

### `TutorClient/`

**Qt · C++**

Tutor-side desktop application that:

- creates a new recording folder;
- launches the Azure Kinect recorder;
- captures a tutor demonstration;
- replays previously recorded demonstrations when the playback tool is available.

### `CustomerClient/`

**Qt · C++**

Customer-side desktop application that:

- displays available customer recordings;
- compares a selected customer session with a tutor demonstration;
- launches the analysis workflow;
- displays generated comparison frames.

### `test_exe/`

**Python · NumPy · SciPy · Dynamic Time Warping**

The core motion-comparison logic is implemented in:

```text
test_exe/main.py
```

It:

1. loads tutor and customer skeleton data from `output2.txt`;
2. computes joint-angle features;
3. applies Gaussian smoothing;
4. aligns the motion sequences using a DTW warping path;
5. computes distances between aligned frames;
6. prints a motion score or generates analysis visualizations.

Supported modes:

- `--function score`: prints an aggregate motion-comparison score;
- `--function showVideos`: generates frame-level analysis images.

Generated analysis images are saved under:

```text
<customer_folder>/analyse/
```

### `show_videos/`

**Python**

Plays an image sequence matching `*_idx_*.jpg` as a lightweight video viewer.

## Expected Recording Layout

Each tutor or customer recording folder should contain:

```text
session_folder/
├── output2.txt
├── imamge_idx_0.jpg
├── imamge_idx_1.jpg
├── imamge_idx_2.jpg
└── ...
```

## Running the Python Analysis

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Compute a motion score

```bash
python test_exe/main.py \
  --folder_tutor "PATH_TO_TUTOR_SESSION" \
  --folder_customer "PATH_TO_CUSTOMER_SESSION" \
  --function score
```

### 3. Generate analysis visualizations

```bash
python test_exe/main.py \
  --folder_tutor "PATH_TO_TUTOR_SESSION" \
  --folder_customer "PATH_TO_CUSTOMER_SESSION" \
  --function showVideos
```

The generated visualization frames are saved under:

```text
<customer_folder>/analyse/
```

## Project Contributions

I independently developed the main components of this project, including:

- the Azure Kinect body-tracking and recording workflow;
- the tutor-side and customer-side Qt interfaces;
- 3D skeleton data processing;
- joint-angle feature extraction;
- Gaussian smoothing of motion trajectories;
- Dynamic Time Warping alignment;
- motion-comparison scoring;
- frame-level visualization generation;
- integration between the recording, analysis, and playback components.

## System Diagram

![System diagram](docs/system_diagram.png)

## Privacy and Repository Notes

- Build outputs, binaries, large dependencies, NuGet packages, OpenCV DLLs, and PyInstaller `dist/` and `build/` directories are excluded through `.gitignore`.
- RGB recordings and body-tracking data may contain sensitive personal information.
- Real patient recordings should not be uploaded to a public repository.
- This repository contains source code and example visualizations, but no private rehabilitation data.
