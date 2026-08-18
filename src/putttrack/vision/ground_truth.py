from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .calibration import GroundPlaneCalibration
from .sync import CameraTimeMap


class GroundTruthError(ValueError):
    """Raised when a ground-truth annotation is incomplete or invalid."""


@dataclass(frozen=True)
class PixelAnnotation:
    frame_id: str
    video_time_ns: int
    u_px: float
    v_px: float
    confidence: float = 1.0
    track_id: str = "ball"
    source: str = "manual"

    def __post_init__(self) -> None:
        if not self.frame_id:
            raise GroundTruthError("frame_id is required")
        if self.video_time_ns < 0:
            raise GroundTruthError("video_time_ns must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise GroundTruthError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class GroundTruthObservation:
    frame_id: str
    video_time_ns: int
    edge_time_ns: int | None
    world_x_m: float
    world_y_m: float
    confidence: float
    track_id: str
    source: str
    camera_id: str
    world_frame: str
    calibration_id: str

    def to_row(self) -> dict[str, object]:
        return {
            "frame_id": self.frame_id,
            "video_time_ns": self.video_time_ns,
            "edge_time_ns": "" if self.edge_time_ns is None else self.edge_time_ns,
            "world_x_m": f"{self.world_x_m:.9f}",
            "world_y_m": f"{self.world_y_m:.9f}",
            "confidence": f"{self.confidence:.6f}",
            "track_id": self.track_id,
            "source": self.source,
            "camera_id": self.camera_id,
            "world_frame": self.world_frame,
            "calibration_id": self.calibration_id,
        }


def read_pixel_annotations(path: str | Path) -> list[PixelAnnotation]:
    annotations: list[PixelAnnotation] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"frame_id", "video_time_ns", "u_px", "v_px"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise GroundTruthError(f"annotation CSV requires columns: {sorted(required)}")
        for row in reader:
            annotations.append(
                PixelAnnotation(
                    frame_id=row["frame_id"],
                    video_time_ns=int(row["video_time_ns"]),
                    u_px=float(row["u_px"]),
                    v_px=float(row["v_px"]),
                    confidence=float(row.get("confidence") or 1.0),
                    track_id=row.get("track_id") or "ball",
                    source=row.get("source") or "manual",
                )
            )
    return annotations


def project_annotations(
    annotations: Iterable[PixelAnnotation],
    calibration: GroundPlaneCalibration,
    time_map: CameraTimeMap | None = None,
) -> list[GroundTruthObservation]:
    projected: list[GroundTruthObservation] = []
    for annotation in annotations:
        x_m, y_m = calibration.project(annotation.u_px, annotation.v_px)
        projected.append(
            GroundTruthObservation(
                frame_id=annotation.frame_id,
                video_time_ns=annotation.video_time_ns,
                edge_time_ns=(
                    time_map.video_to_edge_ns(annotation.video_time_ns)
                    if time_map is not None
                    else None
                ),
                world_x_m=x_m,
                world_y_m=y_m,
                confidence=annotation.confidence,
                track_id=annotation.track_id,
                source=annotation.source,
                camera_id=calibration.camera_id,
                world_frame=calibration.world_frame,
                calibration_id=calibration.calibration_id,
            )
        )
    return projected


def write_ground_truth(path: str | Path, observations: Iterable[GroundTruthObservation]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [observation.to_row() for observation in observations]
    fieldnames = [
        "frame_id",
        "video_time_ns",
        "edge_time_ns",
        "world_x_m",
        "world_y_m",
        "confidence",
        "track_id",
        "source",
        "camera_id",
        "world_frame",
        "calibration_id",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
