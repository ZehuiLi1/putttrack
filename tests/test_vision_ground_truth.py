from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from putttrack.vision import (
    GroundControlPoint,
    PixelAnnotation,
    SyncPair,
    calibrate_ground_plane,
    fit_camera_time_map,
    project_annotations,
    read_pixel_annotations,
    write_ground_truth,
)


class CameraGroundTruthTests(unittest.TestCase):
    def calibration(self):
        # Known affine transform represented by a homography:
        # x = 0.01*u + 0.002*v - 1
        # y = -0.001*u + 0.012*v + 0.5
        image_points = [(100, 100), (900, 100), (900, 500), (100, 500), (500, 300)]
        points = []
        for index, (u, v) in enumerate(image_points):
            points.append(
                GroundControlPoint(
                    label=f"P{index}",
                    image_u_px=u,
                    image_v_px=v,
                    world_x_m=0.01 * u + 0.002 * v - 1.0,
                    world_y_m=-0.001 * u + 0.012 * v + 0.5,
                )
            )
        return calibrate_ground_plane(
            camera_id="cam-1",
            world_frame="LAB_XY",
            points=points,
        )

    def test_oblique_planar_homography_projects_to_world_xy(self) -> None:
        calibration = self.calibration()
        x, y = calibration.project(420.0, 275.0)
        self.assertAlmostEqual(x, 0.01 * 420 + 0.002 * 275 - 1.0, places=7)
        self.assertAlmostEqual(y, -0.001 * 420 + 0.012 * 275 + 0.5, places=7)
        self.assertLess(calibration.rmse_m, 1e-8)

    def test_camera_sync_estimates_offset_and_clock_drift(self) -> None:
        scale = 1.0001
        offset = 4_000_000_000
        pairs = [
            SyncPair(video_time_ns=t, edge_time_ns=int(scale * t + offset))
            for t in (1_000_000_000, 6_000_000_000, 11_000_000_000)
        ]
        mapping = fit_camera_time_map(pairs)
        self.assertAlmostEqual(mapping.scale, scale, places=8)
        self.assertAlmostEqual(mapping.offset_ns, offset, delta=2.0)
        self.assertLess(mapping.rmse_ns, 2.0)

    def test_pixel_annotations_project_and_keep_time_domains(self) -> None:
        calibration = self.calibration()
        mapping = fit_camera_time_map(
            [
                SyncPair(video_time_ns=0, edge_time_ns=1_000_000_000),
                SyncPair(video_time_ns=10_000_000_000, edge_time_ns=11_000_000_000),
            ]
        )
        observations = project_annotations(
            [PixelAnnotation(frame_id="1", video_time_ns=500_000_000, u_px=420, v_px=275)],
            calibration,
            mapping,
        )
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].edge_time_ns, 1_500_000_000)
        self.assertEqual(observations[0].calibration_id, calibration.calibration_id)

    def test_csv_round_trip_for_annotations_and_ground_truth(self) -> None:
        calibration = self.calibration()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            annotations_path = root / "annotations.csv"
            with annotations_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["frame_id", "video_time_ns", "u_px", "v_px", "confidence", "track_id", "source"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "frame_id": "f-1",
                        "video_time_ns": "100",
                        "u_px": "420",
                        "v_px": "275",
                        "confidence": "0.9",
                        "track_id": "ball",
                        "source": "manual",
                    }
                )
            annotations = read_pixel_annotations(annotations_path)
            output = root / "gt.csv"
            write_ground_truth(output, project_annotations(annotations, calibration))
            text = output.read_text(encoding="utf-8")
            self.assertIn("calibration_id", text)
            self.assertIn("f-1", text)


if __name__ == "__main__":
    unittest.main()
