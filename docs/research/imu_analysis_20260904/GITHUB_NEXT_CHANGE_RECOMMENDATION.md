# Recommended next GitHub change

The current repository direction is already correct: motion is generic evidence, not score authority, and Channel Sounding is deferred from the active MVP.

Do not merge the present thresholds into Gameplay.

Recommended next branch:

`research/pickup-holdout-evaluator-20260904`

Suggested scope:

1. `tools/evaluate_pickup_detector.py`
   - replay a versioned detector over labelled episodes;
   - group metrics by session, operator, Ball/core revision and surface;
   - output confusion matrix, event latency, clipping and confidence intervals;
   - fail closed on label/timing/health errors.

2. `configs/research/pickup_detector_v0.json`
   - record feature-definition version and exploratory thresholds;
   - mark `authority=false` and `trained_on_dataset=20260904`.

3. `tests/test_pickup_detector.py`
   - synthetic stationary-start pickup;
   - strict no-lift control;
   - dominant-axis roll;
   - rolling-pickup transition;
   - repeated taps;
   - clipped gyro input;
   - missing pre-action stationary baseline.

4. Capture profiles and manifests
   - existing `handling` profile, whose current instruction strictly requires continuous surface contact;
   - `rolling_pickup`;
   - existing `putt_gentle` / `putt_normal` profiles;
   - existing `putt_rail_collision` and `track_step_drop` profiles;
   - future `cup_sequence` only after physical cup truth exists;
   - separate-day/operator holdout identifiers.

5. Documentation gate
   - only update product-facing status after an untouched holdout is frozen;
   - report whole-episode/session metrics, not random-window accuracy.

Research-tool merge criterion:

- raw JSONL to decision/report is deterministic and configuration-hashed;
- all structural and unsupported paths fail closed to `UNKNOWN`;
- clean, mixed, diagnostic and unsupported episodes are reported separately;
- tests cover the documented numerical and failure paths;
- frozen V0 thresholds are unchanged;
- detector remains evidence-only with `authority=false`.

An untouched separate-date/operator/Ball holdout and acceptable pickup
precision/false-positive confidence bounds remain mandatory for a later
product claim, but are not prerequisites for merging the evaluator itself.
