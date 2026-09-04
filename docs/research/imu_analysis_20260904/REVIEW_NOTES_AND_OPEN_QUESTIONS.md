# Review notes and open questions

This note records the repository review performed after PR #21 was merged and
the reproducibility follow-up performed against the preserved first-campaign
delivery bundle, which is now versioned under `datasets/`. It does not promote
the snapshot to product evidence; it separates resolved
documentation/reproduction questions from evidence that still requires new
physical data.

## Accepted direction

- Pickup precision is the first semantic IMU gate.
- Gravity reversal and acceleration peak are not standalone pickup rules.
- The current vertical-impulse, gyro-energy and axis-consistency combination is worth freezing as a research hypothesis.
- The detector remains on Host/Edge and has `authority=false` until an untouched holdout passes.
- No-lift handling and rolling pickup are the next most valuable classes.
- A neural network is not justified by the current independent episode count.

## Reproducibility review — resolved items

The post-PR #21 review correctly identified that the published small-model aggregate table did not contain enough information to reproduce the model scores. The local delivery bundle still contained the episode-level feature ledger, so the following have now been preserved in Git:

- `pickup_binary_research_set.csv` — exact 22-episode paths, labels, quality notes, three features, target and post-hoc rule output;
- `model_reproduction_spec.json` — exact features, fold policy, scikit-learn version and model hyperparameters;
- `model_benchmark_fold_predictions_3f.csv` — every LOEO held-out prediction;
- `model_benchmark_reproduced_3f.csv` — regenerated aggregate metrics;
- `tools/reproduce_pickup_snapshot_20260904.py` — executable reproduction, pinned to scikit-learn `1.8.0` through the `research-ml` optional dependency.

Reproduction independently regenerates the reported three-feature results:

- Logistic Regression: pickup F1 `0.9565`, confusion `TN=10, FP=1, FN=0, TP=11`;
- linear SVM: pickup F1 `0.9565`, same confusion;
- RBF SVM: pickup F1 `0.9565`, same confusion;
- depth-2 tree: pickup F1 `0.9091`, confusion `TN=10, FP=1, FN=1, TP=10`;
- Random Forest: pickup F1 `0.9565`, confusion `TN=10, FP=1, FN=0, TP=11`.

The repeated-taps episode remains the common false positive for Logistic/SVM/RF. This confirms the earlier interpretation that the immediate limitation is semantic negative diversity rather than a need for a larger model.

The earlier `physics_rule` row remains explicitly **post-hoc/in-sample** and is not LOEO. It must not be combined with trained-model holdout metrics.

The exact frozen V0 onset/feature definition is now versioned in `configs/research/pickup_detector_v0.json`. It remains `authority=false` and supports only stationary-start pickup; rolling-start pickup remains an explicitly unsupported path until new data exists.

## Remaining evidence/reproducibility limits

These are not documentation bugs and should not be hidden by additional software-only work:

1. The reproduced ML baseline starts from the preserved episode-level feature ledger. The original first-campaign field JSONL and complete manifest are now in Git, so source-derived feature extraction can be independently implemented and checked. The current reproduction script still consumes the frozen feature ledger rather than recomputing those features from JSONL.
2. The original `logistic_full` and `rf_full` rows remain historical reported values because the complete full-feature definition was not preserved. Do not cite them as reproducible evidence.
3. The current feature-space/model figures are explanatory snapshot figures. They are not a substitute for raw-source-derived evidence.
4. Episode-level LOEO still does not test new-day, new-operator, new-Ball or new-surface generalization because the current semantic set is mostly one session/operator/assembly.
5. Rolling-start pickup remains unvalidated. The frozen stationary-start V0 must return UNKNOWN / unsupported rather than silently applying stationary-start assumptions to a rolling pickup.

## Data and naming corrections

- The canonical versioned bundle is `datasets/putttrack_imu_dataset_20260904.zip`; it contains 161 unique captures and 113,867 `tag_motion` records.
- `imu_data_20250306_161150.csv` is not in the PuttTrack package or repository, has no accepted PuttTrack provenance and remains excluded. Do not reintroduce it unless its origin is independently established.
- The executable capture profile IDs are `handling`, `rolling_pickup`, `pickup_carry`, `putt_gentle`, `putt_normal`, `putt_rail_collision` and `track_step_drop`. Planning tables should use these executable IDs.
- `handling` is the strict no-lift control: the Ball remains in continuous surface contact.
- `cup_sequence` remains a planned future profile because cup geometry and independent physical truth are not yet present.

## Next data gate

The current hypothesis is now frozen before the next untouched batch. Collect in this order:

1. `handling`: strict no-lift touch/press, in-place rotate and short slide controls;
2. `rolling_pickup`: slow/medium/fast rolling pickups and near-stop pickups;
3. a separately named `pickup_carry` holdout with varied lift speed, grip and initial orientation;
4. clean putts plus `putt_rail_collision` / `track_step_drop` controls;
5. at least one separate day/session/operator holdout before any product-facing accuracy claim.

Do not change `pickup_detector_v0_stationary_start` after viewing these holdout results. If the hypothesis must change, create a new detector ID/version and evaluate it on a later untouched set.

## Merge gate for a detector claim

A product-facing accuracy or automatic invalidation claim requires:

- an exact frozen detector/config version;
- source-identified, independently labelled holdout episodes;
- grouped metrics and confidence bounds;
- explicit results for no-lift handling and rolling pickup;
- documented UNKNOWN behavior for baseline, health, timing and clipping faults;
- confirmation that no holdout result was used to alter V0 thresholds;
- continued separation between Ball motion evidence and Gameplay/scoring authority.
