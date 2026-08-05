param(
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    param([scriptblock]$Command, [string]$FailureMessage)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw $FailureMessage }
}

Push-Location $ProjectRoot
try {
    Write-Host "Checking configuration and public sample data..."
    $Config = Get-Content -Raw -Encoding UTF8 "config\app.json" | ConvertFrom-Json
    if (-not $Config.paths.tutor_recordings -or -not $Config.paths.customer_recordings) {
        throw "config/app.json does not define the recording directories."
    }
    if (-not (Test-Path "data\samples\tutor_session\output2.txt") -or
        -not (Test-Path "data\samples\customer_session\output2.txt") -or
        -not (Test-Path "data\samples\tutor_session\session.json") -or
        -not (Test-Path "data\samples\tutor_session\frames.jsonl") -or
        -not (Test-Path "data\samples\customer_session\session.json") -or
        -not (Test-Path "data\samples\customer_session\frames.jsonl")) {
        throw "Public offline sample sessions are missing."
    }
    $null = Get-Content -Raw -Encoding UTF8 "schemas\motion-session-v1.schema.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "schemas\motion-frame-v1.schema.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "schemas\exercise-profile-v1.schema.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "schemas\assessment-report-v1.schema.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "schemas\subject-tracking-config-v1.schema.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "schemas\realtime-feedback-config-v1.schema.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "schemas\realtime-feedback-event-v1.schema.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "schemas\realtime-feedback-summary-v1.schema.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "config\exercises\arm_raise.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "config\subject_tracking.json" | ConvertFrom-Json
    $null = Get-Content -Raw -Encoding UTF8 "config\realtime_feedback.json" | ConvertFrom-Json

    Write-Host "Compiling Python sources..."
    Invoke-Checked {
        & $PythonCommand -m py_compile `
            "test_exe\main.py" `
            "test_exe\assessment.py" `
            "test_exe\exercise_profile.py" `
            "test_exe\subject_tracking.py" `
            "test_exe\realtime_feedback.py" `
            "test_exe\motion_data.py" `
            "test_exe\motion_preprocessing.py" `
            "test_exe\DTW.py" `
            "test_exe\view_image.py" `
            "test_exe\save3D.py" `
            "show_videos\showvideo.py" `
            "scripts\migrate_motion_data.py"
    } "Python source compilation failed."

    Write-Host "Running offline analysis tests..."
    Invoke-Checked {
        & $PythonCommand -m unittest discover -s tests -v
    } "Offline analysis tests failed."

    $VsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path -LiteralPath $VsWhere)) {
        Write-Warning "Visual Studio Installer was not found; native Release builds cannot be reproduced yet."
    }

    $MissingHelpers = @(
        "sample_helper_includes\BodyTrackingHelpers.h",
        "sample_helper_includes\Utilities.h",
        "sample_helper_libs\window_controller_3d\Window3dWrapper.h",
        "sample_helper_libs\window_controller_3d"
    ) | Where-Object { -not (Test-Path $_) }
    if ($MissingHelpers.Count -gt 0) {
        throw "Azure Kinect sample helper sources are incomplete."
    }

    Write-Host "Offline reproducibility baseline passed."
} finally {
    Pop-Location
}
