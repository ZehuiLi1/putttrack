# Patent Research — World Golf Systems / Puttshack Movement Signatures

## Purpose

This document records public patent disclosures relevant to PuttTrack research. It is intended to:

1. understand prior art;
2. reconstruct testable benchmark ideas from public disclosures and our own data;
3. separate current deployable engineering from patent-sensitive research;
4. define future legal/FTO checkpoints.

It is **not** legal advice and does not determine infringement, validity or freedom to operate.

---

## 1. Key Movement-Signature Family

Relevant family members include:

- `WO2013156778A1` — Ball game apparatus;
- `US9808677B2` — Ball game apparatus;
- `AU2013250910B2` — Ball game apparatus;
- related EP / CA / JP / CN family members.

Public metadata for `AU2013250910B2` records:

- priority date: 2012-04-18;
- filing date: 2013-04-18;
- grant/publication: 2017;
- Google Patents currently labels the Australian patent **Active** and records a 2023 licence event for Puttshack Limited.

Treat Google Patents legal-status labels as research metadata only; confirm current Australian status through official records / counsel before making commercial decisions.

### 1.1 Core granted concept

The US granted independent claim is important because it expressly combines:

- a plurality of balls and holes;
- a predetermined allowable movement range over space and time;
- translational acceleration sequences;
- rotational acceleration sequences;
- valid shot sequences for each hole;
- specific ball movements forming a movement signature;
- a respective movement signature for each hole used to identify valid strokes;
- sensing actual movement;
- comparison against the allowable range;
- indicating the comparison result.

This is the main reason PuttTrack currently treats **hole-specific movement-signature scoring** as a research benchmark rather than the default commercial scoring architecture.

---

## 2. What the Public Patent Teaches Technically

The public description goes beyond a generic statement that an IMU can detect movement.

### 2.1 Ball sensing

Embodiments discuss multi-axis motion sensing and combinations corresponding conceptually to:

- accelerometer;
- gyroscope;
- magnetometer;
- 3-axis, 6-axis or 9-axis sensing configurations.

### 2.2 Valid vs invalid movement

The disclosure describes using movement evidence to distinguish a genuine shot from other ways a ball can move, including examples such as:

- pickup / carry;
- dragging;
- rolling by hand;
- dropping;
- another ball striking the tracked ball.

### 2.3 Hole-specific signatures

The description gives examples where a hole's physical design creates an expected sequence, for example:

```text
putt -> uphill motion -> crest -> downhill roll
```

and a failed attempt could instead look like:

```text
putt -> uphill deceleration -> rollback
```

The patent also discusses route / timing / spin / acceleration context when determining whether a movement is plausible for a particular hole.

### 2.4 Cup-entry dynamics

The description provides a useful qualitative cup-entry example:

```text
rolling
  -> drop at cup edge
  -> bottom impact
  -> decreasing bounces
  -> stationary
```

This is technically interesting even outside the patent question because it suggests that an IMU may provide high-confidence cup evidence without requiring every event to be inferred from XY position alone.

---

## 3. What the Patent Does NOT Give Us

The public patent does not disclose a production-ready Puttshack algorithm. It does not give us, for example:

- exact sensor part numbers used in the original implementation;
- exact IMU sample rate;
- acceleration / gyro full-scale settings;
- exact digital filters;
- exact segmentation thresholds;
- production feature vectors;
- per-hole numerical thresholds;
- classifier architecture;
- training data;
- false-positive / false-negative targets;
- current Trackaball firmware.

Therefore any PuttTrack movement-signature implementation must be described as **our own experimental reconstruction** using our own labelled data.

---

## 4. Later World Golf Systems / Puttshack Patent Families

Do not treat expiry of one family as automatic clearance of the whole product concept.

### 4.1 2015-priority ball-game-apparatus family

Examples include `US11724172B2` and later continuation/grant activity.

Public disclosures cover combinations such as:

- coded balls;
- player-to-ball allocation;
- detector units around the course;
- temporary storage / intermittent transfer of ball movement data;
- server / database architecture;
- ball power-management behaviour;
- charging infrastructure;
- ball activation / deactivation workflows;
- camera replay and related venue functions.

The granted US claims are not identical to the earlier movement-signature claim set, so each family must be reviewed independently.

### 4.2 Later communication-system family

Later public filings also cover golf-ball / tee communication concepts, including magnetic / coded tee interactions in some claims and embodiments.

Conclusion: **2033 is a review horizon, not a guaranteed switch date.**

---

## 5. Patent-Term Planning

The Australian movement-signature family member was filed in 2013. A standard Australian patent ordinarily has a maximum 20-year term from filing, subject to maintenance and legal events. That places the ordinary maximum-term horizon around 2033 for this family.

PuttTrack decision rule:

- do **not** assume the patent is expired until the status is checked at that time;
- do **not** assume other relevant families expire at the same time;
- do **not** assume expiry automatically clears every implementation detail;
- conduct a claims-based FTO review against the final product architecture.

---

## 6. Research Reconstruction — Movement Signature

The benchmark should use our own engineering definitions and data.

### 6.1 Episode segmentation

Segment an episode from first meaningful movement until stable rest.

Candidate state vocabulary:

- `STATIONARY`
- `IMPACT`
- `ROLLING`
- `SLOWING`
- `COLLISION`
- `PICKED_UP`
- `CARRIED`
- `DROP`
- `BOUNCE`
- `UNKNOWN`

### 6.2 Candidate translational features

- peak acceleration magnitude;
- RMS acceleration;
- jerk statistics;
- event duration;
- acceleration integral / impulse proxy;
- vertical acceleration profile;
- rolling-decay characteristics;
- impact count;
- inter-impact timing.

### 6.3 Candidate rotational features

- peak angular rate;
- angular-rate RMS;
- spin / roll decay;
- sustained rotation duration;
- rotation-axis stability;
- abrupt rotation-axis changes.

### 6.4 Candidate sequence features

Examples to test from our own recordings:

```text
impact -> rolling -> slowing -> rest
```

```text
roll -> drop -> impact -> decaying bounces -> rest
```

```text
impact -> uphill deceleration -> rollback -> rest
```

```text
pickup -> carried motion -> replacement
```

```text
ball-ball collision without a preceding local putter-impact pattern
```

These are PuttTrack benchmark features, not a statement of Puttshack's production formulas.

---

## 7. Classifier Ladder

Use interpretable baselines before complex ML:

1. rule / threshold state machine;
2. normalised feature-distance classifier;
3. Dynamic Time Warping (DTW);
4. Hidden Markov / state-sequence model;
5. tree-based classifier;
6. compact temporal neural model only if simpler models are inadequate.

The purpose is to quantify what is gained by increasing model complexity.

---

## 8. Hole-Specific Benchmark

For research comparison only, define a hole profile from our own labelled trials, for example:

```yaml
hole_id: H01
allowed_sequences:
  - tee_putt_roll_stop
  - tee_putt_ramp_roll_stop
constraints:
  expected_phases:
    - impact
    - rolling
    - slowing
    - stationary
```

Compare this with a hole-independent generic motion model.

Metrics:

- valid-stroke precision / recall / F1;
- false-stroke rate;
- route recognition accuracy;
- cup-entry recognition;
- latency;
- energy per classified event.

---

## 9. Current PuttTrack Position

### Spatial-first production/research path

```text
Channel Sounding position
+ generic IMU state
+ course geometry
+ optional feature sensor truth
-> Game Event Engine
```

### Patent benchmark

```text
translational + rotational motion sequence
-> movement signature
-> hole-specific comparison
-> valid / invalid stroke
```

### Possible future hybrid

After technical evidence and legal review, movement-signature evidence could be evaluated as:

- an auxiliary confidence input;
- a false-stroke rejection input;
- cup-entry confirmation;
- a fallback when RF geometry is poor;
- a way to lower Channel Sounding update rate.

It does not need to become the sole scoring truth.

---

## 10. Legal Decision Gates

### Gate L0 — now

- research public patent material;
- implement the spatial-first CS architecture;
- collect our own IMU / CS / camera datasets;
- keep hole-specific signature experiments explicitly labelled as research benchmarks.

### Gate L1 — before commercial use of a claim-sensitive architecture

Obtain Australian patent counsel review of:

- exact granted AU claims;
- prosecution history / amendments;
- current status / renewal events;
- relevant later World Golf Systems / Puttshack families;
- other third-party patents;
- a claim chart against the actual proposed PuttTrack system.

### Gate L2 — 2032/2033 horizon

Re-run the landscape and decide from both technical evidence and current legal status whether to:

- remain spatial-first;
- add generic motion signatures;
- add legally cleared hole-specific signatures;
- license relevant IP if commercially attractive;
- use a technically superior hybrid architecture regardless of expiry.

---

## 11. Source References

Primary patent identifiers to review:

- `US9808677B2`
- `AU2013250910B2`
- `WO2013156778A1`
- `US11724172B2`
- related later continuation / communication-system families

For current legal status, use official patent registers and professional advice rather than relying solely on aggregator status labels.
