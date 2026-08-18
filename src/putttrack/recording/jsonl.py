"""Crash-tolerant append-only JSONL evidence capture."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from putttrack.contracts import (
    BaseRecord,
    RecordCodecError,
    UnsupportedSchemaVersion,
    canonical_json,
    record_from_dict,
)


class JsonlCaptureError(RuntimeError):
    """Base capture/reader failure."""


class JsonlCorruptionError(JsonlCaptureError):
    """Raised for corruption that cannot safely be treated as a tail partial."""


@dataclass(frozen=True)
class ReadResult:
    capture_index: int
    line_number: int
    raw_line: bytes
    raw_object: dict[str, Any] | None
    record: BaseRecord | None
    quarantine_reason: str | None = None
    unterminated: bool = False

    @property
    def accepted(self) -> bool:
        return self.record is not None and self.quarantine_reason is None


class AppendOnlyJsonlWriter:
    """One-line-at-a-time O_APPEND writer.

    The JSONL file is the canonical raw evidence. Parquet is a derived research
    export and can always be regenerated from this append-only source.
    """

    def __init__(self, path: str | os.PathLike[str], *, fsync: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fsync = fsync

    def append(self, record: BaseRecord | Mapping[str, Any]) -> int:
        payload = (canonical_json(record) + "\n").encode("utf-8")
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        fd = os.open(self.path, flags, 0o640)
        try:
            written = os.write(fd, payload)
            if written != len(payload):
                raise JsonlCaptureError(
                    f"short append to {self.path}: {written}/{len(payload)} bytes"
                )
            if self.fsync:
                os.fsync(fd)
        finally:
            os.close(fd)
        return written


def iter_jsonl(
    path: str | os.PathLike[str],
    *,
    tolerate_truncated_tail: bool = True,
    quarantine_decode_errors: bool = True,
) -> Iterator[ReadResult]:
    """Read JSONL in receive/capture order while retaining original bytes.

    A malformed final unterminated line is quarantined as a likely crash tail.
    Malformed middle lines are corruption by default because skipping them would
    silently hide evidence loss.
    """

    file_path = Path(path)
    data = file_path.read_bytes() if file_path.exists() else b""
    lines = data.splitlines(keepends=True)
    for index, raw_line in enumerate(lines):
        line_number = index + 1
        is_last = index == len(lines) - 1
        unterminated = not raw_line.endswith((b"\n", b"\r"))
        stripped = raw_line.strip()
        if not stripped:
            raise JsonlCorruptionError(f"blank JSONL record at line {line_number}")

        try:
            parsed = json.loads(stripped.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise RecordCodecError("JSONL record must be an object")
        except (UnicodeDecodeError, json.JSONDecodeError, RecordCodecError) as exc:
            if is_last and unterminated and tolerate_truncated_tail:
                yield ReadResult(
                    capture_index=index,
                    line_number=line_number,
                    raw_line=raw_line,
                    raw_object=None,
                    record=None,
                    quarantine_reason=f"truncated_tail:{type(exc).__name__}",
                    unterminated=True,
                )
                continue
            raise JsonlCorruptionError(
                f"invalid JSONL at line {line_number}: {exc}"
            ) from exc

        try:
            record = record_from_dict(parsed)
        except UnsupportedSchemaVersion as exc:
            yield ReadResult(
                capture_index=index,
                line_number=line_number,
                raw_line=raw_line,
                raw_object=parsed,
                record=None,
                quarantine_reason=f"unsupported_schema:{exc}",
                unterminated=unterminated,
            )
            continue
        except RecordCodecError as exc:
            if not quarantine_decode_errors:
                raise JsonlCorruptionError(
                    f"typed record decode failed at line {line_number}: {exc}"
                ) from exc
            yield ReadResult(
                capture_index=index,
                line_number=line_number,
                raw_line=raw_line,
                raw_object=parsed,
                record=None,
                quarantine_reason=f"decode_error:{exc}",
                unterminated=unterminated,
            )
            continue

        yield ReadResult(
            capture_index=index,
            line_number=line_number,
            raw_line=raw_line,
            raw_object=parsed,
            record=record,
            quarantine_reason=None,
            unterminated=unterminated,
        )


def load_records(path: str | os.PathLike[str]) -> list[BaseRecord]:
    return [result.record for result in iter_jsonl(path) if result.accepted and result.record]
