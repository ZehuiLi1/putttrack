"""Append-only capture, immutable manifests and research export."""

from .jsonl import (
    AppendOnlyJsonlWriter,
    JsonlCaptureError,
    JsonlCorruptionError,
    ReadResult,
    iter_jsonl,
    load_records,
)
from .manifest import (
    RunManifest,
    RunManifestError,
    config_hashes,
    load_manifest,
    write_immutable_manifest,
)
from .parquet import ParquetDependencyError, export_jsonl_to_parquet

__all__ = [
    "AppendOnlyJsonlWriter",
    "JsonlCaptureError",
    "JsonlCorruptionError",
    "ParquetDependencyError",
    "ReadResult",
    "RunManifest",
    "RunManifestError",
    "config_hashes",
    "export_jsonl_to_parquet",
    "iter_jsonl",
    "load_manifest",
    "load_records",
    "write_immutable_manifest",
]
