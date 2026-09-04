# Versioned research datasets

## `putttrack_imu_dataset_20260904.zip`

This is the canonical, immutable export of the first PuttTrack Tag IMU data
collection campaign. It contains 161 unique, byte-preserved JSONL captures and
113,867 `tag_motion` records, together with provenance, quality annotations,
field definitions, duplicate detection and per-file SHA-256 checksums.

The archive covers:

- early firmware, stationary, wake and manual-motion experiments;
- the curated stationary and manual-floor baselines;
- preliminary and complete programmable-roller characterization;
- the first pickup/carry and nominal-putt field batches;
- three captures retained only for failure/transport diagnosis.

Not every filename is valid semantic ground truth. Read `MANIFEST.csv` inside
the archive before analysis, and exclude `90_diagnostic_or_invalid` from
supervised training. The unrelated `imu_data_20250306_161150.csv` is deliberately
excluded because it has no accepted PuttTrack provenance.

Archive SHA-256:

```text
3a78231c9d3e546cfb00782b91ca310ce98f5fc6b474d6e5f7c7c7170f5701bb  putttrack_imu_dataset_20260904.zip
```

The row-level manifest is also available without downloading the archive at
[`../docs/research/imu_analysis_20260904/MANIFEST.csv`](../docs/research/imu_analysis_20260904/MANIFEST.csv).
Newer holdout batches remain in their individual `experiments/` directories so
this historical archive stays reproducible and unchanged.
