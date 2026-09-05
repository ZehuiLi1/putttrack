# Implementation provenance

- Baseline: PR #25 `ad566404272dc6f5695cb84fd551df5921f7f619`; main/frozen V0 unchanged.
- Inventory: 84 repository raw captures plus 152 archive-only files, nine exact duplicates excluded.
- Initial C implementation replayed all 236 unique files: 10/10 clean, 5/10 rail, 19/20 pickup, 0/10 no-lift candidates.
- Inspected raw early versus full-second gyro windows in the five missed rail cases.
- Inspected the missed pickup's stable ~9.995 m/s2 prebaseline and small noise.
- Added early launch proposal plus long pickup head and measured local baseline.
- A development variant prematurely counted two archived pickup episodes as strokes. Final V1 changed to a non-counting proposal and pickup-first resolution; no claim of untouched validation.
- Retained initial C/config under `tools/research_baselines/stroke_pickup_initial` and rerunnable initial report.
- Added full raw capture + on-MCU event journal + independent truth review/timing audit.
- Host validation and exact-target NCS compilation are separate. Neither means physical test-boot, real timing truth or device-key signing occurred.
- Initial local verifier hit a noexec `/tmp` restriction in a pre-existing C test. Re-run with an executable TMPDIR passed; no detector threshold was changed to satisfy this environmental error.
- CI uses a disposable test signing key. No physical Ball credential, private signing key or deployable update package is published.
