# Tag multi-device identity and capture continuity

## Decision

Every capture is bound to the Tag's full opaque `DEVICE_ID`. A BLE advertising
name or controller address may select a device, but neither is the identity
authority.

This matters before the second Tag is powered. Legacy `0.1.13` used the same
`PuttTrack-Tag-v0.1` advertising name on every board, and a BLE controller
address may be private or represented differently by the host. Confirmed
`0.1.16` adds a per-device scan-response name, while full identity locking
remains required.

The currently commissioned physical Tag reports:

```text
DEVICE_ID=f383571202836e6f
firmware=0.1.16 (confirmed)
```

`DEVICE_ID` is an opaque inventory key, not a secret and not an authorization
credential. Player assignment remains server/Edge state rather than firmware
identity.

## Host capture contract

Both capture paths now accept `--expected-device-id`. Capture starts only when
the first encrypted status record exactly matches that value. The session then
fails closed if it observes:

- a different device ID, boot ID or firmware version at the end;
- a reboot/uptime or sequence regression;
- a duplicate, missing or out-of-order motion record;
- a non-increasing source timestamp;
- an invalid sensor flag, sensor error bit or malformed notification;
- a new sensor, notification-drop, advertising or power-management error.

Clipping deltas are preserved but do not by themselves fail transport
integrity, because a controlled impact may legitimately reach a sensor rail.
Such an episode is unsuitable for amplitude calibration.

The JSONL ends with a `tag_capture_result` record. Offline single-capture and
dataset analyzers reject an explicit failed result, so a failed field capture
cannot later be promoted merely because its motion records look plausible.

For the current Tag, the safest frozen capture pins both the adapter's
BLE address and the full device identity:

```bash
python tools/capture_tag_smp.py \
  --mode frozen \
  --ble-address AA:BB:CC:DD:EE:FF \
  --address-type random \
  --expected-device-id f383571202836e6f \
  --label stationary \
  --output runs/stationary-001.jsonl
```

Use the address type reported by the BLE scan. When the address is not yet
known, keep every other same-name Tag powered off and use:

```bash
python tools/capture_tag_smp.py \
  --mode frozen \
  --device-name PuttTrack-Tag-v0.1 \
  --expected-device-id f383571202836e6f \
  --label stationary \
  --output runs/stationary-001.jsonl
```

The device-ID check prevents silent mislabelling even in that fallback. With
multiple powered boards, repeated non-unique name-based SMP requests should not
be used.

## Per-device firmware name

Repository candidate `0.1.14` adds a per-device scan-response name:

```text
PuttTrack-<first four DEVICE_ID bytes>
```

For the commissioned Tag this is `PuttTrack-f3835712`. The suffix makes
ordinary scanning and service selection less ambiguous; the full encrypted
`DEVICE_ID` remains authoritative. This behavior is now present in confirmed
physical `0.1.16`.

Both default and optional-NFC `0.1.14+0` variants were built with NCS v3.4.0
and verified with the lab Ed25519 key on 2026-09-03:

| Variant | App RRAM | App RAM | signed BIN SHA-256 |
|---|---:|---:|---|
| default | 182,520 / 696,176 B | 207,272 / 262,144 B | `fb89e5f7f93787cd86b49af7610c67eec0bf5cdbbdb9ff9ee5c7e4541b857b3a` |
| NFC service | 189,204 / 696,176 B | 210,340 / 262,144 B | `a64f643fa256147c185cb023de1e209c3160d83109bd93747d116a6a1f49bd45` |

These are build artifacts, not physical validation or authorization to install
them. A future ordinary update can still use signed BLE OTA; DAPLink is needed
only for first commissioning or recovery.

Candidate `0.1.15` retains the identical per-device name and capture contract.
It supersedes the build-only binaries because the optional NFC variant adds a
bounded service window; it does not add new physical multi-Tag evidence. The
latest hashes and memory figures are recorded in
[`NRF54L15_TAG_OTA_BASELINE.md`](NRF54L15_TAG_OTA_BASELINE.md).

## Second Tag commissioning

Leave the second Tag unopened until a second physical unit advances a concrete
test. When it is commissioned:

1. power only that Tag during initial discovery;
2. read and record its full `DEVICE_ID` before collecting data;
3. give it a separate Ball inventory record;
4. use `--expected-device-id` on every labelled capture;
5. preserve the first Tag and confirmed `0.1.16` as the known-good baseline.

The current encrypted BLE pairing uses the lab service posture and does not
provide authenticated MITM protection. Identity locking prevents accidental
cross-device capture; it is not a defence against an active impersonator.
