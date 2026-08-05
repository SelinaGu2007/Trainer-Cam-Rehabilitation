# Reproducible development baseline

## Supported baseline

The repository targets Windows 10/11 x64. The documented native toolchain is:

- Visual Studio 2022 with the Desktop development with C++ workload (`v143`);
- Qt 6.6.2 with the MSVC 2019 x64 kit (Qt 5 remains supported by CMake);
- CMake 3.21 or newer;
- Azure Kinect Sensor SDK 1.4.1;
- Azure Kinect Body Tracking SDK/NuGet package 1.1.2;
- OpenCV 4.8.0 for the native recorder;
- Python 3.11 x64 for analysis and packaging.

The Python package versions are pinned in `requirements.txt`. Python 3.11 is the supported packaging version; newer Python versions may run the NumPy fallback scorer but are not the release baseline.

## Python setup

From PowerShell in the repository root:

```powershell
.\scripts\setup_python.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

To validate with an already configured Python interpreter:

```powershell
.\scripts\verify_baseline.ps1
```

The score workflow has a NumPy-only DTW and smoothing fallback. OpenCV, Matplotlib and `dtaidistance` are still required for the complete visualization and packaged application.

## Runtime configuration

Both Qt clients read `config/app.json`. Relative paths are resolved from `project_root`, not from whichever directory happens to launch the executable.

`paths.exercise_profile` selects the default exercise profile passed to the analyzer. Existing local configuration files that omit it fall back to `config/exercises/arm_raise.json`.

`paths.subject_tracking` selects the training-region and subject-locking configuration passed to the analyzer. Existing local configuration files that omit it fall back to `config/subject_tracking.json`.

`paths.realtime_feedback` selects the online alignment, feedback stabilisation, polling and completion settings. Existing local configuration files that omit it fall back to `config/realtime_feedback.json`.

The `feedback` section selects the post-session summary locale and default voice state, rate and volume. CustomerClient uses Qt TextToSpeech and requires a compatible operating-system speech engine. The visual result remains available when speech is unavailable.

The `capture` section selects `azure-kinect-live` or `azure-kinect-recording`, depth mode, body-tracker processing mode and an optional model path. A recording driver with no configured `recording_path` opens an MKV file chooser in either Qt client. See `docs/MODULAR_CAPTURE.md` for the driver contract and compatibility defaults.

Set `TRAINER_CAM_CONFIG` to use another configuration file:

```powershell
$env:TRAINER_CAM_CONFIG = "C:\path\to\app.local.json"
```

Local configurations should use `config/app.local.json`, which is ignored by Git.

At startup, the applications create the configured tutor, customer and log directories. Qt logs are written to the configured `logs` directory.

## Qt clients

The verified command-line path uses the root `CMakeLists.txt`, Visual Studio 2022 and an MSVC x64 Qt installation. It builds both clients and deploys their Qt runtime files:

```powershell
.\scripts\build_release.ps1 `
    -QtRoot "D:\Qt\6.6.2\msvc2019_64" `
    -OpenCvRoot "D:\opencv\build" `
    -NuGetExe "C:\tools\nuget.exe" `
    -PythonCommand "python"
```

The unified Release script requires a clean Git worktree and a passing engineering acceptance report before compilation. `-AllowDirty` is available only for local development verification. See [ENGINEERING_ACCEPTANCE.md](ENGINEERING_ACCEPTANCE.md) for the exact checks and validation limits.

The Qt Release executables are written to:

- `build-qt-cmake/TutorClient/Release/TutorClient.exe`
- `build-qt-cmake/CustomerClient/Release/CustomerClient.exe`

Machine-specific release evidence is written to `artifacts/acceptance-report.json` and `artifacts/release-manifest.json`. The manifest inventories the deployed Release directories with relative paths, sizes and SHA-256 values.

The existing `.pro` files can still be opened in Qt Creator, but CMake is the reproducible command-line baseline.

The clients expect the recorder, video player and analyzer at the paths declared in `config/app.json`. Those programs can also be launched from source during development by changing a local configuration.

If the packaged analyzer configured at `paths.analyzer` is absent, the Qt clients automatically fall back to `python test_exe/main.py` when Python is available on `PATH`. A packaged analyzer remains preferred for deployment.

CustomerClient's normal assessment flow asks the analyzer for `assessment.json`, `feedback_summary.json` and `session_review.json`. The last artifact drives the native aligned review window and does not require the legacy OpenCV result player. Use `CustomerClient.exe --review-preview REVIEW_JSON CUSTOMER_SESSION TUTOR_SESSION --locale en-US` for UI verification without signing in.

## Azure Kinect recorder

`simple_3d_viewer/simple_3d_viewer.sln` uses Visual Studio 2022 and NuGet package restore. The unified script above sets `OPENCV_DIR`; when invoking MSBuild directly, define it as the OpenCV build directory containing `include` and `x64/vc16/lib`.

Example:

```powershell
$env:OPENCV_DIR = "C:\tools\opencv\build"
```

The recorder now requires an output directory as its first argument and creates that directory if necessary:

```powershell
.\simple_3d_viewer\build\bin\Release\simple_3d_viewer.exe ".\data\runtime\tutor\arm_raise"
```

The equivalent explicit live-source invocation is:

```powershell
.\simple_3d_viewer\build\bin\Release\simple_3d_viewer.exe `
  ".\data\runtime\tutor\arm_raise" `
  --source azure-kinect-live `
  --processing-mode DIRECTML
```

An Azure Kinect MKV can be processed without a connected device by selecting `--source azure-kinect-recording --input FILE.mkv`.

Each recording writes the versioned `session.json` and `frames.jsonl` files as well as the transitional `output2.txt` export. See `docs/MOTION_DATA_FORMAT.md` for the schema and legacy migration command.

## Vendored Azure Kinect sample helpers

The helper source used by the recorder is committed under `sample_helper_includes` and `sample_helper_libs`. It was restored from Microsoft's official Azure Kinect Samples repository at the commit recorded in `third_party/Azure-Kinect-Samples.PROVENANCE.md` and remains under the upstream MIT License.
