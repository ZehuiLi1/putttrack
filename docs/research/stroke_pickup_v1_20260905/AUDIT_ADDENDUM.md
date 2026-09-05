# Final audit addendum — 2026-09-05

This note takes precedence over any broader wording in the initial delivery README/PR description. The algorithm and frozen replay outputs are unchanged.

## Archived normal-putt denominator

The raw replay reports 8 one-candidate outputs across 10 archival files under `07_field_putt`. The two other files were already classified in the historical archive before this implementation:

| Capture | Existing archival quality | Observed shadow result |
|---|---|---|
| `field-20260904-132804-1-putt_normal-r05` | `invalid_no_motion` | No motion onset or stroke candidate |
| `field-20260904-132804-1-putt_normal-r06` | `invalid_timing_or_action` | Unresolved transients, no stroke candidate |

Their raw SHA-256 values are respectively `3a9f50512cb2a8f5d20cf9786f8ab97f70349d09fbb399c2c04406383679c904` and `0e1c82f37a8eb87a3b329e6f37d21c3022d057bb0777b6d07ec2f9ece1c13176`.

Therefore **8/10 describes outputs across archived files, not an 80% recall estimate and not two established false negatives**. The other eight files produce one candidate each, but still have no independent putter-contact timestamps. They must not be combined with the new-data physical gate to claim validated accuracy. All ten remain visible in `replay_v1/capture_results.csv`; no inconvenient row was deleted after tuning.

The two reviewed manual hand-roll false stroke candidates are genuine known challenge cases and remain unresolved. The ten rolling-pickup captures remain unsupported by the stationary-start pickup path.

## Target CI false-green finding

The first `Stroke Pickup Shadow V1` run, `33951422669`, correctly materialized the source and passed the host/replay jobs. Its NCS job returned success **without running the build script**. Log inspection found no west/compiler output or verified build artifacts.

The public Nordic image config has `Entrypoint=["/bin/bash","-c"]`. Passing `bash` and the script path as separate trailing Docker arguments runs the first word as the command and leaves the script as a positional parameter. An empty shell can therefore return zero.

Commit `8d84a1b86a0b549372678b2653c33dc67ca74050` replaces that invocation with an explicit Bash entrypoint and one complete command string. It also requires nonempty ELF, signed BIN and linker map **from the host after the container exits**, verifies V1/NFC/version config and the `spv1_push` symbol, and retains compile diagnostics only. The one-off write-enabled source-delivery step has been removed; the continuing workflow is read-only.

**Do not cite the first NCS job's green status as compile evidence.** Only a subsequent run containing real compiler output and passing the artifact/config checks can establish source compatibility. It still cannot establish physical action accuracy or produce a device-trusted update image: the CI signing key is disposable.

## Physical acceptance remains separate

No physical Ball flash, test boot, device-key signing, measured current or new operator/video-truth trial was performed by this implementation pass. The field tool is provided for that next gate; main and the currently confirmed Ball image were not modified.
