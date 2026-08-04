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
    -NuGetExe "C:\tools\nuget.exe"
```

The Qt Release executables are written to:

- `build-qt-cmake/TutorClient/Release/TutorClient.exe`
- `build-qt-cmake/CustomerClient/Release/CustomerClient.exe`

The existing `.pro` files can still be opened in Qt Creator, but CMake is the reproducible command-line baseline.

The clients expect the recorder, video player and analyzer at the paths declared in `config/app.json`. Those programs can also be launched from source during development by changing a local configuration.

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

Each recording writes the versioned `session.json` and `frames.jsonl` files as well as the transitional `output2.txt` export. See `docs/MOTION_DATA_FORMAT.md` for the schema and legacy migration command.

## Vendored Azure Kinect sample helpers

The helper source used by the recorder is committed under `sample_helper_includes` and `sample_helper_libs`. It was restored from Microsoft's official Azure Kinect Samples repository at the commit recorded in `third_party/Azure-Kinect-Samples.PROVENANCE.md` and remains under the upstream MIT License.
