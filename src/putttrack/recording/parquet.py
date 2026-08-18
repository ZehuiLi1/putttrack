"""Derived Parquet export for research workflows.

JSONL remains the canonical crash-tolerant evidence source. Parquet files are
reproducible derivatives grouped by record type.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from putttrack.contracts import record_to_dict

from .jsonl import iter_jsonl


class ParquetDependencyError(RuntimeError):
    """Raised when the optional research Parquet dependency is unavailable."""


def _load_pyarrow():
    try:
        import pyarrow as pa  # type: ignore[import-not-found]
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ParquetDependencyError(
            "Parquet export requires the optional 'research' dependency: "
            "pip install '.[research]'"
        ) from exc
    return pa, pq


def _normalise_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {**raw, "raw_json": json.dumps(raw, sort_keys=True, separators=(",", ":"))}


def export_jsonl_to_parquet(
    jsonl_path: str | Path,
    output_dir: str | Path,
) -> list[Path]:
    """Export accepted records to one Parquet file per record type.

    Quarantined or partial records remain in the canonical JSONL and are not
    silently presented as valid typed research rows.
    """

    pa, pq = _load_pyarrow()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in iter_jsonl(jsonl_path):
        if not result.accepted or result.record is None:
            continue
        raw = record_to_dict(result.record)
        grouped[result.record.record_type].append(_normalise_row(raw))

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for record_type, rows in sorted(grouped.items()):
        table = pa.Table.from_pylist(rows)
        output = destination / f"{record_type}.parquet"
        pq.write_table(table, output, compression="zstd")
        outputs.append(output)
    return outputs
