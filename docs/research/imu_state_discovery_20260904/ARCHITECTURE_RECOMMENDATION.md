# PuttTrack Research Ball IMU — Full State Discovery Result

Generated from repository data; research-only; `authority=false`.

## Data audit

- unique raw episodes analysed: **233**
- semantic manifest episodes used for model discovery: **122**
- devices / boots / sessions / operators: **1 / 17 / 26 / 2**
- median sample rate: **50.00 Hz**
- sequence-gap episodes: **3**
- BMI270 gyro-clipped episodes: **33**

Classes confined to one session/manifest group: `COLLISION_RAIL, IMPACT_TAP, ROLLING_PICKUP`. This prevents a commercial generalisation claim even when leave-one-episode-out scores are high.

## Empirical model comparison

Best exploratory flat multiclass baseline: **extra_trees**, LOEO macro-F1 **0.729**. This is not a production accuracy estimate because episodes from the same day/operator/Ball remain correlated.

Best exploratory rolling-disruption baseline: **rbf_svm**, LOEO macro-F1 **0.875**.

Frozen V0 reconstruction replay (no threshold changes): `{"episodes": 72, "unknown": 31, "quality_excluded": 2, "unsupported_path_episodes": 10, "metric_eligible_episodes": 60, "metric_eligible_unknown": 19, "config_path": "configs/research/pickup_detector_v0.json", "config_sha256": "62c82c1a313f70912a5bb6c2f53c635fe179c537cdb3738dbc5d2a347050c8ad", "note": "Exact frozen-config replay; UNKNOWN is retained and never counted as NOT_PICKUP.", "metric_eligible_definitive": 41, "tn": 21, "fp": 0, "fn": 0, "tp": 20, "precision": 1.0, "recall": 1.0, "f1": 1.0, "specificity": 1.0, "mcc": 1.0}`. UNKNOWN is retained and is not counted as a true negative.

## Final architecture decision

The recommended system is **not** one flat neural network and **not** one global threshold table. Use a hierarchical hybrid recogniser:

```text
ADXL367 motion wake / low-power guard
    -> BMI270 FIFO event burst
    -> signal health + clipping + continuity gate
    -> multi-scale physics feature bank (0.1 / 0.2 / 0.5 / 1 / 2 s)
    -> hierarchical finite-state / semi-Markov controller
       STATIONARY -> ACTIVE -> ROLLING -> DISRUPTION -> POST_TRANSITION
    -> state-specific small probabilistic classifier
       Path A: stationary pickup vs no-lift / putt
       Path B: rolling pickup vs rail collision / step / natural settling
    -> calibrated confidence + explicit UNKNOWN
    -> generic MotionEvidence only
    -> venue context + Tee/Cup/feature sensors -> Gameplay authority
```

### Model choice now

Use **regularised Logistic Regression first** for each state-specific branch, with an **Extra-Trees challenger** on Edge during research. Logistic is the production candidate now because the independent episode count is small, its evidence can be calibrated and audited, and its implementation can be reduced to a fixed feature vector plus dot products. Keep Extra-Trees only if a future untouched multi-operator/multi-Ball holdout demonstrates a statistically meaningful gain at the same false-event ceiling.

### Temporal controller

Use a hierarchical **explicit-duration FSM / HSMM-like policy**, not an unconstrained framewise classifier. State dwell, hysteresis, refractory intervals, legal transitions, and post-disruption persistence are part of the signal definition. A classifier emits likelihoods; the temporal controller decides whether a candidate state is sufficiently persistent, and low confidence becomes UNKNOWN.

### What 50 Hz can and cannot support

At 50 Hz the current data can support stationary/activity, sustained rolling shape, pickup/carry, rolling-model departure, and coarse settling. It cannot validate exact putter-impact timing or reliably distinguish putter contact from wall/ball contact from the transient alone. Capture normal motion at 200–400 Hz and retain an 800 Hz–1.6 kHz accelerometer/FIFO burst around impact candidates before trying to give IMPACT/COLLISION subtypes product authority.

### Neural-network gate

Do not deploy a TCN/CNN now. Re-open that comparison only after at least two Balls, multiple operators/days/surfaces, independent event timestamps, and hundreds of genuinely independent episodes per difficult branch. The data-driven ROCKET-lite result in this report is a small-data temporal challenger, not evidence that an end-to-end neural model will generalise.

## Commercial validation gates

1. Freeze feature/schema/model version before collection.
2. Blind holdout by day + operator + Ball + surface, never random adjacent windows.
3. Report event precision/recall, false events per player-hour, P50/P95 latency, UNKNOWN rate, clipping, and exact confidence intervals.
4. Auto-penalty requires a much higher precision gate than non-authoritative telemetry.
5. Cup/feature completion remains physical-sensor/venue-confirmed.

No result in this report establishes Puttshack-equivalent commercial accuracy; it establishes the most defensible architecture and the next validation path.
