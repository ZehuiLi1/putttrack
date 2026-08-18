"""Schema-version compatibility rules for PuttTrack evidence records."""

from __future__ import annotations

from dataclasses import dataclass


CURRENT_SCHEMA_VERSION = "1.0"
SUPPORTED_MAJOR_VERSIONS = frozenset({1})


class SchemaVersionError(ValueError):
    """Base error for malformed or unsupported record schema versions."""


class UnsupportedSchemaVersion(SchemaVersionError):
    """Raised when a record uses an unknown incompatible major version."""


@dataclass(frozen=True, order=True)
class SchemaVersion:
    """Semantic schema version with major/minor compatibility semantics.

    Additive optional fields may be introduced within one major version. Any
    unit or meaning change requires a new major version because silently
    interpreting such a record would corrupt evidence.
    """

    major: int
    minor: int

    @classmethod
    def parse(cls, value: str) -> "SchemaVersion":
        if not isinstance(value, str) or not value.strip():
            raise SchemaVersionError("schema_version must be a non-empty string")
        parts = value.split(".")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise SchemaVersionError(
                f"schema_version must use '<major>.<minor>', got {value!r}"
            )
        return cls(int(parts[0]), int(parts[1]))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"

    def assert_supported(self) -> None:
        if self.major not in SUPPORTED_MAJOR_VERSIONS:
            raise UnsupportedSchemaVersion(
                f"unsupported schema major {self.major}; supported: "
                f"{sorted(SUPPORTED_MAJOR_VERSIONS)}"
            )


def validate_schema_version(value: str) -> SchemaVersion:
    version = SchemaVersion.parse(value)
    version.assert_supported()
    return version
