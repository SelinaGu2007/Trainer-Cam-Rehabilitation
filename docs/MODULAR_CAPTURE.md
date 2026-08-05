# Modular capture sources

## Scope

TrainerCam's recorder no longer owns separate processing paths for a live camera and a saved recording. Both enter the same body-tracking, visualisation and motion-session writer through the `CaptureSource` interface.

The first supported drivers are:

- `azure-kinect-live`: captures colour and depth from Azure Kinect device 0;
- `azure-kinect-recording`: reprocesses an Azure Kinect `.mkv` file without requiring a connected camera.

This is an engineering extension point, not a claim that an ordinary RGB webcam already produces Azure Kinect-compatible 3D joints. A future RGB or mobile driver must supply an explicit calibration, coordinate convention, skeleton mapping, timestamps and confidence values before it can safely enter the existing assessment pipeline.

## Application configuration

Both Qt clients read the `capture` section of `config/app.json`:

```json
{
  "capture": {
    "driver": "azure-kinect-live",
    "depth_mode": "NFOV_UNBINNED",
    "processing_mode": "DIRECTML",
    "model_path": "",
    "recording_path": ""
  }
}
```

When `driver` is `azure-kinect-recording`, `recording_path` may name a deployment fixture. If it is empty, TutorClient or CustomerClient asks the operator to select an MKV file when recording starts. The selected source path is passed to the recorder but is not copied into `session.json`; the manifest records the driver and mode without exposing an absolute local path.

The capture object conforms to `schemas/capture-config-v1.schema.json`. Existing local configurations without a `capture` section continue to use `azure-kinect-live`, `NFOV_UNBINNED` and `DIRECTML` defaults.

## Recorder command line

Live device:

```powershell
simple_3d_viewer.exe OUTPUT_FOLDER `
  --source azure-kinect-live `
  --depth-mode NFOV_UNBINNED `
  --processing-mode DIRECTML
```

Recorded Azure Kinect stream:

```powershell
simple_3d_viewer.exe OUTPUT_FOLDER `
  --source azure-kinect-recording `
  --input "C:\recordings\exercise.mkv" `
  --processing-mode CPU
```

The old positional depth/processing arguments and `OFFLINE FILE.mkv` remain accepted for compatibility. New integrations should use the named form because it makes the source contract explicit.

## Completion and failure behaviour

Every driver must open successfully and reach a normal user stop or end of stream before the recorder writes `recording.complete`. Invalid drivers, missing MKV inputs, source read failures and tracker failures return a non-zero exit code and do not publish a false completion marker. Streaming analysis can therefore keep using the same completion contract for either driver.

## Adding another driver

A new native driver implements five operations in `simple_3d_viewer/capture_source.h`: open and provide calibration, read one capture, close resources, report whether it is real-time, and expose a stable driver name. Driver-specific acquisition remains on one side of that boundary; skeleton tracking and session output remain shared.

Before enabling a new driver in the Qt configuration, add its configuration validation, manifest vocabulary, automated fixtures and hardware-specific Release test evidence.
