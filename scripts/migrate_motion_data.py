#!/usr/bin/env python3
"""Convert a legacy output2.txt session to TrainerCam motion-session v1."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "test_exe"))

from motion_data import migrate_legacy_session  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_folder", help="Folder containing output2.txt")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing v1 files")
    args = parser.parse_args()
    count = migrate_legacy_session(args.session_folder, overwrite=args.overwrite)
    print(f"Migrated {count} frames in {Path(args.session_folder).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
