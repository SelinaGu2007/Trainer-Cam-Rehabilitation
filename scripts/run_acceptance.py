"""Run the deterministic, privacy-safe TrainerCam engineering acceptance suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Tuple


REPORT_FORMAT = "trainercam.acceptance-report"
REPORT_SCHEMA_VERSION = 1
CONFIG_FORMAT = "trainercam.acceptance-config"
CONFIG_SCHEMA_VERSION = 1


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def load_acceptance_config(path: Path) -> Dict[str, Any]:
    value = _load_json(path)
    if value.get("format") != CONFIG_FORMAT or value.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError("Unsupported acceptance configuration format or version")
    for section in ("samples", "regression", "performance", "privacy"):
        if not isinstance(value.get(section), dict):
            raise ValueError(f"Acceptance configuration requires {section}")
    if float(value["regression"]["score_tolerance"]) < 0:
        raise ValueError("score_tolerance cannot be negative")
    if float(value["performance"]["maximum_offline_artifact_seconds"]) <= 0:
        raise ValueError("maximum_offline_artifact_seconds must be positive")
    return value


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonical(item)
            for key, item in sorted(value.items())
            if key != "created_at"
        }
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        _canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _git_revision(project_root: Path) -> Dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": "unavailable", "dirty": True}


def _run_artifacts(
    project_root: Path,
    config: Dict[str, Any],
    output_directory: Path,
) -> Tuple[Dict[str, Dict[str, Any]], float]:
    samples = config["samples"]
    paths = {
        "assessment": output_directory / "assessment.json",
        "feedback": output_directory / "feedback.json",
        "review": output_directory / "review.json",
    }
    command = [
        sys.executable,
        str(project_root / "test_exe" / "main.py"),
        "--folder_tutor",
        str(project_root / samples["tutor_session"]),
        "--folder_customer",
        str(project_root / samples["customer_session"]),
        "--profile",
        str(project_root / samples["profile"]),
        "--function",
        "artifacts",
        "--report-output",
        str(paths["assessment"]),
        "--feedback-output",
        str(paths["feedback"]),
        "--review-output",
        str(paths["review"]),
        "--feedback-locale",
        "en-US",
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    duration = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            "Analyzer artifact mode failed: " + completed.stderr.strip()[-1000:]
        )
    if completed.stdout.strip():
        raise RuntimeError("Artifact mode unexpectedly wrote user data to stdout")
    return {name: _load_json(path) for name, path in paths.items()}, duration


def run_acceptance(
    config_path: str | Path | None = None,
    project_root: str | Path | None = None,
) -> Dict[str, Any]:
    root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    selected_config = Path(config_path) if config_path else root / "config" / "acceptance.json"
    if not selected_config.is_absolute():
        selected_config = root / selected_config
    config = load_acceptance_config(selected_config.resolve())
    checks = []
    context: Dict[str, Any] = {}

    def check(identifier: str, action: Callable[[], Tuple[str, Dict[str, Any]]]) -> None:
        started = time.perf_counter()
        try:
            detail, metrics = action()
            status = "passed"
        except Exception as exc:  # report every acceptance failure together
            detail = str(exc)
            metrics = {}
            status = "failed"
        checks.append(
            {
                "id": identifier,
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "detail": detail,
                "metrics": metrics,
            }
        )

    def configuration_check() -> Tuple[str, Dict[str, Any]]:
        json_files = sorted((root / "schemas").glob("*.json"))
        json_files.extend(
            path
            for path in sorted((root / "config").rglob("*.json"))
            if not path.name.endswith(".local.json")
        )
        for path in json_files:
            _load_json(path)
        return "All committed schemas and default configurations are readable JSON.", {
            "json_file_count": len(json_files)
        }

    def sample_check() -> Tuple[str, Dict[str, Any]]:
        privacy = config["privacy"]
        allowed_paths = {str(value).replace("\\", "/") for value in privacy["allowed_sample_paths"]}
        sample_root = root / "data" / "samples"
        files = [path for path in sample_root.rglob("*") if path.is_file()]
        observed_paths = {path.relative_to(sample_root).as_posix() for path in files}
        unexpected = sorted(observed_paths - allowed_paths)
        missing = sorted(allowed_paths - observed_paths)
        declaration = (sample_root / "README.txt").read_text(encoding="utf-8").lower()
        if unexpected:
            raise ValueError("Unexpected public sample files: " + ", ".join(unexpected))
        if missing:
            raise ValueError("Expected public sample files are missing: " + ", ".join(missing))
        if "synthetic" not in declaration or "no private patient data" not in declaration:
            raise ValueError("Public sample privacy declaration is missing")
        return "The public sample inventory exactly matches the synthetic-data allow-list.", {
            "sample_file_count": len(files),
            "unexpected_file_count": 0,
            "missing_file_count": 0,
        }

    check("configuration", configuration_check)
    check("public_sample_privacy", sample_check)

    acceptance_work_root = root / "artifacts"
    acceptance_work_root.mkdir(parents=True, exist_ok=True)
    temp = acceptance_work_root / f"acceptance-work-{os.getpid()}"
    if temp.exists():
        raise FileExistsError(f"Acceptance work directory already exists: {temp}")
    temp.mkdir()
    try:

        def first_run() -> Tuple[str, Dict[str, Any]]:
            artifacts, duration = _run_artifacts(root, config, temp / "run-1")
            expected = {
                "assessment": "trainercam.assessment-report",
                "feedback": "trainercam.feedback-summary",
                "review": "trainercam.session-review",
            }
            for name, format_name in expected.items():
                if artifacts[name].get("format") != format_name:
                    raise ValueError(f"Unexpected {name} artifact format")
                if artifacts[name].get("schema_version") != 1:
                    raise ValueError(f"Unexpected {name} artifact schema version")
            context["first_artifacts"] = artifacts
            context["first_duration"] = duration
            return "The public sample produced all three versioned result artifacts.", {
                "duration_seconds": round(duration, 4),
                "review_item_count": artifacts["review"]["item_count"],
            }

        def deterministic_run() -> Tuple[str, Dict[str, Any]]:
            first = context.get("first_artifacts")
            if not first:
                raise RuntimeError("First artifact run did not complete")
            second, duration = _run_artifacts(root, config, temp / "run-2")
            first_hashes = {name: canonical_hash(value) for name, value in first.items()}
            second_hashes = {name: canonical_hash(value) for name, value in second.items()}
            if first_hashes != second_hashes:
                raise ValueError("Repeated analysis produced different canonical artifacts")
            context["second_duration"] = duration
            context["artifact_hashes"] = first_hashes
            return "Two complete runs produced identical canonical artifacts.", {
                "duration_seconds": round(duration, 4),
                "canonical_sha256": first_hashes,
            }

        def regression_check() -> Tuple[str, Dict[str, Any]]:
            artifacts = context.get("first_artifacts")
            if not artifacts:
                raise RuntimeError("Artifact regression data is unavailable")
            report = artifacts["assessment"]
            expected = config["regression"]
            score = float(report["overall_score"])
            if abs(score - float(expected["expected_overall_score"])) > float(expected["score_tolerance"]):
                raise ValueError(f"Overall score regression: {score}")
            if int(report["alignment"]["path_length"]) != int(expected["expected_alignment_path_length"]):
                raise ValueError("Alignment path length changed")
            minimum_coverage = float(expected["minimum_required_joint_coverage"])
            for role in ("customer", "tutor"):
                quality = report["quality"][role]
                if not quality["subject_tracking"]["gate_passed"]:
                    raise ValueError(f"{role} subject tracking gate failed")
                if float(quality["required_joint_coverage"]) < minimum_coverage:
                    raise ValueError(f"{role} required joint coverage regressed")
            return "Score, alignment, tracking and required-joint coverage match the baseline.", {
                "overall_score": score,
                "alignment_path_length": report["alignment"]["path_length"],
                "customer_required_joint_coverage": report["quality"]["customer"]["required_joint_coverage"],
                "tutor_required_joint_coverage": report["quality"]["tutor"]["required_joint_coverage"],
            }

        def artifact_privacy_check() -> Tuple[str, Dict[str, Any]]:
            artifacts = context.get("first_artifacts")
            if not artifacts:
                raise RuntimeError("Artifact privacy data is unavailable")
            root_text = str(root).lower()
            absolute_values = [
                value
                for artifact in artifacts.values()
                for value in _walk_strings(artifact)
                if root_text in value.lower()
                or (len(value) > 2 and value[1:3] in (":\\", ":/"))
            ]
            if absolute_values:
                raise ValueError("Result artifacts contain absolute local paths")
            return "Result artifacts contain no absolute local paths.", {
                "absolute_path_count": 0
            }

        def boundary_check() -> Tuple[str, Dict[str, Any]]:
            artifacts = context.get("first_artifacts")
            if not artifacts:
                raise RuntimeError("Boundary evidence is unavailable")
            texts = (
                artifacts["feedback"].get("disclaimer", ""),
                artifacts["review"].get("disclaimer", ""),
            )
            if any(
                "diagnosis" not in text.lower()
                or not any(marker in text.lower() for marker in ("not", "does not"))
                for text in texts
            ):
                raise ValueError("A patient-facing artifact lacks the medical boundary statement")
            return "Patient-facing artifacts explicitly state that results are not a diagnosis.", {
                "checked_disclaimer_count": len(texts)
            }

        def performance_check() -> Tuple[str, Dict[str, Any]]:
            durations = [context.get("first_duration"), context.get("second_duration")]
            if any(value is None for value in durations):
                raise RuntimeError("Both artifact timings are required")
            maximum = float(config["performance"]["maximum_offline_artifact_seconds"])
            observed = max(float(value) for value in durations)
            if observed > maximum:
                raise ValueError(
                    f"Offline artifact run took {observed:.3f}s, over the {maximum:.3f}s budget"
                )
            return "Both offline sample runs completed within the engineering budget.", {
                "maximum_observed_seconds": round(observed, 4),
                "budget_seconds": maximum,
            }

        check("end_to_end_artifacts", first_run)
        check("deterministic_results", deterministic_run)
        check("regression_metrics", regression_check)
        check("artifact_path_privacy", artifact_privacy_check)
        check("medical_boundary", boundary_check)
        check("offline_performance_budget", performance_check)
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    passed_count = sum(check["status"] == "passed" for check in checks)
    report = {
        "format": REPORT_FORMAT,
        "schema_version": REPORT_SCHEMA_VERSION,
        "created_at": _created_at(),
        "source_revision": _git_revision(root),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "summary": {
            "passed": passed_count == len(checks),
            "check_count": len(checks),
            "passed_count": passed_count,
            "failed_count": len(checks) - passed_count,
        },
        "checks": checks,
        "limitations": {
            "clinical_validation": {
                "status": "not_performed",
                "required_before_patient_deployment": True,
            },
            "hardware_validation": {
                "status": "not_run_by_offline_acceptance",
                "required_for_target_room_and_device": True,
            },
        },
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TrainerCam engineering acceptance")
    parser.add_argument("--config", default=None, help="acceptance configuration JSON")
    parser.add_argument(
        "--output",
        default="artifacts/acceptance-report.json",
        help="machine-readable acceptance report path",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    report = run_acceptance(args.config, root)
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(
        f"TrainerCam acceptance: {'PASSED' if summary['passed'] else 'FAILED'} "
        f"({summary['passed_count']}/{summary['check_count']})"
    )
    print(f"Report: {output}")
    for check in report["checks"]:
        print(f"- {check['status'].upper():6} {check['id']}: {check['detail']}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
