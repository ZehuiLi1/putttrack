"""Offline research-ball dataset loading, metadata validation and analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from putttrack.motion.features import (
    MotionWindowFeatures,
    extract_window_features,
    provisional_generic_motion_check,
)
from putttrack.tag import MotionRecord


DATASET_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class EpisodeMetadata:
    """Physical metadata that must survive independently of a Tag capture."""

    episode_id: str
    capture: str
    label: str
    session: str | None = None
    trial: str | None = None
    core_revision: str | None = None
    shell_revision: str | None = None
    mass_g: float | None = None
    surface: str | None = None
    orientation: str | None = None
    strength: str | None = None
    video_ref: str | None = None
    operator: str | None = None
    notes: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "EpisodeMetadata":
        required = ("episode_id", "capture", "label")
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            raise ValueError(f"episode metadata missing required fields: {missing}")
        mass = payload.get("mass_g")
        if mass is not None:
            mass = float(mass)
            if mass <= 0:
                raise ValueError("mass_g must be positive when provided")
        return cls(
            episode_id=str(payload["episode_id"]).strip(),
            capture=str(payload["capture"]).strip(),
            label=str(payload["label"]).strip().lower(),
            session=_optional_text(payload.get("session")),
            trial=_optional_text(payload.get("trial")),
            core_revision=_optional_text(payload.get("core_revision")),
            shell_revision=_optional_text(payload.get("shell_revision")),
            mass_g=mass,
            surface=_optional_text(payload.get("surface")),
            orientation=_optional_text(payload.get("orientation")),
            strength=_optional_text(payload.get("strength")),
            video_ref=_optional_text(payload.get("video_ref")),
            operator=_optional_text(payload.get("operator")),
            notes=_optional_text(payload.get("notes")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CaptureData:
    path: Path
    records: tuple[MotionRecord, ...]
    first_status: Mapping[str, Any] | None
    final_status: Mapping[str, Any] | None
    embedded_labels: tuple[str, ...]


@dataclass(frozen=True)
class EpisodeAnalysis:
    metadata: EpisodeMetadata
    capture_path: str
    device_id: str | None
    boot_id: str | None
    firmware_version: str | None
    features: MotionWindowFeatures
    diagnostic_state: str
    diagnostic_passed: bool
    quality_status: str
    quality_issues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "capture_path": self.capture_path,
            "device_id": self.device_id,
            "boot_id": self.boot_id,
            "firmware_version": self.firmware_version,
            "features": self.features.to_dict(),
            "diagnostic_state": self.diagnostic_state,
            "diagnostic_passed": self.diagnostic_passed,
            "quality_status": self.quality_status,
            "quality_issues": list(self.quality_issues),
        }

    def to_flat_dict(self) -> dict[str, Any]:
        row = self.metadata.to_dict()
        row.update(
            {
                "capture_path": self.capture_path,
                "device_id": self.device_id,
                "boot_id": self.boot_id,
                "firmware_version": self.firmware_version,
                "diagnostic_state": self.diagnostic_state,
                "diagnostic_passed": self.diagnostic_passed,
                "quality_status": self.quality_status,
                "quality_issues": ";".join(self.quality_issues),
            }
        )
        row.update(self.features.to_dict())
        return row


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def motion_from_json(payload: Mapping[str, Any]) -> MotionRecord:
    """Build a strict MotionRecord from one canonical capture JSON object."""

    return MotionRecord(
        protocol_version=int(payload["protocol_version"]),
        sequence=int(payload["sequence"]),
        source_monotonic_us=int(payload["source_monotonic_us"]),
        adxl367_valid=bool(payload["adxl367_valid"]),
        bmi270_valid=bool(payload["bmi270_valid"]),
        adxl367_accel_micro_ms2=tuple(
            int(value) for value in payload["adxl367_accel_micro_ms2"]
        ),
        bmi270_accel_micro_ms2=tuple(
            int(value) for value in payload["bmi270_accel_micro_ms2"]
        ),
        bmi270_gyro_micro_rads=tuple(
            int(value) for value in payload["bmi270_gyro_micro_rads"]
        ),
        sensor_error_bits=int(payload["sensor_error_bits"]),
    )


def read_capture(path: Path) -> CaptureData:
    """Read one existing JSONL capture without needing any connected hardware."""

    records: list[MotionRecord] = []
    first_status: Mapping[str, Any] | None = None
    final_status: Mapping[str, Any] | None = None
    labels: set[str] = set()

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")

        record_type = payload.get("record_type")
        if record_type == "tag_motion":
            records.append(motion_from_json(payload))
        elif record_type == "tag_status" and first_status is None:
            first_status = payload
        elif record_type == "tag_status_final":
            final_status = payload

        label = payload.get("episode_label")
        if isinstance(label, str) and label.strip():
            labels.add(label.strip().lower())

    if len(records) < 2:
        raise ValueError(f"{path}: capture must contain at least two tag_motion records")
    return CaptureData(
        path=path,
        records=tuple(records),
        first_status=first_status,
        final_status=final_status,
        embedded_labels=tuple(sorted(labels)),
    )


def load_dataset_manifest(path: Path) -> tuple[str, tuple[EpisodeMetadata, ...]]:
    """Load a versioned manifest whose capture paths are relative to the manifest."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("dataset manifest must be a JSON object")
    if int(payload.get("schema_version", -1)) != DATASET_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported dataset schema_version {payload.get('schema_version')}; "
            f"expected {DATASET_SCHEMA_VERSION}"
        )
    dataset_id = str(payload.get("dataset_id", "")).strip()
    if not dataset_id:
        raise ValueError("dataset_id is required")
    raw_episodes = payload.get("episodes")
    if not isinstance(raw_episodes, list) or not raw_episodes:
        raise ValueError("episodes must be a non-empty list")

    defaults = payload.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("defaults must be a JSON object")

    episodes: list[EpisodeMetadata] = []
    seen_ids: set[str] = set()
    seen_capture_paths: set[str] = set()
    for index, raw_episode in enumerate(raw_episodes):
        if not isinstance(raw_episode, dict):
            raise ValueError(f"episodes[{index}] must be a JSON object")
        merged = {**defaults, **raw_episode}
        episode = EpisodeMetadata.from_mapping(merged)
        if episode.episode_id in seen_ids:
            raise ValueError(f"duplicate episode_id: {episode.episode_id}")
        capture_key = str((path.parent / episode.capture).resolve())
        if capture_key in seen_capture_paths:
            raise ValueError(f"capture reused by multiple episodes: {episode.capture}")
        seen_ids.add(episode.episode_id)
        seen_capture_paths.add(capture_key)
        episodes.append(episode)
    return dataset_id, tuple(episodes)


def analyze_episode(manifest_path: Path, metadata: EpisodeMetadata) -> EpisodeAnalysis:
    capture_path = (manifest_path.parent / metadata.capture).resolve()
    capture = read_capture(capture_path)
    features = extract_window_features(capture.records)
    diagnostic = provisional_generic_motion_check(features)

    hard_failures: list[str] = []
    warnings: list[str] = []
    if features.sequence_gaps:
        hard_failures.append("sequence_gaps")
    if features.valid_fraction < 1.0:
        hard_failures.append("invalid_sensor_samples")
    if len(capture.embedded_labels) > 1:
        hard_failures.append("multiple_embedded_labels")
    elif capture.embedded_labels and capture.embedded_labels[0] != metadata.label:
        hard_failures.append("manifest_capture_label_mismatch")

    if features.adxl367_clip_samples:
        warnings.append("adxl367_clipping")
    if features.bmi270_accel_clip_samples:
        warnings.append("bmi270_accel_clipping")
    if features.bmi270_gyro_clip_samples:
        warnings.append("bmi270_gyro_clipping")

    quality_issues = tuple(hard_failures + warnings)
    quality_status = "FAIL" if hard_failures else "WARN" if warnings else "PASS"
    status = capture.final_status or capture.first_status or {}

    return EpisodeAnalysis(
        metadata=metadata,
        capture_path=str(capture_path),
        device_id=_optional_text(status.get("device_id")),
        boot_id=_optional_text(status.get("boot_id")),
        firmware_version=_optional_text(status.get("firmware_version")),
        features=features,
        diagnostic_state=diagnostic.state,
        diagnostic_passed=diagnostic.passed,
        quality_status=quality_status,
        quality_issues=quality_issues,
    )


def analyze_dataset(
    manifest_path: Path,
) -> tuple[str, tuple[EpisodeAnalysis, ...]]:
    dataset_id, episodes = load_dataset_manifest(manifest_path)
    analyses = tuple(analyze_episode(manifest_path, episode) for episode in episodes)
    return dataset_id, analyses


def build_quality_report(
    dataset_id: str, analyses: Sequence[EpisodeAnalysis]
) -> dict[str, Any]:
    by_label: dict[str, int] = {}
    status_counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    clipping = {
        "adxl367": 0,
        "bmi270_accel": 0,
        "bmi270_gyro": 0,
    }
    for analysis in analyses:
        by_label[analysis.metadata.label] = by_label.get(analysis.metadata.label, 0) + 1
        status_counts[analysis.quality_status] += 1
        if analysis.features.adxl367_clip_samples:
            clipping["adxl367"] += 1
        if analysis.features.bmi270_accel_clip_samples:
            clipping["bmi270_accel"] += 1
        if analysis.features.bmi270_gyro_clip_samples:
            clipping["bmi270_gyro"] += 1

    return {
        "dataset_id": dataset_id,
        "episodes": len(analyses),
        "quality_status_counts": status_counts,
        "episodes_by_label": dict(sorted(by_label.items())),
        "episodes_with_clipping": clipping,
        "failed_episode_ids": [
            item.metadata.episode_id for item in analyses if item.quality_status == "FAIL"
        ],
        "warning_episode_ids": [
            item.metadata.episode_id for item in analyses if item.quality_status == "WARN"
        ],
        "note": (
            "Quality PASS validates capture integrity and metadata consistency only; "
            "it does not validate impact/rolling/pickup semantics."
        ),
    }
