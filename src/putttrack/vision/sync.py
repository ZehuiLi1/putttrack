from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class CameraSyncError(ValueError):
    """Raised when camera/Edge time mapping cannot be fitted safely."""


@dataclass(frozen=True)
class SyncPair:
    video_time_ns: int
    edge_time_ns: int
    label: str = ""

    def __post_init__(self) -> None:
        if self.video_time_ns < 0 or self.edge_time_ns < 0:
            raise CameraSyncError("sync timestamps must be non-negative")


@dataclass(frozen=True)
class CameraTimeMap:
    scale: float
    offset_ns: float
    rmse_ns: float
    max_error_ns: float
    pair_count: int

    @property
    def drift_ppm(self) -> float:
        return (self.scale - 1.0) * 1_000_000.0

    def video_to_edge_ns(self, video_time_ns: int) -> int:
        if video_time_ns < 0:
            raise CameraSyncError("video timestamp must be non-negative")
        mapped = self.scale * float(video_time_ns) + self.offset_ns
        if not math.isfinite(mapped) or mapped < 0:
            raise CameraSyncError("mapped Edge timestamp is invalid")
        return int(round(mapped))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "camera-time-map/1.0",
            "scale": self.scale,
            "offset_ns": self.offset_ns,
            "rmse_ns": self.rmse_ns,
            "max_error_ns": self.max_error_ns,
            "pair_count": self.pair_count,
            "drift_ppm": self.drift_ppm,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CameraTimeMap":
        if data.get("schema_version") != "camera-time-map/1.0":
            raise CameraSyncError("unsupported camera time-map version")
        return cls(
            scale=float(data["scale"]),
            offset_ns=float(data["offset_ns"]),
            rmse_ns=float(data["rmse_ns"]),
            max_error_ns=float(data["max_error_ns"]),
            pair_count=int(data["pair_count"]),
        )


def fit_camera_time_map(pairs: Sequence[SyncPair]) -> CameraTimeMap:
    if not pairs:
        raise CameraSyncError("at least one sync pair is required")
    if len(pairs) == 1:
        pair = pairs[0]
        return CameraTimeMap(
            scale=1.0,
            offset_ns=float(pair.edge_time_ns - pair.video_time_ns),
            rmse_ns=0.0,
            max_error_ns=0.0,
            pair_count=1,
        )

    xs = [float(pair.video_time_ns) for pair in pairs]
    ys = [float(pair.edge_time_ns) for pair in pairs]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator <= 0.0:
        raise CameraSyncError("sync pairs must contain distinct video timestamps")
    scale = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    offset = y_mean - scale * x_mean
    residuals = [y - (scale * x + offset) for x, y in zip(xs, ys)]
    rmse = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    return CameraTimeMap(
        scale=scale,
        offset_ns=offset,
        rmse_ns=rmse,
        max_error_ns=max(abs(value) for value in residuals),
        pair_count=len(pairs),
    )


def save_time_map(path: str | Path, mapping: CameraTimeMap) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(mapping.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_time_map(path: str | Path) -> CameraTimeMap:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return CameraTimeMap.from_dict(data)
