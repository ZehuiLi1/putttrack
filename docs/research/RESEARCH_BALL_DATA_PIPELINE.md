# Research Ball offline data pipeline

## Purpose

This pipeline was designed to be usable before the Research Ball was assembled.
It now also validates the first checked-in physical two-orientation stationary
dataset at `experiments/research_ball_r0_stationary`, while synthetic captures
continue to exercise the path in CI.

It does **not** define impact, rolling, pickup or settling thresholds. Those remain evidence-gated until mechanically repeatable Research Ball data exists.

New captures must use the full expected Tag device ID. The capture session now
checks device, boot, firmware, sequence/time continuity and health-counter
deltas before the offline dataset accepts the file; see
[`TAG_MULTI_DEVICE_IDENTITY.md`](../hardware/TAG_MULTI_DEVICE_IDENTITY.md).

## Dataset layout

Keep raw captures immutable and describe the physical setup in a separate versioned manifest:

```text
research-ball-v0/
├── manifest.json
├── stationary-001.jsonl
├── putt-medium-001.jsonl
├── rolling-001.jsonl
└── ...
```

A minimal manifest is:

```json
{
  "schema_version": 1,
  "dataset_id": "research-ball-v0-pilot",
  "defaults": {
    "core_revision": "RB-V0.1",
    "shell_revision": "S1",
    "mass_g": 47.8,
    "surface": "practice-putting-mat"
  },
  "episodes": [
    {
      "episode_id": "stationary-001",
      "capture": "stationary-001.jsonl",
      "label": "stationary",
      "session": "20260903-A",
      "trial": "001",
      "orientation": "random"
    },
    {
      "episode_id": "putt-medium-001",
      "capture": "putt-medium-001.jsonl",
      "label": "impact_tap",
      "session": "20260903-A",
      "trial": "002",
      "orientation": "random",
      "strength": "medium",
      "video_ref": "camera-A-0002"
    }
  ]
}
```

Recommended metadata fields are:

- `episode_id` — unique immutable episode identifier;
- `capture` — JSONL path relative to the manifest;
- `label` — physical action label, not a gameplay conclusion;
- `session`, `trial` — repeatability/grouping identifiers;
- `core_revision`, `shell_revision` — exact mechanical build;
- `mass_g` — assembled Research Ball mass;
- `surface`, `orientation`, `strength` — physical test conditions;
- `video_ref` — independent visual/time reference when available;
- `operator`, `notes` — optional provenance.

Do not reuse one capture for multiple episode entries. Do not reuse an `episode_id`.

## Run the offline analysis

```bash
python tools/analyze_motion_dataset.py \
  path/to/research-ball-v0/manifest.json \
  --output-dir path/to/research-ball-v0/analysis
```

Outputs:

```text
analysis/
├── dataset_summary.csv
├── dataset_summary.json
├── quality_report.json
└── plots/
    ├── stationary-001.svg
    └── ...
```

The CSV/JSON preserve the manifest metadata together with the existing deterministic features:

- sample count, duration and observed rate;
- sequence gaps and valid fraction;
- acceleration norm statistics;
- gyro RMS/max;
- jerk RMS/peak;
- active fraction and first/last activity offsets;
- ADXL367, BMI270 accelerometer and BMI270 gyro clipping counts;
- the existing conservative `STATIONARY_CANDIDATE`, `ACTIVE_MOTION_CANDIDATE` or `UNCLASSIFIED` diagnostic.

SVG plots are generated using only the Python standard library. CI and a field laptop therefore do not need matplotlib.

## Quality semantics

`quality_status` is deliberately separate from motion semantics:

- `PASS` — source ordering/sensor validity/metadata consistency passed and no clipping was observed;
- `WARN` — capture is structurally usable but at least one sensor clipped;
- `FAIL` — sequence gaps, invalid sensor samples, multiple embedded labels or a manifest/capture label mismatch exist.

A `PASS` does **not** mean the physical label is classified correctly. A `WARN` impact episode may still be scientifically useful for timing/state-transition work but must not be used for amplitude calibration without accounting for saturation.

## Current verification boundary

`tests/test_motion_dataset.py` generates synthetic stationary/active/clipped captures at test time and validates:

- manifest defaults and metadata preservation;
- duplicate episode rejection;
- deterministic feature extraction;
- clipping surfacing;
- dependency-free SVG generation;
- the end-to-end CLI outputs.

The mechanically restrained Research Ball now has two immutable 1,024-sample
stationary captures and generated reports under
`experiments/research_ball_r0_stationary`. Both physical episodes pass integrity
and provisional stationary checks. They establish static transport/noise only;
controlled impact, rolling, settling and stop episodes must provide the evidence
for any threshold or model decision.
