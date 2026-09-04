# IMU analysis snapshot — 2026-09-04

This directory preserves the reviewed analysis artifacts produced from the
2026-09-04 PuttTrack Research Ball IMU export. It is a **research snapshot**,
not a product-accuracy claim and not Gameplay authority.

## Scope

The first source package contains 161 unique raw captures and 113,867
`tag_motion` records. The original decision-relevant semantic set was small,
and later reviewed experiment directories now add no-lift handling,
rolling-pickup, pickup/carry, pickup/drop, gentle-putt, rail-collision and
course-step controls without rewriting this historical archive.

The current finding is that short positive vertical impulse combined with
one-second gyro energy and rotation-axis consistency is useful pickup evidence,
but a hard threshold is not the final state-recognition architecture. The
selected next architecture is a physics-guided dual-head Logistic-emission +
explicit-duration HSMM recognizer with first-class UNKNOWN; see
[`../IMU_ALGORITHM_DECISION_20260904_CN.md`](../IMU_ALGORITHM_DECISION_20260904_CN.md).

## Files

- `IMU_ANALYSIS_REPORT_CN.md` — full Chinese engineering analysis and recommendation.
- `PICKUP_DETECTOR_V0_RESEARCH_ONLY.md` — explicit research-only detector definition and authority boundary.
- `../../../configs/research/pickup_detector_v0.json` — exact frozen V0 onset/feature thresholds.
- `pickup_binary_research_set.csv` — preserved 22-episode feature/label ledger used for the three-feature baseline replay.
- `model_reproduction_spec.json` — exact scikit-learn version, features, preprocessing scope and hyperparameters for the reproducible three-feature baselines.
- `model_benchmark_reproduced_3f.csv` — reproduced whole-episode LOEO metrics for Logistic, linear/RBF SVM, depth-2 tree and Random Forest.
- `model_benchmark_fold_predictions_3f.csv` — held-out prediction for every episode/model fold.
- `model_benchmark_leave_one_episode_out.csv` — original reviewed snapshot table; its post-hoc physics row and legacy full-feature rows remain historical/reporting artifacts.
- `next_capture_plan.csv` — historical minimum capture matrix; later experiment directories and the canonical next-engineering plan supersede repeated same-session collection.
- `dataset_manifest_audit_summary.csv` — category-level audit derived from the full manifest.
- `MANIFEST.csv` / `MANIFEST.json` — complete row-level provenance, label-quality, health, clipping, timing and SHA-256 audit for all 161 unique captures in the first-campaign archive.
- `SHA256SUMS.txt` — checksums for every byte-preserved raw JSONL in the archive.
- `../../../datasets/putttrack_imu_dataset_20260904.zip` — canonical immutable first-campaign archive.
- `GITHUB_NEXT_CHANGE_RECOMMENDATION.md` — original evaluator implementation recommendation retained as design history.
- `REVIEW_NOTES_AND_OPEN_QUESTIONS.md` — post-merge review, resolved reproducibility items and remaining evidence gaps.
- `figures/01_pickup_feature_space.svg` — current pickup/putt/roll feature-space view.
- `figures/02_representative_gyro_traces.svg` — representative rotation traces aligned to detected onset.
- `figures/04_model_benchmark.svg` — baseline model comparison.

Executable baseline reproduction:

```bash
pip install '.[research-ml]'
python tools/reproduce_pickup_snapshot_20260904.py
```

The script is pinned to scikit-learn `1.8.0`, fits `StandardScaler` inside each
LOEO training fold where applicable, reproduces the five three-feature model
confusion matrices and rewrites the reproduced summary/fold files
deterministically.

## Frozen V0 source replay

The raw-source evaluator is now implemented in research tooling:

```text
src/putttrack/motion/pickup_v0.py
configs/research/pickup_detector_v0_eval_profile.json
tools/evaluate_pickup_detector.py
```

The frozen evaluator has now been run over every reviewed precision manifest;
the versioned per-episode decisions and grouped confidence bounds are in
[`pickup_v0_holdout_eval/`](pickup_v0_holdout_eval/). Rolling-start pickup
remains an explicitly unsupported V0 path, and UNKNOWN is never counted as a
negative.

## Decision boundary

Do not infer product accuracy from the current post-hoc rule replay or the
22-episode ML baseline. The detector still requires separately frozen
new-day/operator/Ball/surface evidence before any automatic gameplay claim.

Do not copy thresholds into Gameplay or scoring code. Both frozen V0 and the new
PG-DH-HSMM V1 research architecture remain `authority=false` and output generic
motion evidence only.

## Data policy

The immutable first-campaign ZIP, its complete row-level manifest and all newer
reviewed experiment batches are versioned in Git. Duplicate working copies,
incomplete/live `runs/` and captures without accepted PuttTrack provenance stay
local. The ZIP is historical and must not be regenerated in place; publish a
new dated archive when later reviewed batches need a consolidated export.
