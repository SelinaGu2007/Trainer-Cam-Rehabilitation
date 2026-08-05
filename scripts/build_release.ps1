param(
    [Parameter(Mandatory = $true)]
    [string]$QtRoot,

    [Parameter(Mandatory = $true)]
    [string]$OpenCvRoot,

    [string]$NuGetExe = "nuget.exe",

    [string]$PythonCommand = "python",

    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments, [string]$FailureMessage)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw $FailureMessage }
}

if (-not (Test-Path -LiteralPath $QtRoot)) {
    throw "QtRoot does not exist: $QtRoot"
}
if (-not (Test-Path -LiteralPath $OpenCvRoot)) {
    throw "OpenCvRoot does not exist: $OpenCvRoot"
}
if (-not (Test-Path -LiteralPath $VsWhere)) {
    throw "Visual Studio Installer (vswhere.exe) was not found."
}

$VisualStudioRoot = & $VsWhere -latest -products * -requires Microsoft.Component.MSBuild -property installationPath
if (-not $VisualStudioRoot) { throw "Visual Studio with MSBuild was not found." }

$MSBuild = Join-Path $VisualStudioRoot "MSBuild\Current\Bin\MSBuild.exe"
$CMake = Join-Path $VisualStudioRoot "Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
$WinDeployQt = Join-Path $QtRoot "bin\windeployqt.exe"
$QtConfig = Join-Path $QtRoot "lib\cmake\Qt6\Qt6Config.cmake"

foreach ($RequiredFile in @($MSBuild, $CMake, $WinDeployQt, $QtConfig)) {
    if (-not (Test-Path -LiteralPath $RequiredFile)) {
        throw "Required build tool was not found: $RequiredFile"
    }
}

$Python = Get-Command $PythonCommand -ErrorAction SilentlyContinue
if (-not $Python) {
    throw "Python was not found: $PythonCommand"
}

Push-Location $ProjectRoot
try {
    $GitStatus = & git status --porcelain
    if ($LASTEXITCODE -ne 0) { throw "Unable to inspect the Git worktree." }
    if ($GitStatus -and -not $AllowDirty) {
        throw "Release builds require a clean Git worktree. Commit changes or pass -AllowDirty for development-only verification."
    }

    $ArtifactsDirectory = Join-Path $ProjectRoot "artifacts"
    $AcceptanceReport = Join-Path $ArtifactsDirectory "acceptance-report.json"
    $ReleaseManifest = Join-Path $ArtifactsDirectory "release-manifest.json"
    & (Join-Path $PSScriptRoot "verify_baseline.ps1") -PythonCommand $Python.Source
    Invoke-Checked $Python.Source @(
        "scripts\run_acceptance.py",
        "--output", $AcceptanceReport
    ) "Engineering acceptance failed."

    $KinectPackages = "simple_3d_viewer\packages"
    if (-not (Test-Path -LiteralPath "$KinectPackages\Microsoft.Azure.Kinect.Sensor.1.4.1")) {
        $NuGetCommand = Get-Command $NuGetExe -ErrorAction SilentlyContinue
        if (-not $NuGetCommand) {
            throw "Kinect NuGet packages are missing and NuGet was not found. Pass -NuGetExe with a nuget.exe path."
        }
        Invoke-Checked $NuGetCommand.Source @(
            "restore", "simple_3d_viewer\simple_3d_viewer.sln",
            "-PackagesDirectory", $KinectPackages,
            "-NonInteractive"
        ) "NuGet restore failed."
    }

    $env:OPENCV_DIR = (Resolve-Path -LiteralPath $OpenCvRoot).Path
    Invoke-Checked $MSBuild @(
        "simple_3d_viewer\simple_3d_viewer.sln",
        "/m:1", "/p:Configuration=Release", "/p:Platform=x64", "/verbosity:minimal"
    ) "Azure Kinect recorder Release build failed."

    $QtBuildDirectory = Join-Path $ProjectRoot "build-qt-cmake"
    Invoke-Checked $CMake @(
        "-S", $ProjectRoot,
        "-B", $QtBuildDirectory,
        "-G", "Visual Studio 17 2022",
        "-A", "x64",
        "-DCMAKE_PREFIX_PATH=$QtRoot"
    ) "Qt CMake configuration failed."
    Invoke-Checked $CMake @(
        "--build", $QtBuildDirectory,
        "--config", "Release"
    ) "Qt Release build failed."

    foreach ($Client in @("TutorClient", "CustomerClient")) {
        $Executable = Join-Path $QtBuildDirectory "$Client\Release\$Client.exe"
        Invoke-Checked $WinDeployQt @(
            "--release", "--no-translations", "--no-compiler-runtime", $Executable
        ) "Qt runtime deployment failed for $Client."
    }

    Invoke-Checked $Python.Source @(
        "scripts\create_release_manifest.py",
        "--acceptance-report", $AcceptanceReport,
        "--output", $ReleaseManifest,
        "--root", "kinect-recorder=simple_3d_viewer\build\bin\Release",
        "--root", "tutor-client=build-qt-cmake\TutorClient\Release",
        "--root", "customer-client=build-qt-cmake\CustomerClient\Release"
    ) "Release manifest generation failed."

    Write-Host "Release builds completed successfully."
    Write-Host "Kinect: simple_3d_viewer\build\bin\Release\simple_3d_viewer.exe"
    Write-Host "Tutor:  build-qt-cmake\TutorClient\Release\TutorClient.exe"
    Write-Host "Client: build-qt-cmake\CustomerClient\Release\CustomerClient.exe"
    Write-Host "Evidence: artifacts\acceptance-report.json"
    Write-Host "Manifest: artifacts\release-manifest.json"
} finally {
    Pop-Location
}
