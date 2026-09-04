# Review notes and open questions

This note records the repository review performed after PR #21 was merged. It
does not reject the snapshot; it separates useful conclusions from claims that
are not yet reproducible from Git alone.

## Accepted direction

- Pickup precision is the first semantic IMU gate.
- Gravity reversal and acceleration peak are not standalone pickup rules.
- The current vertical-impulse, gyro-energy and axis-consistency combination is
  worth freezing as a research hypothesis.
- The detector remains on Host/Edge and has `authority=false` until an untouched
  holdout passes.
- No-lift handling and rolling pickup are the next most valuable classes.
- A neural network is not justified by the current independent episode count.

## Reproducibility gaps in the snapshot

1. `model_benchmark_leave_one_episode_out.csv` contains aggregate results but
   no executable feature table/build script, exact episode list, fold outputs,
   preprocessing fit scope, random seed or model hyperparameters. The reported
   `0.957` F1 values cannot yet be independently reproduced from the repository.
2. The `physics_rule` row is post-hoc/in-sample, not leave-one-episode-out. It
   must remain visually and machine-readably separate from trained LOEO rows.
3. The feature-space and representative-trace figures do not identify every
   source JSONL or publish their generating code. They are explanatory figures,
   not immutable derived evidence.
4. The V0 description says "approximately" 0.6 and 1 second but does not fully
   define motion onset, filters, vertical propagation/integration, clipping,
   missing baseline or boundary behavior. An exact versioned config and tested
   evaluator are required before looking at holdout results.
5. Episode-level LOEO does not test new-day, new-operator, new-Ball or new-
   surface generalization because the current semantic set is mostly one
   session/operator/assembly.

## Data and naming corrections

- The canonical local bundle name is `putttrack_imu_dataset_20260904.zip`.
- `imu_data_20250306_161150.csv` is not in the PuttTrack package or repository,
  has no accepted provenance here and must remain excluded. It may belong to an
  unrelated project previously mentioned by the operator.
- The executable capture profile IDs are `handling`, `rolling_pickup`,
  `pickup_carry`, `putt_gentle`, `putt_normal`, `putt_firm`,
  `putt_rail_collision` and `track_step_drop`. Planning tables must use these
  names rather than inventing aliases that the UI cannot run.
- `cup_sequence` remains a planned future profile because cup geometry and
  independent physical truth are not yet present.

## Merge gate for a detector claim

The next evaluator may be merged as research tooling before holdout collection,
but a product-facing accuracy or automatic invalidation claim requires:

- an exact frozen detector/config version;
- source-identified, independently labelled holdout episodes;
- grouped metrics and confidence bounds;
- explicit results for no-lift handling and rolling pickup;
- documented UNKNOWN behavior for baseline, health, timing and clipping faults;
- confirmation that no holdout result was used to alter V0 thresholds.

