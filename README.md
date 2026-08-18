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

## Gameplay Product Direction

PuttTrack should match the best parts of modern tech-enabled mini golf while reducing customer friction:

- guest-first check-in; persistent account optional;
- one assigned smart ball per player;
- flexible player order inside a group;
- unmistakable ball-recognition / ready cues at every hole;
- automatic strokes, bonuses, hazards and cup completion;
- fast non-blocking visual/audio feedback;
- server-side course rules and scoring;
- normal final-hole completion rather than a hidden one-shot terminator;
- explicit recovery and evidence when sensors disagree.

The canonical locked player/product behavior is defined in `docs/PRODUCT_LOGIC_LOCK.md`. System architecture reviewers should preserve that behavior while remaining free to challenge the current RF, gateway, deployment and software-topology hypotheses.

A deterministic Gameplay Engine V1 lives under `src/putttrack/gameplay/`. It consumes confirmed evidence events and deliberately does not depend on the underlying CS / IMU / camera implementation.

Run the demo with:

```bash
PYTHONPATH=src python simulator/demo_gameplay.py
```

Run the unit tests with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Documentation

- [`docs/PRODUCT_LOGIC_LOCK.md`](docs/PRODUCT_LOGIC_LOCK.md) — locked product/player behavior that architecture work must preserve.
- [`docs/ARCHITECTURE_REVIEW_BRIEF.md`](docs/ARCHITECTURE_REVIEW_BRIEF.md) — canonical handoff for the next full end-to-end architecture pass.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — current technical architecture hypothesis; subject to architecture review.
- [`docs/PATENT_RESEARCH.md`](docs/PATENT_RESEARCH.md) — public patent research, movement-signature concept and legal decision gates.
- [`docs/EXPERIMENT_PLAN.md`](docs/EXPERIMENT_PLAN.md) — staged CS / IMU / camera / tracking experiments and acceptance metrics.
- [`docs/GAMEPLAY_EXPERIENCE.md`](docs/GAMEPLAY_EXPERIENCE.md) — player journey, hole interaction, scoring philosophy, recovery UX and 18-hole pacing.
- [`docs/GAMEPLAY_IMPLEMENTATION.md`](docs/GAMEPLAY_IMPLEMENTATION.md) — Gameplay Engine V1 event contract and implementation boundary.

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
15. Connect sensor-fusion evidence to Gameplay Engine V1 and build the first tee-screen prototype.
16. Run the architecture review defined by `docs/ARCHITECTURE_REVIEW_BRIEF.md` before freezing the production topology.

## IP / Legal Note

This repository contains engineering research notes, not legal advice or a freedom-to-operate opinion. Public patent material is used to understand prior art and define experiments. Before commercial deployment of any claim-sensitive movement-signature architecture, obtain an up-to-date Australian patent/FTO review of the exact final system.
