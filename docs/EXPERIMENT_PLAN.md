# PuttTrack Experiment Plan

## Objective

Build evidence in layers. Do not jump directly to AI or full game logic.

The experiment sequence should answer, in order:

1. Does the selected hardware reproduce Nordic Channel Sounding reliably?
2. What is the single-link ranging error under realistic orientations / obstructions?
3. How many anchors are actually useful?
4. Can multi-anchor CS achieve sub-metre 2D localisation?
5. How much do Kalman/EKF and IMU improve dynamic tracking?
6. Can a mechanically repeatable research ball provide reliable raw IMU data for generic motion-state recognition?
7. Can generic motion states reliably identify game-relevant evidence?
8. Do hole-specific movement signatures materially improve event inference?
9. Does a hybrid spatial + motion approach outperform either alone?
10. Can the design scale to multiple balls at acceptable latency and energy?

The final production Smart Ball PCB is **not** a prerequisite for motion research. A repeatable instrumented research ball is. Final sensor ranges, mechanics and classifier choice remain evidence-gated until real ball data exists.

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

Use calibrated camera tracking to obtain timestamped `x_gt, y_gt` trajectories. A stable low/oblique view mapped through surveyed ground-control points is acceptable; a tall overhead camera is not required.

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

## Phase 4 — Research Ball and Generic Motion-State Dataset

See [`research/BALL_IMU_STATE_RECOGNITION.md`](research/BALL_IMU_STATE_RECOGNITION.md) for the canonical algorithm and sensor-range direction.

### P4.1 Tag sensor/logger bring-up

Before trying to classify anything, verify that the Nordic Tag can preserve useful raw IMU evidence:

- BMI270 `ax, ay, az, gx, gy, gz` streaming/FIFO;
- monotonic timestamps and dropped-sample detection;
- stationary noise and bias in multiple orientations;
- initial general-state capture around 400 Hz;
- impact experiments at higher accelerometer ODR, toward 1–1.6 kHz where practical;
- exact accelerometer / gyro range and ODR recorded in every run.

The bare Tag is a firmware/instrumentation reference, not the canonical classifier-training mechanical condition.

### P4.2 Instrumented research-ball gate

Build a mechanically repeatable research ball/core before collecting the canonical dataset.

Requirements:

- rigid, repeatable sensor/core mounting;
- no loose PCB or battery motion;
- fixed sensor coordinate frame and visible orientation marks;
- documented mass and centre-of-mass offset;
- enough impact robustness for controlled weak-to-normal putting tests;
- ball mechanical revision recorded in every run.

The research ball does not need final production RF tuning, potting, battery life or tournament-conforming balance.

Compare bare-Tag and in-ball recordings so enclosure/mounting effects are visible rather than silently absorbed into thresholds.

### P4.3 Saturation gate

Treat BMI270 range sufficiency as a measurement question.

Record accel/gyro clipping counts explicitly. BMI270 is limited to approximately `±16 g` acceleration and `±2000 dps` gyro. For a golf-ball-radius body in pure rolling, approximately `1 m/s` already corresponds to about `2680 dps`, so gyro clipping is plausible during normal rolling. Rigid impact acceleration can also exceed `16 g`.

If clipping removes information needed for classification, evaluate a high-g accelerometer during EVT. Do not add one to the production BOM without measured evidence.

### P4.4 Canonical labelled dataset

Minimum classes/episodes:

- stationary;
- weak putter strike;
- normal putter strike;
- strong putter strike;
- rolling;
- slowing / settling;
- wall collision;
- ball-ball collision;
- pickup;
- carry;
- hand roll;
- drag / deliberate manipulation;
- drop;
- bounce;
- ramp ascent;
- rollback;
- cup drop / bounce / rest;
- removal from cup.

Data collection rules:

- start with roughly 100–200 episodes per important class;
- multiple operators;
- multiple ball orientations;
- multiple speeds / strike strengths;
- multiple representative surfaces;
- more samples for classes that remain confused after the first baseline;
- retain raw accel + gyro rather than only processed states;
- align video ground truth and CS position to the same timeline for ambiguous sequences;
- retain clipping/saturation information.

Canonical raw schema:

```text
t_us,ax,ay,az,gx,gy,gz,label,event_id,ball_id,session_id
```

Train/test separation must be by session and preferably by physical ball. Do not randomly split adjacent windows from the same episode into train and test.

### P4.5 Algorithm ladder

Do not start with an opaque eight-class neural network.

**V0 — deterministic baseline**

- orientation-invariant acceleration magnitude;
- gyro magnitude;
- jerk / sample-to-sample acceleration change;
- high-pass impact energy;
- variance / RMS;
- temporal dwell, hysteresis, debounce and refractory periods;
- explicit FSM/state-transition constraints.

Target easy states first: `STATIONARY`, `IMPACT`, `ROLLING/ACTIVE`, `SETTLING`, `FREE_FALL/DROP`.

**V1 — feature ML baseline**

If V0 leaves meaningful ambiguity:

- extract compact time/frequency features;
- benchmark Random Forest first;
- optionally compare SVM;
- inspect feature importance and reduce the deployed feature set.

**V2 — temporal TinyML only if justified**

If held-out confusion remains material, benchmark a small quantised 1D-CNN or TCN, especially for:

- putter strike vs collision;
- pickup/carry vs unusual rolling/handling;
- cup/drop/bounce sequences.

Do not use an end-to-end model that directly produces score.

### P4.6 Metrics

Report more than overall accuracy:

- precision / recall / F1 per class;
- macro-F1;
- missed-stroke rate;
- false strokes per labelled non-stroke episode and per player-hour where possible;
- event timestamp error;
- confusion matrix;
- latency;
- CPU / RAM / flash;
- active energy per event;
- clipping/saturation rate;
- robustness across balls, operators, orientations and surfaces.

Primary goal:

- robust generic physical-state evidence independent of hole number.

Architecture candidate verification targets remain:

- stroke recall >= 99%;
- false-stroke rate <= 0.1% of labelled non-stroke episodes.

These are targets, not current measured performance.

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
- ball/core mechanical revision for IMU experiments;
- IMU range / ODR;
- clipping/saturation summary;
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
6. Keep held-out sessions/balls for motion-state ML work.
7. Report P50/P90/P95, not only averages.
8. Record failed / missing ranging attempts.
9. Record sensor clipping/saturation rather than silently clipping features.
10. Track configuration changes explicitly.

---

## Decision Gates

### Technical Gate T1 — CS works

Pass when Bbo -> Nordic Tag ranging is stable and machine-readable.

### T2 — Localisation works

Pass when 4/5-anchor static P90 < 1 m.

### T3 — Sub-metre tracking is credible

Pass when dynamic tracking approaches the <=0.5 m P90 target in representative conditions.

### T4 — Research-ball IMU evidence is credible

Pass when:

- a repeatable instrumented ball can capture raw timestamped IMU without unexplained data loss;
- clipping/saturation limits are quantified;
- generic-state baselines are evaluated on held-out sessions/balls;
- motion evidence materially reduces false event / tracking ambiguity;
- the remaining ambiguous classes are identified rather than hidden by overall accuracy.

Only after T4 should the production IMU range/sensor stack and embedded classifier be frozen.

### T5 — Signature benchmark adds value

Pass only if hole-specific / sequence methods clearly outperform simpler generic + spatial approaches on held-out data.

### T6 — Venue scalability

Pass when multi-ball update rate, latency and power meet the eventual game requirements.

### T7 — Commercial architecture

Only after technical evidence and patent/FTO review should the final scoring architecture and custom ball PCB be frozen.
