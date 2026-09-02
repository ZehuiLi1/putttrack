#!/usr/bin/env python3
"""Exact-tree verifier for PuttTrack gameplay and evidence foundation."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
PYTHON = sys.executable
ENV = {**os.environ, "PYTHONPATH": str(SRC)}


def run(name: str, command: list[str], report: list[dict[str, Any]]) -> None:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=ENV,
        text=True,
        capture_output=True,
        check=False,
    )
    report.append(
        {
            "name": name,
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.returncode == 0,
        }
    )
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def require_capture_outputs(run_dir: Path, name: str, report: list[dict[str, Any]]) -> None:
    expected = [
        run_dir / "manifest.json",
        run_dir / "manifest.json.sha256",
        run_dir / "raw_serial.log",
        run_dir / "ranges.jsonl",
        run_dir / "capture_summary.json",
    ]
    missing = [str(path) for path in expected if not path.exists()]
    report.append({"name": name, "passed": not missing, "missing": missing})
    if missing:
        raise RuntimeError(f"phase0 capture outputs missing: {missing}")


def main() -> int:
    report: list[dict[str, Any]] = []
    try:
        run(
            "unit_tests",
            [PYTHON, "-m", "unittest", "discover", "-s", "tests", "-v"],
            report,
        )
        run("gameplay_simulator", [PYTHON, "simulator/demo_gameplay.py"], report)
        run(
            "deterministic_replay",
            [PYTHON, "tools/replay_run.py", "experiments/evidence_replay_example"],
            report,
        )
        with tempfile.TemporaryDirectory() as temp:
            run(
                "phase0_vendor_fixture_capture",
                [
                    PYTHON,
                    "tools/capture_cs.py",
                    "--input",
                    "experiments/phase0_cs/fixtures/bbo_vendor_smoke.log",
                    "--run-root",
                    temp,
                    "--run-id",
                    "verify-cs-vendor",
                    "--anchor-id",
                    "A",
                    "--reflector-id",
                    "ball-reference",
                    "--truth-distance-m",
                    "1.0",
                    "--condition",
                    "fixture",
                    "--firmware-version",
                    "vendor-fixture",
                    "--ncs-version",
                    "3.0.2-fixture",
                    "--anchor-config",
                    "configs/anchors/phase0.example.json",
                    "--max-records",
                    "2",
                ],
                report,
            )
            vendor_run = Path(temp) / "verify-cs-vendor"
            require_capture_outputs(vendor_run, "phase0_vendor_capture_outputs", report)
            vendor_summary = json.loads(
                (vendor_run / "capture_summary.json").read_text(encoding="utf-8")
            )
            vendor_fallback_ok = (
                vendor_summary["captured_records"] == 2
                and vendor_summary["source_identity_complete"] is False
                and vendor_summary["device_boot_records"] == 0
            )
            report.append(
                {
                    "name": "phase0_vendor_fallback_identity",
                    "passed": vendor_fallback_ok,
                    "summary": vendor_summary,
                }
            )
            if not vendor_fallback_ok:
                raise RuntimeError("vendor fixture source-identity fallback changed unexpectedly")

            run(
                "phase0_source_fixture_capture",
                [
                    PYTHON,
                    "tools/capture_cs.py",
                    "--input",
                    "experiments/phase0_cs/fixtures/putttrack_source_telemetry.log",
                    "--run-root",
                    temp,
                    "--run-id",
                    "verify-cs-source",
                    "--anchor-id",
                    "A",
                    "--reflector-id",
                    "ball-reference",
                    "--truth-distance-m",
                    "1.0",
                    "--condition",
                    "source-telemetry-fixture",
                    "--firmware-version",
                    "putttrack-source-fixture",
                    "--ncs-version",
                    "source-fixture",
                    "--anchor-config",
                    "configs/anchors/phase0.example.json",
                    "--max-records",
                    "2",
                ],
                report,
            )
            source_run = Path(temp) / "verify-cs-source"
            require_capture_outputs(source_run, "phase0_source_capture_outputs", report)
            source_summary = json.loads(
                (source_run / "capture_summary.json").read_text(encoding="utf-8")
            )
            source_identity_ok = (
                source_summary["captured_records"] == 2
                and source_summary["source_identity_complete"] is True
                and source_summary["device_boot_records"] == 2
                and source_summary["device_timestamp_records"] == 2
                and source_summary["device_sequence_records"] == 2
                and source_summary["observed_source_boot_ids"] == ["boot-a1b2c3d4"]
            )
            report.append(
                {
                    "name": "phase0_source_identity_complete",
                    "passed": source_identity_ok,
                    "summary": source_summary,
                }
            )
            if not source_identity_ok:
                raise RuntimeError("structured source telemetry identity was not preserved")

        modules = [
            "putttrack.contracts",
            "putttrack.recording",
            "putttrack.evidence",
            "putttrack.cs",
            "putttrack.motion",
            "putttrack.tag",
            "putttrack.gameplay",
            "putttrack.venue",
        ]
        for module in modules:
            __import__(module)
        report.append({"name": "import_checks", "passed": True, "modules": modules})

        pyarrow_available = importlib.util.find_spec("pyarrow") is not None
        report.append(
            {
                "name": "parquet_capability",
                "passed": True,
                "pyarrow_installed": pyarrow_available,
                "note": (
                    "actual pyarrow export is available"
                    if pyarrow_available
                    else "optional pyarrow is not installed; exporter path is exercised by the fake-backend unit test"
                ),
            }
        )
    except Exception as exc:
        summary = {
            "status": "FAIL",
            "python": sys.version.split()[0],
            "error": f"{type(exc).__name__}: {exc}",
            "checks": report,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1

    summary = {
        "status": "PASS",
        "python": sys.version.split()[0],
        "checks_passed": sum(1 for item in report if item.get("passed")),
        "checks": report,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
