# PuttTrack System Architecture

## 1. Architecture Goal

Build a smart mini-golf system in which the ball carries identity and motion sensing, the venue supplies spatial infrastructure, and the edge/server determines position and game events.

Primary design principle:

> Keep the ball simple and power-efficient; keep heavy localisation, tracking, learning and scoring off-ball.

---

## 2. Top-Level Architecture

```text
                           CAMERA (research GT)
                                  |
                                  v
                          Ground-truth service
                                  |
                                  |
SMART BALL -----------------------+------------------------------+
 nRF54L15                                                        |
 IMU                                                             |
 CS Reflector                                                    |
 BALL_ID                                                         |
   |                                                             |
   | Bluetooth Channel Sounding                                  |
   v                                                             |
+---------+   +---------+   +---------+   +---------+   +---------+
|Anchor A |   |Anchor B |   |Anchor C |   |Anchor D |   |Anchor E |
|Initiator|   |Initiator|   |Initiator|   |Initiator|   |Initiator|
+----+----+   +----+----+   +----+----+   +----+----+   +----+----+
     \             |             |             |             /
      \____________|_____________|_____________|____________/
                                  |
                                  v
                         RANGE COLLECTOR
                                  |
                                  v
                     CALIBRATION / QUALITY
                                  |
                                  v
                   ROBUST MULTILATERATION
                                  |
                                  v
                      EKF / IMM TRACKER <----- IMU events
                                  |
                                  v
                    POSITION + CONFIDENCE
                                  |
                                  v
                       GAME EVENT ENGINE
                                  |
                     +------------+-----------+
                     |                        |
                   SCORE                    UI / Replay
```

---

## 3. Hardware Roles

### 3.1 Ball

Prototype target:

- Nordic nRF54L15 Tag.

Responsibilities:

- permanent / provisioned `BALL_ID`;
- Bluetooth Channel Sounding Reflector;
- IMU sampling;
- low-power motion wake;
- generic motion-state detection;
- health / battery reporting;
- timestamped event buffering where useful.

Non-responsibilities:

- final XY calculation;
- five-anchor multilateration;
- full EKF / ML localisation;
- scoring authority.

### 3.2 Anchors

Initial research target:

- five identical Bbo nRF54L15 development boards;
- one additional spare/development board.

Responsibilities:

- Channel Sounding Initiator;
- obtain ranging evidence against the ball;
- retain multiple estimator outputs where available;
- timestamp data;
- forward structured logs to the collector.

Initial geometry:

```text
A ---------------- B
|                  |
|        E         |
|                  |
|       BALL       |
|                  |
D ---------------- C
```

E is not assumed to be automatically superior because it is central. Its value will be measured as redundancy / geometry / quality support.

### 3.3 Edge Host / Gateway

Research implementation: PC / Linux host.

Responsibilities:

- ingest all anchor serial streams;
- clock / timestamp alignment;
- associate records with `ball_id` and `anchor_id`;
- store raw evidence;
- calibration and localisation;
- real-time tracking;
- camera-ground-truth alignment;
- experiment orchestration;
- game-event inference.

Production may later move some functions into a dedicated per-hole gateway.

---

## 4. Software Services

```text
firmware/
  ball-reflector/
  anchor-initiator/

services/
  cs-anchor-service/
  smart-ball-service/
  range-collector/
  vision-ground-truth/

localization/
  calibration/
  quality/
  multilateration/
  tracking/
  ml-correction/

motion/
  segmentation/
  generic-state/
  signature-benchmark/

game-engine/
  events/
  hole-config/
  scoring/

tools/
  replay/
  calibration/
  dataset-export/
```

These directories are target boundaries; implementation can start smaller and grow into them.

---

## 5. Data Contracts

### 5.1 Anchor range record

Minimum record:

```json
{
  "timestamp_ns": 0,
  "ball_id": "ball-001",
  "anchor_id": "A",
  "distance_ifft_m": null,
  "distance_phase_slope_m": null,
  "distance_rtt_m": null,
  "distance_best_m": null,
  "rssi_dbm": null,
  "antenna_path": 0,
  "quality": {}
}
```

Do not discard raw estimator disagreement. It may become an important quality feature.

### 5.2 IMU record

```json
{
  "timestamp_ns": 0,
  "ball_id": "ball-001",
  "accel_mps2": [0.0, 0.0, 0.0],
  "gyro_rads": [0.0, 0.0, 0.0],
  "motion_state": "UNKNOWN"
}
```

Research datasets should preserve raw samples even when the ball firmware emits a derived state.

### 5.3 Ground-truth record

```json
{
  "timestamp_ns": 0,
  "x_gt_m": 0.0,
  "y_gt_m": 0.0,
  "visible": true,
  "confidence": 1.0
}
```

### 5.4 Localisation output

```json
{
  "timestamp_ns": 0,
  "ball_id": "ball-001",
  "x_m": 0.0,
  "y_m": 0.0,
  "vx_mps": 0.0,
  "vy_mps": 0.0,
  "confidence": 0.0,
  "anchors_used": ["A", "B", "D", "E"],
  "method": "adaptive-ekf"
}
```

---

## 6. Localisation Pipeline

### 6.1 Per-anchor calibration

Start with simple affine calibration per anchor:

```text
d_corrected = a_i * d_raw + b_i
```

Then determine whether orientation / range / region-specific residual models are justified.

### 6.2 Quality and outlier rejection

Candidate inputs:

- estimator disagreement;
- RSSI;
- tone / ranging quality exposed by the SDK;
- antenna path;
- recent residual history;
- physically impossible jumps;
- consistency with other anchors.

Output a confidence weight `w_i` for each range.

### 6.3 Robust multilateration

Solve the overdetermined position problem with weighted residuals:

```text
minimise sum_i w_i * (predicted_range_i(x,y) - measured_range_i)^2
```

Evaluate:

- all 5 anchors;
- best 4 of 5;
- robust loss functions;
- iterative exclusion of bad ranges.

### 6.4 Tracking

Baseline state:

```text
[x, y, vx, vy]
```

Compare:

- KF;
- EKF;
- adaptive EKF;
- IMM-EKF / motion-mode switching.

Use generic IMU states to change process noise and update policy, e.g.:

```text
STATIONARY -> low process noise
ROLLING    -> rolling model / medium process noise
IMPACT     -> temporarily high process noise
PICKED_UP  -> different model / suspend course-constrained tracking
```

---

## 7. Camera Role

The camera is initially a measurement instrument, not the product's localisation dependency.

Research use:

```text
camera -> x_gt,y_gt -> synchronised dataset
```

Uses:

- measure ranging / localisation error;
- train range-bias or confidence models;
- validate trajectory tracking;
- provide labels for motion / game-event datasets.

Target deployment:

- CS + IMU operate without camera-derived XY;
- cameras may remain for replay, diagnostics or special evidence but are not required for normal localisation.

---

## 8. Motion Architecture

### Generic production-safe research states

- stationary;
- impact;
- rolling;
- slowing;
- collision;
- pickup;
- carried;
- drop;
- bounce;
- unknown.

Generic states are intentionally independent of hole number.

### Movement-signature benchmark

Hole-specific sequence comparison is isolated behind a research boundary until both technical evidence and IP review justify any deployment.

---

## 9. Game Event Engine

Separate physical sensing from game semantics:

```text
RAW SENSOR
   -> PHYSICAL STATE
   -> SPATIAL STATE
   -> GAME EVENT
   -> SCORING
```

Examples:

```text
IMPACT
+ ball starts moving from tee zone
=> SHOT_CONFIRMED
```

```text
trajectory crosses bonus geometry
+ confidence above threshold
=> BONUS_TRIGGERED
```

```text
ball reaches cup region
+ drop/impact/rest evidence
+ optional physical cup sensor
=> HOLE_COMPLETE
```

The event engine should preserve evidence and confidence rather than only returning a black-box score.

---

## 10. Power / Scheduling Direction

The ball should not range at maximum update rate continuously.

Concept:

```text
stationary -> very low update rate / sleep
impact detected -> raise tracking rate
rolling -> active CS tracking
rest detected -> confirm position -> drop tracking rate
```

Anchors are mains / venue powered and can carry the heavier Initiator scheduling responsibility.

Multi-ball scheduling is a later explicit research phase; do not assume a 1-ball demo scales automatically to venue load.

---

## 11. Production Hardware Direction

Do not design the final embedded golf-ball PCB until the research rig establishes:

- required anchor update rate;
- required IMU data;
- single vs dual antenna benefit;
- power budget;
- required processing split;
- actual positioning performance.

Current product research candidate after proof:

```text
nRF54L15
+ ultra-low-power motion sensor
+ 6-axis IMU if justified
+ dual antenna if experimentally justified
+ coin-cell power architecture
```

The final power architecture should be selected from measured duty-cycle data rather than copied from another commercial product.
