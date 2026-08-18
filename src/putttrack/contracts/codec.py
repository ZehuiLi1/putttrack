"""Deterministic JSON encoding and decoding for canonical evidence records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from typing import Any, Mapping

from .records import BaseRecord, RECORD_CLASS_BY_TYPE
from .versioning import UnsupportedSchemaVersion, validate_schema_version


class RecordCodecError(ValueError):
    """Raised when a wire record cannot be decoded without ambiguity."""


class UnknownRecordType(RecordCodecError):
    """Raised when ``record_type`` has no registered typed contract."""


def _json_ready(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def record_to_dict(record: BaseRecord) -> dict[str, Any]:
    """Return the stable wire representation of a typed record.

    Unknown additive fields decoded from a compatible minor version are kept in
    ``extensions`` in memory and emitted at their original top-level location.
    """

    result: dict[str, Any] = {"record_type": record.record_type}
    for item in fields(record):
        if item.name == "extensions":
            continue
        result[item.name] = _json_ready(getattr(record, item.name))
    for key, value in record.extensions.items():
        if key in result:
            raise RecordCodecError(f"extension field collides with canonical field {key!r}")
        result[key] = _json_ready(value)
    return result


def record_from_dict(data: Mapping[str, Any]) -> BaseRecord:
    """Decode one typed record, quarantining unknown major versions upstream."""

    if not isinstance(data, Mapping):
        raise RecordCodecError("record must be a JSON object")
    record_type = data.get("record_type")
    if not isinstance(record_type, str) or not record_type:
        raise RecordCodecError("record_type is required")
    try:
        cls = RECORD_CLASS_BY_TYPE[record_type]
    except KeyError as exc:
        raise UnknownRecordType(f"unknown record_type {record_type!r}") from exc

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str):
        raise RecordCodecError("schema_version is required")
    validate_schema_version(schema_version)

    canonical_names = {item.name for item in fields(cls)}
    kwargs = {
        key: value
        for key, value in data.items()
        if key in canonical_names and key != "extensions"
    }
    unknown = {
        key: value
        for key, value in data.items()
        if key not in canonical_names and key != "record_type"
    }
    existing_extensions = data.get("extensions")
    if isinstance(existing_extensions, Mapping):
        unknown = {**existing_extensions, **unknown}
    kwargs["extensions"] = unknown

    try:
        return cls(**kwargs)
    except UnsupportedSchemaVersion:
        raise
    except (TypeError, ValueError) as exc:
        raise RecordCodecError(f"invalid {record_type} record: {exc}") from exc


def canonical_json(value: BaseRecord | Mapping[str, Any]) -> str:
    payload = record_to_dict(value) if isinstance(value, BaseRecord) else _json_ready(dict(value))
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def record_digest(record: BaseRecord | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()
