"""Research ground-truth utilities that do not participate in production scoring authority."""

from .calibration import (
    GroundControlPoint,
    GroundPlaneCalibration,
    GroundPlaneCalibrationError,
    Homography2D,
    calibrate_ground_plane,
    fit_homography,
    load_calibration,
    save_calibration,
)
from .ground_truth import (
    GroundTruthError,
    GroundTruthObservation,
    PixelAnnotation,
    project_annotations,
    read_pixel_annotations,
    write_ground_truth,
)
from .sync import (
    CameraSyncError,
    CameraTimeMap,
    SyncPair,
    fit_camera_time_map,
    load_time_map,
    save_time_map,
)

__all__ = [
    "CameraSyncError",
    "CameraTimeMap",
    "GroundControlPoint",
    "GroundPlaneCalibration",
    "GroundPlaneCalibrationError",
    "GroundTruthError",
    "GroundTruthObservation",
    "Homography2D",
    "PixelAnnotation",
    "SyncPair",
    "calibrate_ground_plane",
    "fit_camera_time_map",
    "fit_homography",
    "load_calibration",
    "load_time_map",
    "project_annotations",
    "read_pixel_annotations",
    "save_calibration",
    "save_time_map",
    "write_ground_truth",
]
