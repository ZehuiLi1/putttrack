#!/usr/bin/env python3
"""Export canonical JSONL evidence into derived Parquet files by record type."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.recording import ParquetDependencyError, export_jsonl_to_parquet  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        outputs = export_jsonl_to_parquet(args.jsonl, args.output_dir)
    except ParquetDependencyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"outputs": [str(path) for path in outputs]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
