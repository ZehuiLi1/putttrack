from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from putttrack.contracts import RangeObservation, canonical_json, record_to_dict
from putttrack.recording import (
    AppendOnlyJsonlWriter,
    JsonlCorruptionError,
    ParquetDependencyError,
    RunManifest,
    RunManifestError,
    export_jsonl_to_parquet,
    iter_jsonl,
    load_manifest,
    write_immutable_manifest,
)


class RecordingTests(unittest.TestCase):
    def range_record(self, sequence: int) -> RangeObservation:
        return RangeObservation(
            event_id=f"range-{sequence}",
            event_type="cs.range_observed",
            source_device_id="anchor-A",
            source_boot_id="boot-1",
            sequence=sequence,
            source_monotonic_ns=sequence * 100,
            edge_received_ns=sequence * 100 + 10,
            trace_id="run:test",
            ball_id="ball-1",
            anchor_id="anchor-A",
            distance_ifft_m=float(sequence),
        )

    def manifest(self) -> RunManifest:
        return RunManifest(
            run_id="run-1",
            started_at_utc="2026-08-18T00:00:00Z",
            host="host",
            platform="test",
            git_sha="abc123",
            python_version="3.13.5",
            tool_version="test-1",
            firmware_versions={"anchor-A": "fw-1"},
            ncs_version="3.0.2",
            board_identities={"anchor-A": {"board": "Bbo"}},
            anchor_coordinates_m={"anchor-A": (0.0, 0.0, 1.0)},
            ball_identity={"ball_id": "ball-1"},
            experiment_condition={"truth_distance_m": 1.0},
            calibration_version="uncalibrated",
            camera_metadata={},
            config_hashes={"anchors.json": "deadbeef"},
        )

    def test_append_only_capture_preserves_receive_order_and_raw(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "records.jsonl"
            writer = AppendOnlyJsonlWriter(path)
            writer.append(self.range_record(1))
            writer.append(self.range_record(2))
            results = list(iter_jsonl(path))
            self.assertEqual([r.record.sequence for r in results if r.record], [1, 2])
            self.assertTrue(all(r.raw_line.endswith(b"\n") for r in results))
            self.assertEqual(results[0].capture_index, 0)

    def test_partial_final_record_is_quarantined_not_silently_lost(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "records.jsonl"
            path.write_bytes(
                (canonical_json(self.range_record(1)) + "\n").encode()
                + b'{"record_type":"range_observation"'
            )
            results = list(iter_jsonl(path))
            self.assertTrue(results[0].accepted)
            self.assertFalse(results[1].accepted)
            self.assertIn("truncated_tail", results[1].quarantine_reason or "")

    def test_corrupt_middle_record_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "records.jsonl"
            path.write_text(
                canonical_json(self.range_record(1))
                + "\nnot-json\n"
                + canonical_json(self.range_record(2))
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(JsonlCorruptionError):
                list(iter_jsonl(path))

    def test_unknown_major_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "records.jsonl"
            raw = record_to_dict(self.range_record(1))
            raw["schema_version"] = "9.0"
            path.write_text(json.dumps(raw) + "\n", encoding="utf-8")
            result = list(iter_jsonl(path))[0]
            self.assertFalse(result.accepted)
            self.assertIn("unsupported_schema", result.quarantine_reason or "")

    def test_manifest_is_immutable_and_digest_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            digest = write_immutable_manifest(path, self.manifest())
            self.assertEqual(load_manifest(path).digest(), digest)
            with self.assertRaises(RunManifestError):
                write_immutable_manifest(path, self.manifest())
            path.write_text(path.read_text() + " ", encoding="utf-8")
            with self.assertRaises(RunManifestError):
                load_manifest(path)

    def test_parquet_dependency_error_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "records.jsonl"
            AppendOnlyJsonlWriter(path).append(self.range_record(1))
            if "pyarrow" not in sys.modules:
                with self.assertRaises(ParquetDependencyError):
                    export_jsonl_to_parquet(path, Path(temp) / "parquet")

    def test_parquet_export_groups_records_with_optional_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "records.jsonl"
            AppendOnlyJsonlWriter(path).append(self.range_record(1))

            class FakeTable:
                @staticmethod
                def from_pylist(rows):
                    return rows

            pa = types.ModuleType("pyarrow")
            pa.Table = FakeTable
            pq = types.ModuleType("pyarrow.parquet")

            def write_table(table, output, compression=None):
                Path(output).write_text(json.dumps(table), encoding="utf-8")

            pq.write_table = write_table
            prior = {name: sys.modules.get(name) for name in ("pyarrow", "pyarrow.parquet")}
            try:
                sys.modules["pyarrow"] = pa
                sys.modules["pyarrow.parquet"] = pq
                outputs = export_jsonl_to_parquet(path, Path(temp) / "parquet")
            finally:
                for name, value in prior.items():
                    if value is None:
                        sys.modules.pop(name, None)
                    else:
                        sys.modules[name] = value
            self.assertEqual(len(outputs), 1)
            self.assertTrue(outputs[0].exists())


if __name__ == "__main__":
    unittest.main()
