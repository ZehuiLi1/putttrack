# Camera / Survey Ground Truth Strategy

## Status

Research support only. Camera is **not** a production scoring or localisation dependency.

A high overhead camera is useful but **not required**. PuttTrack must be able to develop and validate the RF tracker when the site cannot accommodate a tall camera mast.

## 1. Ground-truth hierarchy

Use the simplest truth source that is stronger than the quantity under test.

### Phase 0 / Phase 1 — single-link ranging

**Camera not required.**

Use surveyed physical truth:

- measured Anchor RF reference point;
- measured Reflector/Tag reference point;
- tape/laser distance recorded in the immutable run manifest;
- measured height and orientation.

For the 0.5 / 1 / 2 / 3 / 5 / 8 / 10 m matrix, a carefully laid-out measured baseline is better than adding unnecessary vision error.

### Phase 2 — static 3/4/5-Anchor XY

**Camera still optional.**

Create a surveyed floor/grid coordinate system and place the Tag/ball reference at known grid points. Recommended:

- fixed venue/lab origin;
- x/y axes marked physically;
- 0.25–0.50 m grid where practical;
- each evaluation point surveyed independently rather than inferred from image pixels;
- Anchor x/y/z recorded in the same world frame.

This gives direct static XY truth and avoids making Phase 2 depend on camera mounting.

### Phase 3 — dynamic rolling-object tracking

Continuous trajectory truth benefits from video. Preferred order:

1. **one low/oblique camera + planar homography** if the test lane is planar and sufficiently visible;
2. **two low/oblique cameras with overlapping coverage** if one view has occlusion or poor far-end resolution;
3. **piecewise planar calibration** for distinct flat regions;
4. multi-view/3D reconstruction only if ramps or non-planar motion must be evaluated continuously.

If continuous video truth cannot be made reliable, use surveyed gates/lines and timing markers for partial dynamic truth and do not pretend that they provide full XY ground truth.

## 2. Low / oblique camera setup

The camera does not need to look straight down. It needs:

- a stable mount that does not move during a calibration/run;
- a view of the ball path;
- at least four non-collinear ground control points on the same physical plane;
- enough image resolution at the far end of the region;
- limited occlusion by players/obstacles;
- independently surveyed control-point XY coordinates.

Recommended practical setup:

- 6–12 control markers around the edge of the test region;
- keep markers outside normal ball travel where possible;
- distribute markers across the entire image rather than clustering them near the camera;
- measure their world XY with tape/laser/survey methods;
- capture calibration image(s) after the camera is locked in place;
- re-calibrate whenever the camera, zoom, digital stabilisation or crop changes.

The checked-in v1 tools fit an image-pixel -> world-XY planar homography using only Python standard-library code:

```bash
PYTHONPATH=src python tools/calibrate_ground_plane.py \
  configs/ground_truth/camera_oblique.example.json \
  runs/camera/calibration.json
```

The example file is not a real venue calibration.

## 3. Validation, not just fitting

A low calibration residual on the same points used to fit the homography is not sufficient.

For real experiments:

1. fit on distributed control points;
2. reserve additional surveyed points as independent validation points;
3. report validation P50/P90/P95 and maximum spatial error;
4. plot error versus image location / distance from camera;
5. split the region or add a second camera if the far end degrades materially.

Candidate target for the research region:

- held-out camera-projection P95 <= 0.03 m;
- held-out maximum <= 0.05 m where practical.

These are research-quality targets, not guaranteed properties of any camera. If the camera setup cannot meet them, narrow the evaluation region, improve optics/mounting, add a second view, or fall back to surveyed static truth.

## 4. Lens distortion

A projective homography models perspective on a plane; it does **not** model strong lens distortion.

Avoid using an aggressive wide/fisheye lens without correction. Options:

- use a moderate-FOV lens and keep the evaluation region away from severely distorted edges;
- undistort pixel coordinates with a calibrated camera model before using the PuttTrack homography tools;
- add a future OpenCV-based distortion stage if the real camera requires it.

Do not hide residual distortion inside the RF error budget.

## 5. Pixel annotation / detector boundary

PuttTrack deliberately separates **how a pixel location was obtained** from **how it is mapped into world XY**.

Canonical research path:

```text
video
  -> manual annotation / detector / tracker
  -> frame_id, video_time_ns, u_px, v_px, confidence
  -> planar calibration
  -> world_x_m, world_y_m
  -> optional camera-to-Edge time map
  -> research Ground Truth CSV
```

The checked-in projection tool accepts any annotation source that produces the CSV contract:

```bash
PYTHONPATH=src python tools/project_camera_gt.py \
  annotations.csv \
  calibration.json \
  ground_truth.csv \
  --time-map camera_time_map.json
```

Automatic ball detection is intentionally not frozen before seeing the real camera/lighting/background. A detector that works in one lab may fail outdoors, at night or under shadows. Manual/semi-manual annotation remains a valid reference for a smaller validation dataset.

## 6. Time synchronisation without PTP

Camera video time and PuttTrack Edge monotonic time are separate clock domains.

For dynamic experiments use a visible sync LED/marker placed in camera view. Record the Edge timestamp when each pulse is commanded/observed by the experiment controller. Prefer at least:

- one pulse near run start;
- one or more pulses during the run;
- one pulse near run end.

Then fit:

```text
edge_time = scale * video_time + offset
```

This estimates offset and camera-clock drift without pretending that camera time is UTC or directly comparable to Anchor monotonic time.

```bash
PYTHONPATH=src python tools/fit_camera_sync.py \
  sync_pairs.csv \
  camera_time_map.json
```

Candidate target for the dynamic research dataset:

- sync residual <= 10 ms P95 where practical;
- record video frame rate and timestamp source;
- prefer >=60 fps for faster rolling tests if the camera supports it.

At 60 fps, one frame is ~16.7 ms, so frame quantisation itself can dominate the time error even if the fitted clock map is perfect.

## 7. Non-planar holes and ramps

A single floor homography is valid only for points on its calibrated plane.

For a ramp or raised feature:

- do not map ramp pixels with the flat-floor homography and call them accurate XY;
- either exclude that feature from the first dynamic accuracy gate;
- calibrate a separate planar segment and tag observations with the segment;
- or use a multi-view 3D method in a later research phase.

The first dynamic CS/EKF benchmark should favour a controlled planar lane. Complex venue geometry comes after the baseline tracker is understood.

## 8. Production boundary

The deployed game must continue when the research camera is absent.

Camera may later be useful for:

- research ground truth;
- difficult-case evidence;
- commissioning/calibration;
- dispute/replay support;
- model validation.

It is not the authority that decides a stroke, bonus, hazard or cup completion in Production V1.
