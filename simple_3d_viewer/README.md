# Azure Kinect Body Tracking Simple3dViewer Sample

## Introduction

The Azure Kinect Body Tracking Simple3dViewer sample creates a 3d window that visualizes all the information provided
by the body tracking SDK.

The recorder writes `recording.complete` after `session.json`, `frames.jsonl`,
`output2.txt`, and the session log have been flushed. Streaming analysis uses
this marker to finish without reading a partial final frame.

Capture acquisition is isolated behind `CaptureSource`. Use
`--source azure-kinect-live` for device 0 or
`--source azure-kinect-recording --input FILE.mkv` for deterministic offline
processing. Both drivers use the same body-tracking and session-writing loop;
the legacy `OFFLINE FILE.mkv` command remains supported.

## Usage Info

USAGE: simple_3d_viewer.exe OUTPUT_FOLDER [--source DRIVER] [--input FILE.mkv] [--depth-mode MODE] [--processing-mode MODE]
* SensorMode:
  * NFOV_UNBINNED (default) - Narraw Field of View Unbinned Mode [Resolution: 640x576; FOI: 75 degree x 65 degree]
  * WFOV_BINNED             - Wide Field of View Binned Mode [Resolution: 512x512; FOI: 120 degree x 120 degree]
* RuntimeMode:
  * CPU - Use the CPU only mode. It runs on machines without a GPU but it will be much slower
  * OFFLINE - Play a specified file. Does not require Kinect device. Can use with CPU mode

```
e.g.   simple_3d_viewer.exe WFOV_BINNED CPU
                 simple_3d_viewer.exe CPU
                 simple_3d_viewer.exe WFOV_BINNED
                 simple_3d_viewer.exe OFFLINE MyFile.mkv
```

## Instruction

### Basic Navigation:
* Rotate: Rotate the camera by moving the mouse while holding mouse left button
* Pan: Translate the scene by holding Ctrl key and drag the scene with mouse left button
* Zoom in/out: Move closer/farther away from the scene center by scrolling the mouse scroll wheel
* Select Center: Center the scene based on a detected joint by right clicking the joint with mouse

### Key Shortcuts
* ESC: quit
* h: help
* b: body visualization mode
* k: 3d window layout
