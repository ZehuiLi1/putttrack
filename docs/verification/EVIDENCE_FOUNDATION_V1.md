# Evidence Foundation V1 — Verification Evidence

## Verified target

- Repository: `ZehuiLi1/putttrack`
- Branch: `foundation/evidence-contracts-replay-v1`
- Implementation target SHA: `3f15e21282a1c1c048b7983d39c713b5763edc44`
- Base Architecture main SHA: `59dfb37ad1a2182a82b69d107c7f1e3529efe4eb`
- Python: `3.13.5`
- Date: `2026-08-18`

The verification-report commit changes documentation only. The target SHA above is the exact implementation/content tree that was executed.

## Command

```bash
python tools/verify.py
```

## Result

```text
status: PASS
checks passed: 7
```

### Unit suite

```text
27 tests run
27 passed
```

Coverage includes:

- existing Gameplay Engine behavior;
- schema round-trip and compatible additive fields;
- unknown major schema fail-closed/quarantine;
- append-only receive/source-order capture;
- corrupted-middle and truncated-tail behavior;
- immutable manifest creation and digest verification;
- optional Parquet exporter dependency and backend path;
- Bbo vendor-text and structured-JSON CS parsing;
- source sequence gaps, out-of-order records and boot-domain changes;
- invalid Gameplay transitions quarantined without score mutation;
- duplicate event IDs not double-scoring.

### Existing Gameplay simulator

```text
exit code: 0
```

The Architecture/Product Gameplay authority remained unchanged.

### Deterministic replay

Fixture:

```text
experiments/evidence_replay_example
```

Result:

```text
authoritative digest run 1:
6946a0fba18123e7f5002b38048a53b59c43793cb311b9510166e0bc2d337b2b

authoritative digest run 2:
6946a0fba18123e7f5002b38048a53b59c43793cb311b9510166e0bc2d337b2b

deterministic: true
quarantine count: 0
accepted records: 6
gameplay inputs: 5
```

The fixture deliberately includes the same `stroke.confirmed` record twice. The authoritative state contains one stroke and one score mutation.

### Phase-0 fixture capture

The verifier ran the real capture CLI against the checked-in Bbo vendor-text fixture and produced:

```text
manifest.json
manifest.json.sha256
raw_serial.log
ranges.jsonl
capture_summary.json
```

Result:

```text
captured records: 2
parse errors: 0
hardware_validated: false
```

This verifies the collection path, not physical Channel Sounding accuracy, update rate, power or multi-ball behavior.

### Import and optional export checks

All canonical modules imported successfully:

- `putttrack.contracts`
- `putttrack.recording`
- `putttrack.evidence`
- `putttrack.cs`
- `putttrack.gameplay`

`pyarrow` was not installed in the verifier environment. The Parquet exporter dependency failure is explicit, and its grouped-write path is executed through a controlled fake-backend unit test. A real binary Parquet export requires:

```bash
pip install '.[research]'
```

## Acceptance

**PASS.** The repository is software Evidence-ready:

- typed canonical records exist in code;
- JSONL is append-only and replayable;
- run manifests are immutable and digest-checked;
- incompatible schemas fail closed;
- duplicate/late/out-of-order/reboot conditions are explicit;
- semantic evidence adapts to the unchanged Gameplay Engine;
- deterministic replay produces an identical authoritative digest;
- Phase-0 CS capture tooling is ready for real Bbo/Nordic hardware.

Issue #1 remains hardware-dependent and is not claimed complete by this evidence.
