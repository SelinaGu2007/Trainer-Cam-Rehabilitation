import hashlib
import json
import shutil
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import create_release_manifest  # noqa: E402
import run_acceptance  # noqa: E402


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = PROJECT_ROOT / ".test-acceptance" / self._testMethodName
        self.temporary.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temporary, ignore_errors=True)

    def test_canonical_hash_ignores_creation_timestamp(self):
        first = {"created_at": "one", "value": [1, {"created_at": "two", "x": 3}]}
        second = {"created_at": "changed", "value": [1, {"created_at": "changed", "x": 3}]}
        self.assertEqual(
            run_acceptance.canonical_hash(first),
            run_acceptance.canonical_hash(second),
        )

    def test_public_engineering_acceptance_passes_with_explicit_limitations(self):
        report = run_acceptance.run_acceptance(project_root=PROJECT_ROOT)
        self.assertEqual(report["format"], "trainercam.acceptance-report")
        self.assertTrue(report["summary"]["passed"])
        self.assertEqual(report["summary"]["failed_count"], 0)
        self.assertGreaterEqual(report["summary"]["check_count"], 8)
        self.assertEqual(
            report["limitations"]["clinical_validation"]["status"],
            "not_performed",
        )
        self.assertEqual(
            report["limitations"]["hardware_validation"]["status"],
            "not_run_by_offline_acceptance",
        )

    def test_release_manifest_hashes_only_verified_project_artifacts(self):
        acceptance_path = self.temporary / "acceptance.json"
        acceptance_path.write_text(
            json.dumps(
                {
                    "format": "trainercam.acceptance-report",
                    "summary": {"passed": True},
                }
            ),
            encoding="utf-8",
        )
        bundle = self.temporary / "bundle"
        bundle.mkdir()
        artifact = bundle / "client.bin"
        artifact.write_bytes(b"trainercam-release-test")
        manifest = create_release_manifest.create_release_manifest(
            PROJECT_ROOT,
            acceptance_path,
            roots=[("customer-client", bundle)],
        )
        self.assertEqual(manifest["format"], "trainercam.release-manifest")
        self.assertTrue(manifest["acceptance"]["passed"])
        self.assertEqual(len(manifest["artifacts"]), 1)
        self.assertEqual(
            manifest["artifacts"][0]["sha256"],
            hashlib.sha256(artifact.read_bytes()).hexdigest(),
        )

    def test_release_manifest_includes_hashed_robustness_evidence(self):
        acceptance_path = self.temporary / "acceptance.json"
        acceptance_path.write_text(
            json.dumps(
                {
                    "format": "trainercam.acceptance-report",
                    "summary": {"passed": True},
                }
            ),
            encoding="utf-8",
        )
        bundle = self.temporary / "bundle"
        bundle.mkdir()
        (bundle / "client.bin").write_bytes(b"release")
        robustness = self.temporary / "robustness.json"
        robustness.write_text(
            json.dumps(
                {
                    "format": "trainercam.robustness-report",
                    "summary": {"passed": True},
                }
            ),
            encoding="utf-8",
        )
        manifest = create_release_manifest.create_release_manifest(
            PROJECT_ROOT,
            acceptance_path,
            roots=[("customer-client", bundle)],
            files=[("robustness-evidence", robustness)],
        )
        evidence = next(
            item for item in manifest["artifacts"]
            if item["component"] == "robustness-evidence"
        )
        self.assertEqual(evidence["sha256"], hashlib.sha256(robustness.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
