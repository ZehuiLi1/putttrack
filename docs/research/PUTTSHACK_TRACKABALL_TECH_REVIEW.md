# Puttshack Trackaball technical review and PuttTrack decisions

**Status:** primary-source review complete; reusable observation layer
implemented; live RF power changes blocked by FTO and measurement gates

**Effective:** 2026-09-03

## What is publicly confirmed

Puttshack's current public product description confirms that each ball is
linked to a player profile and records strokes, hazards and bonus points. A
2025 Nordic customer report confirms that the upgraded Trackaball uses an
nRF54L15, an nPM2100 PMIC, integrated movement/acceleration sensing and
Bluetooth LE. It describes Ball states including moving, picked up, downhill,
slowing, stationary and feature/hole/gate, and reports a company estimate of
more than 7.5 years from a CR2447 primary cell.

Primary sources:

- [Puttshack game and Trackaball description](https://www.puttshack.com/the-game/)
- [Nordic: nRF54L15/nPM2100 Trackaball customer case](https://www.nordicsemi.com/Nordic-news/2025/08/Puttshack-Trackaball-uses-Nordic-nRF54L15-SoC-and-nPM2100-PMIC)
- [Nordic nRF54L15 product specification](https://docs.nordicsemi.com/r/bundle/ps_nrf54l15/page/keyfeatures_html5.html)

The Nordic report does **not** disclose the current packet format, number or
placement of receivers, sensor part numbers, actual transmit powers, security
protocol or exact state classifier. Those remain unknown.

## What the licensed World Golf Systems patent family describes

Puttshack publicly identifies World Golf Systems patents as exclusively
licensed technology. The WGS patent family provides a much more specific
architecture, but a patent embodiment is not proof that every detail remains
in the current nRF54L15 product.

The currently granted US family member describes:

- Bluetooth communication beacons distributed around the facility, each with
  its own identity;
- a tee-adjacent beacon detecting the presence and code of a Ball;
- a Ball storing movement data locally and transferring it intermittently;
- low-power Ball transmission when not in play or close to the tee, then
  higher-power transmission after leaving the tee;
- normally passive beacons that answer only when required and at the lowest
  useful power;
- RSSI-based proximity plus optional triangulation/trilateration from more than
  one beacon;
- server-directed retransmission with different delays after message clashes,
  with frequency hopping also proposed;
- optical Ball detection at each hole;
- central Ball-code/player-code association;
- activation at issue, deactivation at return, battery/charge-cycle and fault
  tracking, plus optional video replay.

Relevant primary sources:

- [US20230338814A1 / US12611585B2, Ball game apparatus](https://patents.google.com/patent/US20230338814A1/en)
- [US9808677B2, movement signatures and facility integration](https://patents.google.com/patent/US9808677B2/en)
- [US12551756B2, coded magnetic tee communication](https://patentsgazette.uspto.gov/week07/OG/html/1543-3/US12551756-20260217.html)
- [Puttshack patent notice](https://cloudarena-wwp.puttshack.com/patents/)

The first patent's granted claims expressly include Ball transmit power varying
with movement and detector transmit power varying with proximity. The magnetic
tee patent claims a coded changing magnetic field that identifies a particular
tee and moves the Ball from low- to high-power state. This is an explicit FTO
boundary, not merely a vague similarity. This document is an engineering
review, not a legal opinion; production use needs a claims/jurisdiction review.

## Direct answers for PuttTrack

### Is it multiple BLE receivers?

The WGS disclosure says yes: multiple distributed Bluetooth beacons may hear a
Ball and forward data to a central server. More than one beacon can refine
proximity. We cannot claim that the current 2025 nRF54L15 generation uses the
identical topology, but it is a well-supported Trackaball architecture rather
than speculation.

PuttTrack should adopt the useful generic pattern:

```text
Ball connectionless event packet
        |       |       |
      RX-A    RX-B    RX-C
        \       |       /
         receiver observations
                 |
        deduplicate one Ball packet
                 |
      identity + freshness + diversity
                 |
       non-authoritative RF evidence
```

Multiple receivers improve delivery diversity and provide useful RSSI/path-loss
research. They do not turn RSSI into centimetre-level position authority. Ball
rotation, body blocking, antenna pattern, battery/enclosure detuning and changed
TX power all bias RSSI. Any packet used for path-loss comparison must carry the
actual TX power.

The repository now defines `RadioReceptionObservation` and
`aggregate_radio_receptions()`. Receiver identity/order is separate from Ball
device/boot/radio sequence. Unknown devices/receivers, mixed packets, wrong
Ball mappings, repeated receiver reports and late aggregation fail closed.
Meeting a two-receiver quorum still grants neither position nor Gameplay
authority.

The check-in inventory now also supports a one-to-one optional
`DEVICE_ID -> BALL_ID` mapping and resolves it only inside the current session's
assignment. Duplicate Ball IDs or physical device IDs are rejected instead of
being silently overwritten.

### Should TX power change with state?

Technically, yes: nRF54L15 supports configurable TX power in 1 dB steps from
-10 dBm to the package maximum, and Zephyr/NCS includes controller APIs and an
HCI power-control sample. Lower power can save energy and reduce cross-hole RF
contention; higher power can improve active-play coverage.

The repository's research-only proposal is:

| State | TX proposal | Advertising | Event copies/window | Gate |
|---|---:|---:|---:|---|
| `SHIPPING` | radio off | off | 0 | explicit service/assignment wake |
| `IDLE` | -10 dBm | 2.0–2.5 s | 1 | motion sentinel armed |
| `TEE_NEAR` | -10 dBm | 100–150 ms | 2 / 80 ms | independent near-tee confirmation |
| `ACTIVE` | 0 dBm | 100–150 ms | 3 / 120 ms | measured motion |
| `SERVICE` | 0 dBm | 100–150 ms | 1 | commissioning/diagnostics/OTA |

These values are bounded hypotheses, not firmware defaults. `0 dBm` is used as
the first active-test ceiling rather than immediately choosing the nRF54L15
maximum. The current physical Tag runs confirmed `0.1.17`; it still does not
implement dynamic TX power.

Before enabling this policy on hardware:

1. complete FTO review of the movement/proximity power claims;
2. confirm controller support in the pinned NCS build and export actual applied
   TX power/error counters in status;
3. test reconnect, idle OTA and wake coverage at every proposed power;
4. measure current and packet-delivery rate in the real shell/battery geometry;
5. calibrate every receiver and keep TX power in every observation;
6. run adjacent-hole interference and many-Ball collision tests.

## Useful Trackaball lessons already present in PuttTrack

- immutable device identity separated from human Ball label and player
  assignment;
- local raw history followed by intermittent BLE retrieval;
- motion states kept separate from the authoritative Gameplay Engine;
- motion wake plus active/idle radio intervals;
- physical tee/cup/feature evidence instead of trusting motion alone;
- local Edge authority and deterministic audit;
- signed OTA with rollback and recovery.

## Important gaps the comparison exposed

1. **Multi-receiver packet provenance — now implemented.** The old PuttTrack
   contracts did not distinguish the Ball emission from each receiver's own
   boot/sequence/time domain.
2. **Actual TX-power metadata — contract implemented.** RSSI without transmitted
   power cannot be compared across radio states.
3. **Connectionless event packet — pending.** Current Tag motion transport is a
   connected GATT/SMP path. Several passive receivers cannot simultaneously
   consume the same live event through that path.
4. **Collision/airtime control — pending measurement.** Add deterministic
   event IDs, jittered repetitions and Edge deduplication. A decentralized,
   packet-keyed deterministic repetition scheduler is now implemented for
   simulation; do not copy the patented server-assigned resend mechanism
   without FTO review.
5. **Explicit lifecycle states — partly present.** `auto/research/idle` exists,
   but production still needs `SHIPPING`, `ASSIGNED`, `PLAY`, `SERVICE` and
   `QUARANTINED` ownership semantics.
6. **Near-tee context — physical gate.** A receiver's strong RSSI alone is not
   enough. Test a deliberately local tee mechanism such as a shielded/near-field
   reader, NFC/service touch or another independently justified sensor. The WGS
   coded magnetic-coil mechanism is patent-sensitive.
7. **Battery observability — hardware gap.** The Tag board has no documented
   divider/fuel gauge. A custom Ball should evaluate a PMIC/fuel-gauge path and
   a larger primary cell only after mass, balance and impact constraints are
   known. Puttshack's CR2447/nPM2100 result is a useful benchmark, not a direct
   lifetime prediction for PuttTrack.
8. **Fleet maintenance — pending.** Add assignment eligibility, firmware/
   capability compatibility, service history, fault/quarantine and battery
   replacement records before pilot scale.

## Recommended architecture decision

Use BLE in two complementary ways:

- **connectionless, small event/health beacons** for redundant reception by
  several Gateways and coarse receiver-domain evidence;
- **encrypted connection-oriented BLE** for commissioning, configuration,
  detailed history, diagnostics and signed OTA.

Do not stream 50 Hz raw IMU to every receiver. The Ball buffers raw windows and
emits a compact sequence-stamped state/event hint; Edge requests the detailed
window only when needed. Do not let the Ball or RSSI directly confirm score.
Tee/cup/feature hardware and game context retain the authority gates.

## Experiment ladder after the printed core

1. One Ball, one receiver: measure delivery and current for `-10`, `-4`, `0`
   dBm in stationary/active shell orientations.
2. One Ball, three receivers: record receiver ID, boot/sequence, channel, RSSI,
   TX power and packet digest; verify Edge deduplication.
3. Rotate the stationary Ball through controlled orientations to quantify
   antenna-pattern RSSI spread before interpreting distance.
4. Two Balls, then a realistic active-Ball count: measure collisions, missed
   events, retransmission cost and adjacent-hole leakage.
5. Add a physically local tee cue and prove it rejects a nearby non-tee Ball.
6. Only then decide whether receiver diversity is merely reliable transport,
   coarse zone evidence, or good enough for any bounded proximity feature.

Channel Sounding remains deferred. This BLE receiver experiment is cheaper and
directly useful for message delivery, but it must not silently recreate a
continuous-position promise using uncalibrated RSSI.
