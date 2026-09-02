# No-CS one-hole software soak

**Status:** PASS — deterministic software/fault-injection gate only

**Run date:** 2026-09-03

## Command

```bash
PYTHONPATH=src python tools/soak_no_cs_hole.py \
  --rounds 1000 \
  --players 4 \
  --seed 54015
```

## Result

```text
rounds completed:             1,000 / 1,000
simulated player-hole runs:   4,000
authoritative events/round:   12
accepted physical decisions:  8,000
pending physical decisions:   8,000
rejected physical decisions: 12,000
injected faults:              20,000
failures:                          0
digest: 556fa299d6218b8d6e46e4fc62080eb783cb68354638af21285d388e9bef8036
```

Every simulated player completed exactly one one-stroke hole for 100 points.
Each round used a seeded shuffled player order. The expected authoritative
event count remained exactly three per player: `tee.presented`, an independently
confirmed stroke and `cup.confirmed`.

## Faults injected

Each player path includes one of each:

- foreign Ball at the tee;
- different event reusing the tee node's last source sequence;
- cup occupancy without a preceding entry;
- cup entry attributed to the wrong Ball;
- exact retransmission of the accepted cup-presence event ID.

The run asserts immediately that these inputs cannot arm the wrong player,
complete a hole early, add a stroke, add points, create an extra authoritative
Gameplay event or change the post-completion snapshot.

## Reproducibility

`src/putttrack/venue/soak.py` contains the scenario generator and invariants.
The same seed produces the same player order and authoritative digest. Unit
tests run a smaller version on every repository verification pass.

## Boundary

This result validates deterministic software authority, idempotency and the
selected fault cases. It does **not** count as the physical 1,000-round gate in
ADR-009. It does not exercise switch bounce waveforms, optical/mechanical false
triggers, RF Ball correlation, packet loss over a real transport, outdoor
latency, power loss, weather, wiring or human play. Those tests start only after
the tee and two-stage cup mechanisms exist.
