# Frozen pickup V0 raw replay

This directory is the deterministic source-JSONL replay requested by the
PG-DH-HSMM V1 research plan. It is a research evaluation snapshot with
`authority=false`, not a product or gameplay-accuracy claim.

## Scope and result

Seven reviewed precision manifests supplied 72 episodes:

- 10 `rolling_pickup` episodes are outside stationary-start V0 and are reported
  as unsupported;
- 2 explicitly mixed episodes are excluded from clean metrics;
- 60 episodes are metric-eligible;
- 41 receive a definitive decision and 19 return `UNKNOWN`;
- definitive rows contain TP=20, TN=21, FP=0, FN=0.

Definitive coverage is 0.683 (Wilson 95% interval 0.558–0.787). The observed
false-pickup rate is zero, but its Wilson 95% upper bound is still about 0.088.
Ten rail-collision and nine clean gentle-putt episodes return `UNKNOWN` because
the BMI270 gyro clipped. UNKNOWN is never converted to NOT_PICKUP.

The apparent 100% precision/recall among definitive rows is not independent
product validation: the data are dominated by one day, one operator and one
Ball, and lack independent physical/video event truth.

## Files

- `episode_decisions.csv` contains provenance, frozen configuration hashes,
  features, decisions and reason codes for every episode.
- `evaluation_report.json` contains overall and label/session/operator/core/
  surface grouped metrics with Wilson intervals.

## Reproduction

```bash
PYTHONPATH=src python tools/evaluate_pickup_detector.py \
  experiments/research_ball_r1_pickup_precision_1a/manifest.json \
  experiments/research_ball_r1_pickup_precision_1b/manifest.json \
  experiments/research_ball_r1_pickup_precision_1c/manifest.json \
  experiments/research_ball_r1_pickup_precision_1c_drop/manifest.json \
  experiments/research_ball_r1_pickup_precision_1d_gentle/manifest.json \
  experiments/research_ball_r1_pickup_precision_1e_rail/manifest.json \
  experiments/research_ball_r1_pickup_precision_1e_step/manifest.json \
  --output-dir docs/research/imu_analysis_20260904/pickup_v0_holdout_eval
```
