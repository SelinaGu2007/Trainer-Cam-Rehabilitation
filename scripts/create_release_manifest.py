"""Create a SHA-256 manifest for verified TrainerCam release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_assignment(value: str) -> Tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected COMPONENT=PATH: {value}")
    component, path = value.split("=", 1)
    if not component.strip() or not path.strip():
        raise ValueError(f"Expected COMPONENT=PATH: {value}")
    return component.strip(), Path(path)


def _source_revision(project_root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def create_release_manifest(
    project_root: str | Path,
    acceptance_report: str | Path,
    roots: Iterable[Tuple[str, str | Path]] = (),
    files: Iterable[Tuple[str, str | Path]] = (),
) -> Dict[str, Any]:
    root = Path(project_root).resolve()
    acceptance_path = Path(acceptance_report)
    if not acceptance_path.is_absolute():
        acceptance_path = root / acceptance_path
    acceptance_path = acceptance_path.resolve()
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    if acceptance.get("format") != "trainercam.acceptance-report":
        raise ValueError("Unsupported acceptance report")
    if not acceptance.get("summary", {}).get("passed"):
        raise ValueError("Cannot manifest a release with failed acceptance")

    selected = []
    for component, value in roots:
        directory = Path(value)
        if not directory.is_absolute():
            directory = root / directory
        if not directory.is_dir():
            raise FileNotFoundError(f"Release root does not exist: {directory}")
        selected.extend((component, path) for path in sorted(directory.rglob("*")) if path.is_file())
    for component, value in files:
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            raise FileNotFoundError(f"Release file does not exist: {path}")
        selected.append((component, path))
    if not selected:
        raise ValueError("At least one release root or file is required")

    artifacts = []
    seen = set()
    for component, path in selected:
        resolved = path.resolve()
        key = (component, str(resolved).lower())
        if key in seen:
            continue
        seen.add(key)
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Release artifact is outside the project root: {resolved}") from exc
        artifacts.append(
            {
                "component": component,
                "path": relative,
                "size_bytes": resolved.stat().st_size,
                "sha256": _sha256(resolved),
            }
        )

    return {
        "format": "trainercam.release-manifest",
        "schema_version": 1,
        "created_at": _created_at(),
        "source_revision": _source_revision(root),
        "acceptance": {
            "report": acceptance_path.relative_to(root).as_posix(),
            "passed": True,
            "sha256": _sha256(acceptance_path),
        },
        "artifacts": artifacts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create TrainerCam release manifest")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--acceptance-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--root", action="append", default=[], metavar="COMPONENT=PATH")
    parser.add_argument("--file", action="append", default=[], metavar="COMPONENT=PATH")
    args = parser.parse_args(argv)
    project_root = Path(args.project_root or Path(__file__).resolve().parents[1]).resolve()
    manifest = create_release_manifest(
        project_root,
        args.acceptance_report,
        roots=[_parse_assignment(value) for value in args.root],
        files=[_parse_assignment(value) for value in args.file],
    )
    output = Path(args.output)
    if not output.is_absolute():
        output = project_root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Release manifest: {output}")
    print(f"Artifacts: {len(manifest['artifacts'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
