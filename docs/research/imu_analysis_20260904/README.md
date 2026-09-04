# IMU analysis snapshot — 2026-09-04

This directory preserves the reviewed analysis artifacts produced from the 2026-09-04 PuttTrack Research Ball IMU export. It is a **research snapshot**, not a product-accuracy claim and not Gameplay authority.

## Scope

The source package contained 161 unique raw captures and 113,867 `tag_motion` records. The most decision-relevant semantic evidence was still small: ten recent pickup/carry captures, ten nominal-putt captures of mixed label quality, the seven-episode manual-floor set and the completed 86-run programmable-roller characterization.

The current finding is that short positive vertical impulse combined with one-second gyro energy and rotation-axis consistency is worth validating for pickup detection. The present thresholds were selected after inspecting the same data and therefore remain post-hoc, research-only hypotheses.

## Files

- `IMU_ANALYSIS_REPORT_CN.md` — full Chinese engineering analysis and recommendation.
- `PICKUP_DETECTOR_V0_RESEARCH_ONLY.md` — explicit research-only detector definition and authority boundary.
- `../../../configs/research/pickup_detector_v0.json` — exact frozen V0 onset/feature thresholds for the next untouched batch.
- `pickup_binary_research_set.csv` — the preserved 22-episode feature/label ledger used for the three-feature baseline replay.
- `model_reproduction_spec.json` — exact scikit-learn version, features, preprocessing scope and hyperparameters for the reproducible three-feature baselines.
- `model_benchmark_reproduced_3f.csv` — reproduced whole-episode LOEO metrics for Logistic, linear/RBF SVM, depth-2 tree and Random Forest.
- `model_benchmark_fold_predictions_3f.csv` — held-out prediction for every episode/model fold.
- `model_benchmark_leave_one_episode_out.csv` — original reviewed snapshot table; its post-hoc physics row and legacy full-feature rows remain historical/reporting artifacts.
- `next_capture_plan.csv` — minimum next capture matrix for handling/no-lift, rolling pickup, clean putt, collision/step and later cup sequences.
- `dataset_manifest_audit_summary.csv` — category-level audit derived from the full local manifest; the complete row-level audit remains in the local delivery bundle.
- `GITHUB_NEXT_CHANGE_RECOMMENDATION.md` — proposed holdout-evaluator implementation scope.
- `REVIEW_NOTES_AND_OPEN_QUESTIONS.md` — post-merge review, resolved reproducibility items and remaining evidence gaps.
- `figures/01_pickup_feature_space.svg` — current pickup/putt/roll feature-space view.
- `figures/02_representative_gyro_traces.svg` — representative rotation traces aligned to detected onset.
- `figures/04_model_benchmark.svg` — baseline model comparison.

Executable reproduction:

```bash
pip install '.[research-ml]'
python tools/reproduce_pickup_snapshot_20260904.py
```

The script is pinned to scikit-learn `1.8.0`, fits `StandardScaler` inside each LOEO training fold where applicable, reproduces the five three-feature model confusion matrices and rewrites the reproduced summary/fold files deterministically.

## Decision boundary

Do not infer product accuracy from the current 11/11 pickup and 0/11 selected-negative post-hoc rule replay. The detector must first pass strict no-lift controls, rolling pickup, collision/step controls and a separately collected day/session/operator holdout.

Do not copy these thresholds into Gameplay or scoring code. The next implementation target is a host/Edge holdout evaluator that reports whole-episode/session metrics, confidence intervals, clipping and provenance while keeping `authority=false`.

The three-feature ML baseline is now reproducible from the preserved episode-level feature ledger. This does **not** make it an independent holdout result and does not make the underlying feature extraction reproducible from raw field JSONL, because those raw field runs intentionally remain outside Git. The legacy `logistic_full` / `rf_full` snapshot rows are also not promoted to reproducible evidence because their full feature definition was not preserved.

## Data policy

The generated ZIP bundle, raw field `runs/`, duplicate local captures and the complete row-level manifest audit remain local. Git contains only the reviewed analysis artifacts, compact derived episode-level evidence needed for reproducibility, and existing curated research evidence.
