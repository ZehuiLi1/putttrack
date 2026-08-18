# PuttTrack

PuttTrack is a research and product-development repository for a smart mini-golf ball and venue tracking system.

The current direction combines:

- Nordic nRF54L15 smart-ball hardware;
- Bluetooth Channel Sounding (CS) for spatial ranging;
- multi-anchor localisation;
- ball IMU / motion-state sensing;
- camera-derived ground truth during research and calibration;
- multilateration + Kalman/EKF/IMM tracking;
- optional learned RF confidence / range-bias correction;
- venue game-event and scoring logic;
- a parallel research benchmark of publicly disclosed World Golf Systems / Puttshack movement-signature concepts.

## Current Decision

The **current implementation path is spatial-first**:

```text
Smart Ball
  nRF54L15
  + IMU
  + Channel Sounding Reflector
        |
        v
5 x nRF54L15 Anchors
  4 perimeter + 1 centre/reference
  Channel Sounding Initiators
        |
        v
Range Collector / Edge Host
        |
        v
Calibration + robust multilateration
        |
        v
IMU-assisted adaptive EKF / IMM
        |
        v
x, y, velocity, confidence
        |
        v
Game Event Engine
```

Movement-signature methods are being studied in parallel as a **research benchmark and possible future hybrid component**, not as the current commercial scoring dependency.

## Initial Hardware Research Rig

### Moving ball / tag

- 1-2 x Nordic `nRF54L15 Tag`.
- First Tag remains a golden-reference board where practical.
- Second Tag, if available, can be used for rolling / enclosure / impact / orientation experiments.

### Anchors

Initial target:

- 5 identical nRF54L15 development boards as active anchors.
- 1 additional identical spare/development board.
- Current candidate: Bbo nRF54L15 development board because it is available quickly and supports Nordic nRF Connect SDK workflows, USB serial logging and SWD.

Baseline geometry:

```text
A ---------------- B
|                  |
|        E         |
|                  |
|       BALL       |
|                  |
D ---------------- C
```

A/B/C/D provide geometry. E is an additional redundancy/reference anchor. Experiments will compare 3 anchors, 4 perimeter anchors, 4+centre, best-4-of-5 and weighted-5 solutions before a production anchor count is fixed.

## Ball / Anchor / Server Responsibilities

### Ball

Keep the battery-powered ball minimal:

- permanent `BALL_ID`;
- Channel Sounding Reflector role;
- raw / derived IMU sensing;
- generic motion states such as impact, rolling, slowing, stationary, pickup, drop and collision;
- battery / health status;
- event buffering and low-power scheduling.

The ball should **not** be responsible for final XY localisation or scoring.

### Anchor

- Channel Sounding Initiator;
- obtain / calculate per-link ranging estimates;
- retain ranging quality information;
- forward timestamped range evidence to the edge host.

### Edge / Server

- anchor calibration;
- outlier rejection and confidence weighting;
- multilateration;
- Kalman / EKF / IMM tracking;
- camera-ground-truth alignment during research;
- optional ML range-bias / covariance estimation;
- game-event inference and scoring;
- evidence / replay / diagnostics.

## Research Tracks

### Track A — Spatial-first (current build path)

Bluetooth Channel Sounding + generic IMU context + robust multilateration + adaptive tracking.

### Track B — Movement-signature benchmark

Study the public World Golf Systems patent disclosures around translational/rotational acceleration sequences and hole-specific movement signatures. Reconstruct benchmark classifiers from our own data; do not assume access to Puttshack production algorithms.

### Track C — Hybrid

Use spatial trajectory + generic motion evidence + course geometry + optional physical feature truth. After legal review, movement-signature evidence may be evaluated as a confidence feature or fallback rather than the sole scoring truth.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system architecture and module boundaries.
- [`docs/PATENT_RESEARCH.md`](docs/PATENT_RESEARCH.md) — public patent research, movement-signature concept and legal decision gates.
- [`docs/EXPERIMENT_PLAN.md`](docs/EXPERIMENT_PLAN.md) — staged CS / IMU / camera / tracking experiments and acceptance metrics.

## Immediate Backlog

1. Acquire 1-2 Nordic nRF54L15 Tags.
2. Acquire 5 identical nRF54L15 anchors + 1 spare.
3. Archive anchor schematic, pin map, recovery firmware/tooling and SDK notes.
4. Reproduce Nordic Channel Sounding Initiator/Reflector samples on bench hardware.
5. Run anchor -> Nordic Tag ranging.
6. Implement structured timestamped CS logging.
7. Implement synchronized IMU logging.
8. Add overhead-camera ground truth.
9. Build 3/4/5-anchor localisation baseline.
10. Add calibration, robust weighting and EKF.
11. Collect labelled movement episodes.
12. Benchmark generic vs hole-specific movement-signature models offline.
13. Compare spatial-first, movement-signature and hybrid methods.
14. Complete a patent/FTO checkpoint before any patent-sensitive commercial architecture is adopted.

## IP / Legal Note

This repository contains engineering research notes, not legal advice or a freedom-to-operate opinion. Public patent material is used to understand prior art and define experiments. Before commercial deployment of any claim-sensitive movement-signature architecture, obtain an up-to-date Australian patent/FTO review of the exact final system.
