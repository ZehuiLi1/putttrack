# ADR-008 — Asynchronous Range-Domain EKF as Primary Dynamic Tracker

## Context

Connected CS ranges from multiple Anchors are sequential and have individual timestamps. Treating them as one simultaneous frame introduces timing distortion, especially for a rolling ball.

## Options

1. Multilateration snapshot each cycle, then KF/EKF on XY.
2. Asynchronous EKF updates directly with each range.
3. End-to-end neural tracker.
4. Particle filter/IMM from day one.

## Decision

Choose option 2 for primary dynamic tracking. Keep robust weighted multilateration for initialization, static benchmarks, diagnostics and reacquisition. Adaptive process noise uses generic motion state. IMM is deferred.

## Why

- respects true source timestamps;
- avoids fake synchronization and correlated XY fixes;
- naturally handles missing/variable-rate Anchors;
- yields covariance for evidence policy;
- remains physics-based and explainable.

## Risks

Model/calibration errors can bias range updates; initialization and nonlinear behavior need care.

## Validation

Replay comparison against snapshot WLS, WLS+KF and camera ground truth; report P50/P90/P95, latency, reacquisition and stationary drift.

## Revisit trigger

- asynchronous EKF fails dynamic gates;
- a particle/IMM model materially improves difficult modes;
- UWB/TDoA changes the measurement model;
- raw IMU orientation/dead reckoning becomes reliably usable.
