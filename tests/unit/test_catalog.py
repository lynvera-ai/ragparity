import json
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "scenario,status,exit_code,code",
    [
        ("synchronized", "PASS", 0, "CHUNKS_SYNCED"),
        ("stale", "FAIL", 1, "VERSION_MISMATCH"),
        ("missing-chunk", "FAIL", 1, "MISSING_CHUNK"),
        ("deleted", "FAIL", 1, "DELETED_PRESENT"),
        ("wrong-answer", "FAIL", 1, "CLAIM_VALUE_MISMATCH"),
        ("partial", "INCONCLUSIVE", 3, "SNAPSHOT_INCOMPLETE"),
    ],
)
def test_synthetic_catalog_pipeline(scenario, status, exit_code, code):
    result = subprocess.run(
        [sys.executable, "examples/catalog/pipeline.py", "--scenario", scenario],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == exit_code, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == status
    assert code in report["counts"]
