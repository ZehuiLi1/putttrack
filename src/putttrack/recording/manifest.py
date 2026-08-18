"""Immutable experiment run manifests and configuration provenance."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


class RunManifestError(ValueError):
    """Raised when a run manifest is incomplete, mutable or inconsistent."""


def _non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise RunManifestError(f"{name} must be a non-empty string")


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config_hashes(paths: Sequence[str | os.PathLike[str]]) -> dict[str, str]:
    return {str(Path(path)): sha256_file(path) for path in sorted(map(Path, paths))}


@dataclass(frozen=True, kw_only=True)
class RunManifest:
    """Enough provenance to reproduce and interpret one captured experiment."""

    manifest_schema_version: str = "1.0"
    run_id: str
    started_at_utc: str
    host: str
    platform: str
    git_sha: str
    python_version: str
    tool_version: str
    firmware_versions: dict[str, str]
    ncs_version: str | None
    board_identities: dict[str, dict[str, Any]]
    anchor_coordinates_m: dict[str, tuple[float, float, float]]
    ball_identity: dict[str, Any]
    experiment_condition: dict[str, Any]
    calibration_version: str | None
    camera_metadata: dict[str, Any]
    config_hashes: dict[str, str]
    command: tuple[str, ...] = ()
    environment: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        for name in (
            "manifest_schema_version",
            "run_id",
            "started_at_utc",
            "host",
            "platform",
            "git_sha",
            "python_version",
            "tool_version",
        ):
            _non_empty(name, getattr(self, name))
        try:
            parsed = datetime.fromisoformat(self.started_at_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RunManifestError("started_at_utc must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise RunManifestError("started_at_utc must include a timezone")
        if self.ncs_version is not None:
            _non_empty("ncs_version", self.ncs_version)
        if self.calibration_version is not None:
            _non_empty("calibration_version", self.calibration_version)

        coordinates: dict[str, tuple[float, float, float]] = {}
        for anchor_id, coordinate in self.anchor_coordinates_m.items():
            _non_empty("anchor_id", anchor_id)
            if len(coordinate) != 3:
                raise RunManifestError(
                    f"anchor {anchor_id!r} coordinate must contain x/y/z"
                )
            coordinates[anchor_id] = tuple(float(value) for value in coordinate)
        object.__setattr__(self, "anchor_coordinates_m", coordinates)
        object.__setattr__(self, "firmware_versions", dict(self.firmware_versions))
        object.__setattr__(
            self,
            "board_identities",
            {key: dict(value) for key, value in self.board_identities.items()},
        )
        object.__setattr__(self, "ball_identity", dict(self.ball_identity))
        object.__setattr__(self, "experiment_condition", dict(self.experiment_condition))
        object.__setattr__(self, "camera_metadata", dict(self.camera_metadata))
        object.__setattr__(self, "config_hashes", dict(self.config_hashes))
        object.__setattr__(self, "command", tuple(self.command))
        object.__setattr__(self, "environment", dict(self.environment))

    @classmethod
    def for_current_host(
        cls,
        *,
        run_id: str,
        git_sha: str,
        tool_version: str,
        firmware_versions: Mapping[str, str],
        ncs_version: str | None,
        board_identities: Mapping[str, Mapping[str, Any]],
        anchor_coordinates_m: Mapping[str, Sequence[float]],
        ball_identity: Mapping[str, Any],
        experiment_condition: Mapping[str, Any],
        calibration_version: str | None,
        camera_metadata: Mapping[str, Any] | None = None,
        config_hash_values: Mapping[str, str] | None = None,
        command: Sequence[str] = (),
        environment: Mapping[str, str] | None = None,
        notes: str = "",
    ) -> "RunManifest":
        return cls(
            run_id=run_id,
            started_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            host=socket.gethostname() or "unknown-host",
            platform=platform.platform(),
            git_sha=git_sha,
            python_version=sys.version.split()[0],
            tool_version=tool_version,
            firmware_versions=dict(firmware_versions),
            ncs_version=ncs_version,
            board_identities={key: dict(value) for key, value in board_identities.items()},
            anchor_coordinates_m={
                key: tuple(float(item) for item in value)
                for key, value in anchor_coordinates_m.items()
            },
            ball_identity=dict(ball_identity),
            experiment_condition=dict(experiment_condition),
            calibration_version=calibration_version,
            camera_metadata=dict(camera_metadata or {}),
            config_hashes=dict(config_hash_values or {}),
            command=tuple(command),
            environment=dict(environment or {}),
            notes=notes,
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["anchor_coordinates_m"] = {
            key: list(value) for key, value in self.anchor_coordinates_m.items()
        }
        result["command"] = list(self.command)
        return result

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def write_immutable_manifest(
    path: str | os.PathLike[str], manifest: RunManifest
) -> str:
    """Create a manifest and digest sidecar without ever replacing an existing run."""

    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (manifest.canonical_json() + "\n").encode("utf-8")
    digest = hashlib.sha256(payload.rstrip(b"\n")).hexdigest()

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(manifest_path, flags, 0o440)
    except FileExistsError as exc:
        raise RunManifestError(
            f"manifest already exists and is immutable: {manifest_path}"
        ) from exc
    try:
        written = os.write(fd, payload)
        if written != len(payload):
            raise RunManifestError("short manifest write")
        os.fsync(fd)
    finally:
        os.close(fd)

    digest_path = manifest_path.with_suffix(manifest_path.suffix + ".sha256")
    try:
        digest_fd = os.open(digest_path, flags, 0o440)
    except FileExistsError as exc:
        raise RunManifestError(f"digest sidecar already exists: {digest_path}") from exc
    try:
        sidecar = f"{digest}  {manifest_path.name}\n".encode("ascii")
        written = os.write(digest_fd, sidecar)
        if written != len(sidecar):
            raise RunManifestError("short digest sidecar write")
        os.fsync(digest_fd)
    finally:
        os.close(digest_fd)
    return digest


def load_manifest(
    path: str | os.PathLike[str], *, verify_digest: bool = True
) -> RunManifest:
    manifest_path = Path(path)
    raw_bytes = manifest_path.read_bytes()
    try:
        raw = raw_bytes.decode("utf-8")
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunManifestError(f"invalid manifest JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RunManifestError("manifest must be a JSON object")
    try:
        manifest = RunManifest(**data)
    except (TypeError, ValueError) as exc:
        raise RunManifestError(f"invalid manifest: {exc}") from exc

    if verify_digest:
        digest_path = manifest_path.with_suffix(manifest_path.suffix + ".sha256")
        if not digest_path.exists():
            raise RunManifestError(f"manifest digest sidecar missing: {digest_path}")
        expected_payload = (manifest.canonical_json() + "\n").encode("utf-8")
        if raw_bytes != expected_payload:
            raise RunManifestError("manifest is non-canonical or was modified")
        expected = digest_path.read_text(encoding="ascii").split()[0]
        actual = hashlib.sha256(manifest.canonical_json().encode("utf-8")).hexdigest()
        if actual != expected:
            raise RunManifestError(
                f"manifest digest mismatch: expected {expected}, got {actual}"
            )
    return manifest
