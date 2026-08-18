from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


class GroundPlaneCalibrationError(ValueError):
    """Raised when a planar camera calibration cannot be solved safely."""


@dataclass(frozen=True)
class GroundControlPoint:
    label: str
    image_u_px: float
    image_v_px: float
    world_x_m: float
    world_y_m: float

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "GroundControlPoint":
        return cls(
            label=str(data.get("label", "")),
            image_u_px=float(data["image_u_px"]),
            image_v_px=float(data["image_v_px"]),
            world_x_m=float(data["world_x_m"]),
            world_y_m=float(data["world_y_m"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "image_u_px": self.image_u_px,
            "image_v_px": self.image_v_px,
            "world_x_m": self.world_x_m,
            "world_y_m": self.world_y_m,
        }


def _solve_linear_system(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> list[float]:
    n = len(rhs)
    if n == 0 or len(matrix) != n or any(len(row) != n for row in matrix):
        raise GroundPlaneCalibrationError("linear system must be square")

    a = [list(map(float, row)) + [float(rhs[i])] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise GroundPlaneCalibrationError("ground-control geometry is singular or degenerate")
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= scale
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                a[row][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]


def _least_squares(rows: Sequence[Sequence[float]], values: Sequence[float]) -> list[float]:
    if not rows or len(rows) != len(values):
        raise GroundPlaneCalibrationError("least-squares input lengths do not match")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise GroundPlaneCalibrationError("least-squares rows have inconsistent width")
    ata = [[0.0 for _ in range(width)] for _ in range(width)]
    atb = [0.0 for _ in range(width)]
    for row, value in zip(rows, values):
        for i in range(width):
            atb[i] += row[i] * value
            for j in range(width):
                ata[i][j] += row[i] * row[j]
    return _solve_linear_system(ata, atb)


@dataclass(frozen=True)
class Homography2D:
    matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

    def project(self, u_px: float, v_px: float) -> tuple[float, float]:
        h = self.matrix
        denominator = h[2][0] * u_px + h[2][1] * v_px + h[2][2]
        if abs(denominator) < 1e-12:
            raise GroundPlaneCalibrationError("projected point lies on homography horizon")
        x_m = (h[0][0] * u_px + h[0][1] * v_px + h[0][2]) / denominator
        y_m = (h[1][0] * u_px + h[1][1] * v_px + h[1][2]) / denominator
        if not (math.isfinite(x_m) and math.isfinite(y_m)):
            raise GroundPlaneCalibrationError("homography produced non-finite coordinates")
        return x_m, y_m

    def to_list(self) -> list[list[float]]:
        return [list(row) for row in self.matrix]

    @classmethod
    def from_list(cls, matrix: Sequence[Sequence[float]]) -> "Homography2D":
        if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
            raise GroundPlaneCalibrationError("homography must be a 3x3 matrix")
        return cls(tuple(tuple(float(value) for value in row) for row in matrix))  # type: ignore[arg-type]


def fit_homography(points: Sequence[GroundControlPoint]) -> Homography2D:
    if len(points) < 4:
        raise GroundPlaneCalibrationError("at least four non-collinear control points are required")

    rows: list[list[float]] = []
    values: list[float] = []
    for point in points:
        u = point.image_u_px
        v = point.image_v_px
        x = point.world_x_m
        y = point.world_y_m
        rows.append([u, v, 1.0, 0.0, 0.0, 0.0, -x * u, -x * v])
        values.append(x)
        rows.append([0.0, 0.0, 0.0, u, v, 1.0, -y * u, -y * v])
        values.append(y)

    h = _least_squares(rows, values)
    return Homography2D(
        (
            (h[0], h[1], h[2]),
            (h[3], h[4], h[5]),
            (h[6], h[7], 1.0),
        )
    )


@dataclass(frozen=True)
class GroundPlaneCalibration:
    camera_id: str
    world_frame: str
    calibration_id: str
    homography: Homography2D
    control_points: tuple[GroundControlPoint, ...]
    rmse_m: float
    max_error_m: float
    notes: str = ""

    def project(self, u_px: float, v_px: float) -> tuple[float, float]:
        return self.homography.project(u_px, v_px)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "camera-ground-plane/1.0",
            "camera_id": self.camera_id,
            "world_frame": self.world_frame,
            "calibration_id": self.calibration_id,
            "homography": self.homography.to_list(),
            "control_points": [point.to_dict() for point in self.control_points],
            "rmse_m": self.rmse_m,
            "max_error_m": self.max_error_m,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "GroundPlaneCalibration":
        points = tuple(GroundControlPoint.from_dict(item) for item in data["control_points"])  # type: ignore[arg-type]
        return cls(
            camera_id=str(data["camera_id"]),
            world_frame=str(data["world_frame"]),
            calibration_id=str(data["calibration_id"]),
            homography=Homography2D.from_list(data["homography"]),  # type: ignore[arg-type]
            control_points=points,
            rmse_m=float(data["rmse_m"]),
            max_error_m=float(data["max_error_m"]),
            notes=str(data.get("notes", "")),
        )


def _calibration_id(camera_id: str, world_frame: str, points: Iterable[GroundControlPoint]) -> str:
    payload = {
        "camera_id": camera_id,
        "world_frame": world_frame,
        "points": [point.to_dict() for point in points],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"camcal-{digest[:16]}"


def calibrate_ground_plane(
    *,
    camera_id: str,
    world_frame: str,
    points: Sequence[GroundControlPoint],
    notes: str = "",
) -> GroundPlaneCalibration:
    if not camera_id.strip() or not world_frame.strip():
        raise GroundPlaneCalibrationError("camera_id and world_frame are required")
    homography = fit_homography(points)
    errors: list[float] = []
    for point in points:
        x_m, y_m = homography.project(point.image_u_px, point.image_v_px)
        errors.append(math.hypot(x_m - point.world_x_m, y_m - point.world_y_m))
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    return GroundPlaneCalibration(
        camera_id=camera_id,
        world_frame=world_frame,
        calibration_id=_calibration_id(camera_id, world_frame, points),
        homography=homography,
        control_points=tuple(points),
        rmse_m=rmse,
        max_error_m=max(errors),
        notes=notes,
    )


def save_calibration(path: str | Path, calibration: GroundPlaneCalibration) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(calibration.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_calibration(path: str | Path) -> GroundPlaneCalibration:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "camera-ground-plane/1.0":
        raise GroundPlaneCalibrationError("unsupported camera ground-plane calibration version")
    return GroundPlaneCalibration.from_dict(data)
