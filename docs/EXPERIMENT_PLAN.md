# PuttTrack Experiment Plan

## Objective

Build evidence in layers. Do not jump directly to AI or full game logic.

The experiment sequence should answer, in order:

1. Does the selected hardware reproduce Nordic Channel Sounding reliably?
2. What is the single-link ranging error under realistic orientations / obstructions?
3. How many anchors are actually useful?
4. Can multi-anchor CS achieve sub-metre 2D localisation?
5. How much do Kalman/EKF and IMU improve dynamic tracking?
6. Can generic motion states reliably identify game-relevant events?
7. Do hole-specific movement signatures materially improve event inference?
8. Does a hybrid spatial + motion approach outperform either alone?
9. Can the design scale to multiple balls at acceptable latency and energy?

---

## Phase 0 — Hardware Bring-Up

### P0.1 Bbo-to-Bbo baseline

Configure:

- Anchor / Initiator: Bbo nRF54L15.
- Reflector: second Bbo nRF54L15.
- Nordic nRF Connect SDK Channel Sounding sample.

Verify:

- stable connection;
- Channel Sounding procedure completes repeatedly;
- IFFT / phase-slope / RTT estimates are visible where exposed;
- timestamps and serial logs are reliable.

### P0.2 Bbo-to-Nordic-Tag baseline

Replace reflector with Nordic nRF54L15 Tag.

Acceptance:

- stable ranging at 1 m and 3 m;
- logs can be parsed automatically;
- no unexplained reset / disconnect during a 30-minute bench run.

---

## Phase 1 — Single-Link Static Ranging

Ground-truth distances:

- 0.5 m
- 1 m
- 2 m
- 3 m
- 5 m
- 8 m
- 10 m

For each distance collect repeated samples under:

### Orientation

- Tag orientation 0 / 90 / 180 / 270 deg;
- anchor orientation variations;
- near-ground placement;
- representative ball-like enclosure where available.

### RF conditions

- clear LOS;
- human body obstruction;
- wall adjacency;
- corner / multipath condition;
- near metal / feature structures;
- single vs dual antenna path where supported.

### Metrics

Per condition:

- mean bias;
- standard deviation;
- MAE;
- P50 absolute error;
- P90 absolute error;
- P95 absolute error;
- outlier rate;
- estimator disagreement;
- missing-measurement rate.

Do not report only mean error.

---

## Phase 2 — Static 2D Localisation

### Test geometry

Mark a test field with camera-calibrated coordinates.

Example:

```text
A ---------------- B
| . . . . . . . . |
| . . . E . . . . |
| . . . . . . . . |
| . . . . . . . . |
D ---------------- C
```

Use a 25-50 cm ground-truth grid depending on field size.

### Methods to compare

1. 3-anchor multilateration.
2. 4 perimeter anchors.
3. 4 perimeter + centre E.
4. Best-4-of-5.
5. Weighted 5-anchor solution.
6. Robust-loss 5-anchor solution.

### Questions

- Does the centre anchor reduce tail error?
- Is best-4-of-5 better than blindly using all five?
- Which layouts minimise geometric dilution?
- Where do NLOS / multipath failures cluster?

### Metrics

- 2D Euclidean error;
- P50 / P90 / P95;
- max error;
- failure / no-fix rate;
- spatial heatmap of error;
- anchor residual heatmap.

Initial research target:

- static P90 < 1.0 m to pass the first localisation gate;
- stretch target: static P90 <= 0.5 m.

---

## Phase 3 — Dynamic Tracking

### Ground truth

Use overhead camera tracking to obtain timestamped `x_gt, y_gt` trajectories.

### Trajectories

- straight slow roll;
- straight fast roll;
- diagonal roll;
- wall rebound;
- S-shaped / obstacle route;
- ramp ascent and descent;
- stop / restart;
- pickup and reposition.

### Algorithms

Compare incrementally:

1. raw multilateration per frame;
2. calibrated multilateration;
3. median / simple temporal smoothing;
4. KF;
5. EKF;
6. adaptive EKF;
7. IMU-assisted adaptive EKF;
8. IMM-EKF if multiple motion modes justify it.

### Metrics

- trajectory RMSE;
- P50 / P90 / P95 position error;
- lag / latency;
- overshoot after impacts;
- time to reacquire after bad ranges;
- stationary drift;
- false movement during stationary periods.

Stretch target:

- dynamic P90 <= 0.5 m under representative venue conditions.

---

## Phase 4 — Generic Motion-State Dataset

Collect labelled examples from the Nordic Tag IMU.

Minimum classes:

- stationary;
- valid putt;
- weak tap;
- strong putt;
- rolling;
- slowing;
- wall collision;
- ball-ball collision;
- pickup;
- carry;
- hand roll;
- drag;
- drop;
- bounce;
- ramp ascent;
- rollback;
- cup drop / bounce / rest.

### Data collection rules

- multiple repetitions per class;
- multiple operators;
- multiple ball orientations;
- multiple speeds;
- battery-state variation where practical;
- retain raw accel + gyro rather than only processed states;
- camera labels and CS position aligned to the same timeline.

### Baselines

- threshold / rule classifier;
- feature-distance classifier;
- tree classifier.

Primary goal:

- robust generic physical-state labels independent of hole number.

---

## Phase 5 — Movement-Signature Benchmark

This phase is research-only and must remain clearly separated from commercial decision logic until IP review.

### Dataset structure

For each hole / route, record repeated labelled trials of:

- valid strokes;
- under-hit rollback;
- over-hit / abnormal trajectories;
- pickup / carry / replacement;
- drop;
- hand roll;
- ball-ball collision;
- cup entry;
- alternative valid routes where the hole permits them.

### Models

Compare:

1. generic motion-state rules;
2. feature-distance signature matching;
3. DTW sequence matching;
4. HMM / state-sequence model;
5. tree model;
6. compact temporal neural model only if required.

### Compare generic vs hole-specific

Primary question:

> Does adding a hole-specific motion model materially improve valid-stroke / route / cup classification over generic motion evidence plus spatial tracking?

Metrics:

- precision;
- recall;
- F1;
- false-stroke rate;
- false cup-completion rate;
- route classification;
- inference latency;
- memory / CPU cost;
- energy per event if run on-ball.

---

## Phase 6 — Hybrid Fusion

Candidate fusion inputs:

```text
CS XY trajectory
+ range confidence
+ IMU generic state
+ optional movement-signature score
+ course geometry
+ optional cup / gate sensor truth
```

Candidate outputs:

- `SHOT_CONFIRMED`;
- `SHOT_REJECTED`;
- `BONUS_TRIGGERED`;
- `HAZARD_TRIGGERED`;
- `ROUTE_CLASSIFIED`;
- `HOLE_COMPLETE`;
- `MANUAL_REVIEW`.

The hybrid estimator should preserve confidence and supporting evidence.

---

## Phase 7 — RF ML Correction

Only after calibrated non-ML baselines exist.

Candidate features:

- IFFT distance;
- phase-slope distance;
- RTT distance;
- estimator disagreement;
- RSSI;
- SDK tone / quality information;
- antenna path;
- anchor ID;
- region / geometry features;
- IMU state;
- recent residuals.

Preferred ML outputs:

1. range-bias correction `delta_d`; or
2. measurement confidence / covariance used by the EKF.

Avoid starting with a black-box RF -> XY neural network unless simpler approaches fail.

### Required ablation

```text
Raw CS
-> calibrated CS
-> robust multilateration
-> EKF
-> IMU-EKF
-> ML confidence/bias + EKF
```

Quantify the incremental contribution of each layer.

---

## Phase 8 — Multi-Ball Scalability

Progression:

- 1 ball;
- 2 balls;
- 4 balls;
- 8 balls;
- larger simulated / physical loads as justified.

Measure:

- CS update rate per ball;
- connection / procedure scheduling overhead;
- end-to-end latency;
- dropped updates;
- anchor CPU / memory;
- RF airtime;
- ball active energy;
- fairness between balls;
- handover between hole / zone anchor groups.

Do not extrapolate venue capacity from a single-ball demo.

---

## Data Storage Layout

Proposed structure:

```text
data/
  raw/
    cs/
    imu/
    camera/
  aligned/
  labels/
  calibration/
  derived/
  reports/
```

Each experimental run should have a manifest containing:

- date/time;
- firmware commit;
- SDK version;
- anchor serial IDs;
- Tag hardware revision;
- antenna configuration;
- physical anchor coordinates;
- camera calibration ID;
- environment notes;
- operator;
- experiment protocol ID.

---

## Reproducibility Rules

1. Preserve raw logs.
2. Never overwrite a dataset in place.
3. Store firmware / algorithm commit hashes with each run.
4. Separate calibration, training and test trajectories.
5. Keep a held-out test region / trajectory set for ML work.
6. Report P50/P90/P95, not only averages.
7. Record failed / missing ranging attempts.
8. Track configuration changes explicitly.

---

## Decision Gates

### Technical Gate T1 — CS works

Pass when Bbo -> Nordic Tag ranging is stable and machine-readable.

### T2 — Localisation works

Pass when 4/5-anchor static P90 < 1 m.

### T3 — Sub-metre tracking is credible

Pass when dynamic tracking approaches the <=0.5 m P90 target in representative conditions.

### T4 — Motion is useful

Pass when generic IMU states materially reduce false event / tracking ambiguity.

### T5 — Signature benchmark adds value

Pass only if hole-specific / sequence methods clearly outperform simpler generic + spatial approaches on held-out data.

### T6 — Venue scalability

Pass when multi-ball update rate, latency and power meet the eventual game requirements.

### T7 — Commercial architecture

Only after technical evidence and patent/FTO review should the final scoring architecture and custom ball PCB be frozen.
