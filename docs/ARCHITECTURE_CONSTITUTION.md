# PuttTrack Architecture Constitution

**Status:** Architecture convergence candidate v1  
**Applies to:** Research rig, one-hole pilot, 18-hole venue architecture and production evolution  
**Product-behaviour authority:** [`PRODUCT_LOGIC_LOCK.md`](PRODUCT_LOGIC_LOCK.md)

> **Current execution note (2026-09-02):**
> [ADR-013](adr/ADR-013-defer-cs-for-ble-motion-mvp.md) defers Channel
> Sounding, Anchors and continuous localisation for the active BLE + motion +
> physical-sensor MVP. The CS architecture below is retained as a conditional
> future system hypothesis, not the present implementation dependency order.
> See [`CURRENT_PLAN_NO_CS.md`](CURRENT_PLAN_NO_CS.md).

This document is the technical source of truth for PuttTrack after the player journey and gameplay authority were locked. It replaces the current draft architecture as the preferred system direction while preserving empirical gates for decisions that cannot yet be proven.

It is not a freedom-to-operate opinion. Patent-sensitive movement-signature work remains isolated from production authority until a claims-based legal review is completed.

---

## 1. Product promise and architecture rule

PuttTrack must make the technology disappear:

```text
Guest / Booking
  -> quick check-in
  -> assigned smart ball
  -> walk to hole
  -> DETECTED / CHECKING
  -> READY
  -> normal physical mini-golf play
  -> automatic stroke / feature / cup evidence
  -> deterministic score
  -> next player / next hole
  -> local leaderboard and final digital result
```

The system architecture must therefore optimise, in order:

1. scoring integrity;
2. effortless player flow;
3. graceful recovery;
4. predictable multi-ball operation;
5. outdoor maintainability;
6. battery life and installation cost;
7. research value without contaminating production authority.

A component is not justified merely because it is technically interesting.

---

## 2. Final system shape

```text
                                 CLOUD PLANE
 bookings / optional accounts / loyalty / fleet analytics / release control
                                      ^
                                      | queued, idempotent sync
                                      |
+-----------------------------------------------------------------------+
|                         VENUE AUTHORITY PLANE                         |
|                                                                       |
|  Managed Ethernet / PoE LAN                    Local Edge Server       |
|       |                                         (authoritative)        |
|       +---- Zone Gateway Z1 ----+               device registry       |
|       +---- Zone Gateway Z2 ----+---- events -> session manager       |
|       +---- ...                 |               localisation/tracking |
|       +---- Hole displays       |               evidence fusion       |
|       +---- check-in/admin      |               gameplay + scoring    |
|                                 |               local event store     |
+---------------------------------+-------------------------------------+
                                  |
                         24 V + protected RS-485
                      (two isolated branches / zone)
                                  |
          +-----------------------+-----------------------+
          |                       |                       |
       Anchor(s)             Tee/Cup/Feature          Anchor(s)
       Hole N                 sensor nodes             Hole N+1
          \                                               /
           \--------- Bluetooth Channel Sounding --------/
                                   |
                              SMART BALL
                        nRF54L15 + motion sensing
                        CS Reflector + BLE control
```

### Architecture allocation

| Layer | Authority |
|---|---|
| Smart Ball | Physical device identity, radio participation, raw/derived motion and health |
| Anchor / RF cell | Per-link ranging observations and local RF diagnostics |
| Zone Gateway | CS scheduling, field-bus coordination, source timestamps, local buffering, sensor I/O and device health |
| Venue Edge | Device/session authority, localisation, evidence fusion, gameplay, scoring, audit, HMI state and offline operation |
| Cloud | Booking/account integrations, optional history/rewards, fleet analytics, release control and remote support |

The ball never owns player identity, hole rules, final XY, score or game outcome.

---

## 3. Canonical technology decisions

### 3.1 Keep

- **nRF54L15** as the research and first custom-ball radio/MCU candidate.
- **Nordic nRF54L15 Tag** as the moving research reference.
- **Ball = Channel Sounding Reflector; fixed infrastructure = Initiator.**
- **Bluetooth Channel Sounding** as the conditional primary research/pilot ranging technology.
- **Generic, hole-independent motion states** on or near the ball.
- **Camera ground truth** for research, calibration and replay; not required for production positioning.
- **Physical cup sensor** and independent tee-presence sensing for the first production system.
- **Deterministic Gameplay Engine** behind a semantic evidence boundary.
- **Local venue authority** with WAN-independent scoring.

### 3.2 Change

- Production Anchor baseline becomes **four geometry anchors per RF cell**, not an assumed permanent five.
- The fifth research node becomes an **optional elevated/reference/recovery anchor**, selected by RF evidence rather than placed blindly at geometric centre.
- Dynamic tracking changes from “assemble simultaneous ranges -> multilateration -> EKF” to an **asynchronous range-domain EKF** that consumes each timestamped range when it arrives. Robust multilateration remains for initialization, diagnostics and reacquisition.
- Gateway topology changes from an undefined per-hole possibility to a **Zone Gateway managing approximately 2–3 neighbouring holes**, subject to site survey and RF-cell tests.
- Field-node backhaul becomes **wired 24 V + protected/isolated RS-485**; Ethernet/PoE is used between Zone Gateways, displays, operator stations and Edge.
- Production Edge is a **modular monolith with explicit modules and one local event authority**, not an early microservice estate.

### 3.3 Defer

- Whether the final ball retains both a wake accelerometer and a six-axis IMU.
- Production dual antenna on the ball and any dual antenna on fixed anchors.
- IMM tracking, learned range-bias/covariance models and connectionless CS.
- Rechargeable ball, wireless charging and charging racks.
- Exact production Anchor SoC/vendor, gateway MCU and database engine beyond the stage guidance in this constitution.
- Shared anchors between holes until geometry, scheduling and fault-domain evidence exists.

### 3.4 Reject for Production V1

- Hole-specific movement signatures as authoritative valid-stroke logic.
- End-to-end opaque AI that directly outputs score or authoritative XY.
- Camera-only scoring or camera-required runtime localisation.
- Wireless Anchor backhaul competing in the 2.4 GHz band.
- Cloud-authoritative live scoring.
- A Linux SBC at every hole.
- Always-on full-rate ranging for every ball against every Anchor.
- Hidden score edits or non-audited operator correction.

---

## 4. Smart Ball constitution

### 4.1 Research hardware

Use the Nordic nRF54L15 Tag as the golden reference because it provides:

- nRF54L15 with official Bluetooth Channel Sounding support;
- two switched 2.4 GHz antennas;
- ADXL367 low-power motion wake;
- BMI270 accelerometer/gyroscope;
- CR2032 supply and accessible debug/current-measurement points.

The development board is not an impact-rated or balanced production golf-ball core.

### 4.2 Custom EVT candidate

```text
nRF54L15
+ nPM2100 primary-cell PMIC candidate
+ CR2447 candidate
+ high-reliability motion sensing
+ six-axis IMU during EVT
+ two antenna paths during EVT
+ secure boot / signed DFU
+ pogo production test pads
+ welded-tab battery connection
+ mechanically symmetric rigid core
```

The Puttshack public case study confirms that nRF54L15 + nPM2100 + CR2447 is technically plausible, but its reported battery life is that company's estimate and is not a PuttTrack design claim.

### 4.3 Mechanical requirements

- Target traditional golf-ball diameter: at least 42.67 mm; target mass no greater than 45.93 g where practical, even though venue balls need not be tournament-conforming.
- Centre of mass must remain close enough to geometric centre that roll bias is not operationally perceptible.
- Do not use a spring coin-cell holder in the final core.
- Battery, PCB and counter-mass must be constrained against impact and vibration.
- Potting/encapsulation material must be selected through RF-detuning, thermal, impact and service-life tests.
- Antennas require clearance from battery metal, ground planes, potting and shell pigments.
- Record per-ball RF, IMU bias, mass, balance and power calibration at production test.

### 4.4 Ball firmware state machine

```text
MANUFACTURED
  -> SHIPPING
  -> STORAGE
  -> IDLE_UNASSIGNED
  -> ASSIGNED
  -> PRESENTED
  -> ARMED
  -> IMPACT
  -> ACTIVE_ROLLING
  -> SETTLING
  -> STATIONARY
  -> PRESENTED / ARMED on next action

Any operational state may enter:
  PICKED_UP / CARRIED
  LOW_BATTERY
  FAULT
  SERVICE_DFU
  QUARANTINED
```

- `SHIPPING/STORAGE`: minimum power, explicit authenticated wake/service action.
- `IDLE/ASSIGNED`: advertisement and health at low duty cycle.
- `PRESENTED/ARMED`: local RF cell selected; secure connected-CS links prepared.
- `IMPACT/ACTIVE_ROLLING`: high-rate motion capture and event-driven ranging.
- `SETTLING/STATIONARY`: final position confirmation, then rate reduction.
- `PICKED_UP/CARRIED`: notify evidence layer; do not directly add a stroke.
- `LOW_BATTERY`: finish current round if safe, prevent new assignment below service threshold.
- `SERVICE_DFU`: not entered during an active player action.

### 4.5 No-CS multi-receiver BLE boundary

During the active no-CS milestone, a compact connectionless Ball event/health
packet may be observed by several registered receivers. Each receiver records
its own identity, boot, sequence and receive time plus the Ball device, boot,
radio sequence, packet digest, RSSI and actual TX power. Edge may use the
result for redundant delivery and bounded RF research only.

Receiver count or RSSI does not grant position, tee, stroke, feature, cup or
score authority. Connected encrypted BLE remains the channel for detailed
history, configuration, diagnostics and signed OTA. State-based TX power is a
research candidate gated by FTO, shell RF/current, coverage, coexistence and
many-Ball tests. See ADR-014.

### 4.5 Ball data boundary

The ball may hold a bounded transport/event FIFO for resilience. It must not be the long-term game-history database and must not store per-hole score rules or player personal data.

---

## 5. Anchor and RF-cell constitution

### 5.1 Research rig

Use five identical Bbo nRF54L15 boards plus one spare:

- A/B/C/D: perimeter geometry;
- E: experimental reference/elevated/recovery node;
- same board revision and firmware across all nodes;
- Nordic official CS samples are the bring-up baseline.

Bbo is a research convenience, not the production Anchor design.

### 5.2 Production RF cell

Default starting hypothesis per ordinary hole:

```text
A ---------------- B
|                  |
|     playable     |
|       area       |
|                  |
D ---------------- C

Optional R: elevated/reference position with good LOS
```

- Four fixed Anchors are the production geometry baseline.
- Add R only if it reduces P95/tail error or no-fix rate materially.
- A centre node on the ground is not automatically useful and may be vulnerable to obstruction.
- One high-quality fixed antenna is the production Anchor baseline; add antenna diversity only if measured benefit justifies cost.
- Anchor height/orientation is a site-calibration parameter. An elevated line-of-sight reference can be more useful than geometric centre.
- Shared Anchors between holes are permitted only after a site-specific geometry/scheduling/fault-domain analysis.

### 5.3 Production Anchor hardware

- Bluetooth CS-capable radio/MCU, initially nRF54L15 or a pre-certified module using it.
- Validated RF layout, stable clocks and production FAE/range calibration.
- 24 V input with protected conversion to local rails.
- Isolated or appropriately protected RS-485 interface.
- Hardware watchdog, brownout protection, signed boot/DFU and recovery image.
- Local ring buffer for observations during short gateway outages.
- Device identity, firmware/version reporting and replaceable field enclosure.
- IP65/67 enclosure with controlled RF window, drainage/condensation strategy and surge protection.

### 5.4 Ranging ownership

The Anchor produces timestamped observations, not game points:

```text
PBR/IFFT distance
phase-slope/phase-derived distance where available
RTT distance / security cross-check
RSSI
antenna path
quality / channel map / estimator diagnostics
connection/procedure identifiers
```

---

## 6. Channel Sounding operating model

Bluetooth Core 6.0 Channel Sounding is 1:1 and is initiated over an encrypted ACL connection. PBR and RTT may be combined. The application is responsible for converting controller measurements into distance. Multi-antenna paths can reduce multipath sensitivity.

### 6.1 Production V1 policy

- Standard encrypted, connected Bluetooth CS only.
- **One active CS procedure per ball at a time.** Do not depend on concurrent procedures across multiple links.
- Permit several pre-established links only after controller/stack tests prove stability and power impact.
- One active player per ordinary hole means one ball gets high-rate positioning in that RF cell.
- Unplayed balls remain discoverable/healthy at low duty cycle rather than being continuously ranged.

### 6.2 Adaptive schedule

Recommended initial schedule, to be measured rather than assumed:

| Ball state | CS policy |
|---|---|
| Unassigned / elsewhere | advertisements and coarse zone discovery only |
| Assigned, stationary outside tee | very low-rate health/coarse range |
| Presented / READY | establish local links and validate identity/zone |
| Impact / rolling | high-rate cycle over best 3 Anchors |
| Rolling with weak geometry | add fourth and optional reference observation |
| Settling | confirm final position with 4 or best-4-of-5 |
| Stationary | reduce to low rate after confidence hold |

Best-N scheduling is preferred to blindly ranging all five nodes every cycle.

### 6.3 Scalability boundary

The venue is partitioned into RF cells. Eighty balls physically present do not imply eighty actively ranged balls:

- ordinary hole: at most one active ball;
- 18 holes: nominally at most 18 high-rate balls;
- inactive group balls remain low-rate;
- neighbouring cells use planned channel maps/timing and 2.4 GHz coexistence policy;
- Zone Gateways coordinate local cells, while Edge has venue-wide visibility.

Connectionless CS over PAwR is a Research V2 path. A 2026 nRF54L15 proof of concept reports large switching/energy improvements, but it is not the Production V1 dependency.

---

## 7. Zone Gateway constitution

### Decision

Use **one Zone Gateway per approximately 2–3 holes** as the production baseline. One gateway per hole is acceptable for the one-hole pilot but not the default full-venue architecture. No-gateway direct Anchor-to-Edge wiring creates excessive cabling and pushes field timing/sensor responsibility into the server.

### Responsibilities

- schedule CS procedures and choose best-N Anchors;
- own ball/Anchor connection lifecycle in its RF cells;
- distribute monotonic time/offset synchronisation to field nodes;
- collect Anchor range observations and physical sensor events;
- apply sequence numbers and source timestamps;
- buffer during short Edge/LAN interruptions;
- monitor Anchor, cup, tee and feature sensor health;
- relay staged signed updates and support rollback/recovery;
- forward data through Ethernet to Edge;
- never own final score authority.

### Hardware direction

- Production: industrial MCU-class gateway with Ethernet MAC, secure boot, hardware watchdog, two isolated/protected RS-485 buses and optional CAN.
- Pilot: ESP32-S3 Ethernet or another available Ethernet MCU is acceptable if watchdog, recovery, wired I/O and deterministic scheduling gates pass.
- Do not deploy a Linux SBC per hole.

---

## 8. Physical venue network

### Baseline 18-hole topology

```text
                       Internet / Cloud
                              |
                        Firewall/Router
                              |
                  Managed core PoE switch + UPS
                  /       |        |        \
          Edge Server   HMI LAN   Zone GWs   Cameras (optional)
                                  Z1...Z6
                                    |
                           local 24 V fused supply
                            + two RS-485 buses
                                    |
                      Anchors + Tee/Cup/Feature nodes
```

- Six Zone Gateways is a planning starting point for 18 holes at 3 holes/zone, not a fixed count.
- Hole displays/check-in/operator stations use wired Ethernet/PoE where practical.
- Anchors and simple sensors use 24 V SELV distribution with protected RS-485.
- Use managed switches, VLANs, surge protection, labelled service loops, accessible junctions and spare ports.
- Outdoor copper requires earthing/bonding and surge/lightning engineering appropriate to the site. Fibre is reserved for electrically separated buildings, long exposed trunks or surge-domain isolation.
- Edge, core switches and critical gateways are UPS-backed; player safety systems remain independent of game software.

---

## 9. Venue Edge constitution

### Architecture style

Start with a **modular monolith** deployed as a small number of supervised processes, not twenty microservices.

Logical modules:

```text
Device Registry
Gateway/Measurement Ingestion
Session & Ball Assignment
Course Configuration
Calibration Registry
Localisation & Tracking
Motion State Ingestion
Evidence Fusion
Gameplay Engine
Score/Event Audit
Presentation Hub
Operator Console
Health/Fault Manager
Evidence/Replay
Update Manager
Cloud Sync
```

Recommended process boundary for pilot:

1. `putttrack-core`: registry, sessions, localisation, evidence, gameplay and persistence;
2. `putttrack-io`: gateway/device adapters and scheduling control;
3. `putttrack-web`: player/operator presentation and WebSocket/SSE;
4. database and optional raw-data recorder.

Modules share versioned contracts and one authoritative local state model. Split into additional services only when independent scaling or fault isolation is proven necessary.

### Persistence

- Research/one-hole: SQLite/WAL is acceptable.
- 18-hole pilot/production: PostgreSQL is the preferred authoritative operational database.
- Gameplay/evidence mutations are append-only events with materialized current state.
- Raw high-volume CS/IMU/camera research data is stored in Parquet/object files with metadata references, not in the gameplay tables.
- Edge restart recovers from committed events and device snapshots.

### Offline rule

WAN loss cannot interrupt ball recognition, positioning, gameplay, scoring, HMI or operator recovery. Cloud sync resumes through an idempotent outbound queue.

---

## 10. Localisation and tracking constitution

### 10.1 Observation model

Each Anchor range is an asynchronous measurement:

```text
z_i(t) = sqrt((x(t)-a_ix)^2 + (y(t)-a_iy)^2 + dz_i^2) + bias_i + noise_i
```

The system must retain the source timestamp, Anchor position/height, estimator type, antenna path and confidence inputs.

### 10.2 Primary pipeline

```text
raw per-link observation
 -> schema/sanity validation
 -> per-device/per-antenna calibration
 -> quality and outlier probability
 -> asynchronous range-domain EKF update
 -> course-boundary plausibility
 -> track/confidence output
```

Robust weighted multilateration is still required for:

- initial fix;
- operator diagnostics;
- static benchmark;
- tracker reacquisition after long outage;
- 3/4/5-Anchor ablation.

This avoids pretending sequential CS measurements are simultaneous and lets the tracker use each observation at its true acquisition time.

### 10.3 IMU role

Generic motion states adjust process noise and schedule:

- stationary -> low process noise and low ranging rate;
- impact -> high process noise / immediate tracking burst;
- rolling -> rolling motion model;
- pickup/carry -> suspend course-constrained roll model;
- drop/bounce -> completion/supporting evidence.

Do not double-integrate unconstrained ball accelerometer data into authoritative position unless later research proves a calibrated orientation/gravity model.

### 10.4 ML boundary

ML may estimate:

- range bias correction;
- variance/covariance;
- outlier/NLOS probability;
- sensor-health anomaly.

ML must not directly mutate score or become the sole authoritative XY source in Production V1.

### 10.5 UWB trigger

Start a formal UWB benchmark if any of the following occurs after the full CS gate:

- representative dynamic P90 remains above 0.6 m or P95 above 1.0 m;
- NLOS tail errors cannot be detected/contained well enough for game features;
- connected-CS scheduling cannot sustain required multi-hole update rates;
- a product mechanic requires repeatable sub-20 cm geometry rather than independent physical feature sensors;
- ball energy/connection overhead is incompatible with service-life target.

UWB is not rejected; it is an evidence-triggered fallback/hybrid.

---

## 11. Evidence and gameplay authority

Canonical pipeline:

```text
RF / IMU / Tee / Cup / Feature sensor
 -> raw observation
 -> measurement processing
 -> confidence-aware evidence candidate
 -> fusion / confirmation policy
 -> semantic gameplay event
 -> deterministic Gameplay Engine
 -> authoritative score state
 -> presentation event
```

### First-production confirmation policies

- `tee.presented`: assigned ball identity + tee-presence sensor + local-cell confirmation.
- `stroke.confirmed`: generic impact evidence + subsequent valid spatial/motion change; no hole-specific movement signature.
- narrow scoring-critical `feature.confirmed`: physical beam/switch plus trajectory where available.
- broad hazard/route zones: geometry may be sufficient if position confidence and dwell/crossing rules pass.
- `cup.confirmed`: physical cup sensor plus spatial proximity and motion consistency; never a single low-confidence point.
- `operator.adjustment`: explicit authenticated audit event with reason.

Presentation cannot mutate score directly.

---

## 12. Time and ordering constitution

- Every device has an immutable identity, boot ID, monotonic timestamp and sequence number.
- Edge also attaches receive time and wall clock.
- Gateways distribute periodic sync/offset messages to field nodes.
- Edge and gateways use NTP; hardware PTP is preferred where supported by production Ethernet hardware but is not required for the lab.
- Dynamic tracking consumes measurements asynchronously, reducing the need for fake frame synchrony.
- Initial target: within-zone relative timestamp error <=2 ms; research camera alignment <=5 ms.
- Camera experiments use a gateway-controlled sync LED or hardware trigger visible in frames and recorded in the event log.
- Duplicate, late and out-of-order observations are retained for audit but only applied according to a bounded reorder/replay policy.

---

## 13. Player HMI constitution

- Check-in: booking QR/code, guest display name, optional account linking.
- Assignment: player name + human-readable ball colour/number/marker.
- Hole states: `AVAILABLE -> DETECTED/CHECKING -> READY -> PLAYING -> COMPLETE`.
- Use text, icon, light and short audio; never colour alone.
- Normal hole play is zero-touch.
- Bonus/hazard feedback target <=500 ms after confirmed evidence and cannot block the next legal transition.
- Wrong-ball and recognition-retry messages give specific self-recovery instructions.
- Outdoor displays/indicators must be sunlight-readable, IP-rated, thermally suitable for Brisbane, vandal-resistant and serviceable.
- If a screen fails, the hole can use ring/audio plus operator guidance; scoring state remains local and auditable.

---

## 14. Security and update constitution

- Opaque provisioned IDs for balls, Anchors and Gateways; do not treat BLE MAC address as score identity.
- Per-device credentials established in manufacturing/service provisioning.
- Encrypted/authenticated BLE control and CS setup.
- Signed firmware with MCUboot/secure boot, rollback protection where supported and version compatibility policy.
- Gateway/Edge communication authenticated; mTLS is preferred over Ethernet.
- RS-485 nodes use authenticated command/update envelopes and sequence/anti-replay fields.
- Operator/admin actions require roles and produce audit events.
- Updates are staged by zone, prohibited during active play, health-checked and automatically rolled back or quarantined on failure.
- Ball DFU occurs at a service/assignment station, not during a live hole.
- Lost/stolen devices can be revoked without changing player workflow.

---

## 15. Failure and degradation principles

- One Anchor lost: continue with three good geometry Anchors if confidence gate passes; alert operator.
- Two geometry Anchors lost: no authoritative XY; retain stroke/cup physical evidence, pause location-dependent scoring or route to review.
- CS confidence collapse: reduce feature authority, retry/reacquire; do not invent score.
- Cup sensor failure: hold completion for alternate independent evidence/operator review; mark hole degraded.
- Wrong ball: reject arming and provide human-readable owner/required-ball message.
- Ball low battery: finish current action where safe; block new assignment below service threshold.
- Gateway restart: restore schedule/device state from Edge and replay buffered records.
- Edge restart: recover committed game state from event log; no duplicate score mutations.
- WAN/cloud loss: venue continues normally; queue outbound sync.
- Display loss: game authority remains operational; use indicator/audio/operator fallback.
- Partial OTA/version mismatch: quarantine affected node; previous signed image remains bootable.

Detailed policies live in `docs/architecture/FAILURE_MODES.md`.

---

## 16. Development stages

| Stage | Hardware | Primary objective | Exit condition |
|---|---|---|---|
| Research rig | Nordic Tag + 5 Bbo Anchors + PC + camera | Establish CS, IMU and localisation evidence | Single-link, 3/4/5-Anchor and dynamic data gates pass |
| EVT | Custom ball core + custom Anchor prototype + pilot gateway | Prove mechanics, RF, power and interfaces | RF/power/impact and one-hole vertical slice pass |
| DVT | Production-like enclosures/network/HMI | Reliability, security, maintainability | Environmental, endurance, OTA and degraded-mode gates pass |
| Pilot venue | 3–6 holes then full 18 | Throughput and real operations | Scoring integrity, uptime and staff-recovery gates pass |
| Production | Qualified BOM and manufacturing test | Repeatable deployment | Release verification and FTO checkpoints complete |

---

## 17. Go/no-go summary

The detailed matrix is authoritative in `docs/architecture/VERIFICATION_MATRIX.md`. Headline gates:

- single-link LOS P90 <=0.5 m and stable 30-minute operation;
- representative static XY P90 <=0.5 m, P95 <=0.8 m;
- dynamic XY P90 <=0.6 m, P95 <=1.0 m, reacquisition <=1 s;
- ordinary confirmed-event presentation <=500 ms;
- stroke sensitivity >=99% with false-stroke rate <=0.1% of labelled non-stroke episodes;
- cup false positive: zero in at least 10,000 representative completion trials before removing operator guardrails;
- no duplicate/cross-ball score mutation;
- one-hole 1,000-round soak before multi-hole pilot;
- 80-ball simulation with bounded queues and no event loss; actual high-rate load is active-hole bounded;
- custom-ball battery life target >=2 years initially, >=5 years stretch, based on measured energy—not copied claims.

---

## 18. IP and research separation

Production authority is spatial-first and hole-independent:

```text
position/trajectory + generic motion + course geometry + physical truth
```

The production system must not use a hole-specific translational/rotational movement signature as the main valid-stroke authority without a later claims-based FTO review.

Research may compare rules, feature distance, DTW, HMM, tree and temporal models using PuttTrack's own labelled data. Research output cannot silently become production scoring logic.

Mandatory legal checkpoints:

1. before committing to final commercial smart-ball/venue architecture;
2. before adding hole-specific movement-signature authority;
3. before adopting rechargeable/inductive charging and detector/activator combinations resembling later public patent families;
4. before launch in each target jurisdiction;
5. at the 2032/2033 patent-landscape review horizon.

---

## 19. Keep / Change / Defer / Reject table

| Item | Decision | Rationale / gate |
|---|---|---|
| nRF54L15 | KEEP | Best integrated CS/BLE/power research candidate; recheck after EVT power/RF |
| Nordic Tag | KEEP (research) | Golden moving reference; not production core |
| Bbo | KEEP (research) | Fast Anchor bring-up; not production hardware |
| 5 Anchors | CHANGE | Five for experiments; four production baseline plus optional reference |
| Centre Anchor | CHANGE | RF-optimal elevated/reference, not mandatory geometric centre |
| Ball Reflector | KEEP | Pushes active/scheduling work to powered venue infrastructure |
| Anchor Initiator | KEEP | Matches connected-CS model and powered infrastructure |
| Bluetooth CS | KEEP, CONDITIONAL | Primary research/pilot; must pass accuracy and scalability gates |
| Dual antenna | DEFER | Keep on research Tag; production only if tail-error benefit is material |
| IMU | KEEP | Generic motion/evidence/scheduling; exact sensor set remains open |
| nPM2100 | KEEP AS EVT CANDIDATE | Strong primary-cell fit; measure actual duty cycle |
| CR2447 | KEEP AS EVT CANDIDATE | Plausible capacity/form; mechanical/RF/service life must be proved |
| Gateway | CHANGE | Zone gateway per ~2–3 holes; one-hole pilot may use one per hole |
| RS-485 | KEEP | Robust low-cost field bus; use isolation/protection and 24 V |
| PoE | KEEP | Gateways/displays/network endpoints; not necessarily every Anchor |
| Ethernet | KEEP | Authoritative wired venue backbone |
| Edge PC | KEEP | Local authority and research compute; modular monolith |
| Camera GT | KEEP | Research/calibration/replay only |
| Cup sensor | KEEP | First-production scoring-critical truth |
| Multilateration | KEEP, REPOSITION | Initialization/reacquisition/static benchmark |
| EKF | CHANGE | Primary asynchronous range-domain tracker |
| IMM | DEFER | Add only if motion-mode data proves measurable benefit |
| ML | DEFER/CONSTRAIN | Bias/variance/outlier models only after physics baseline |
| UWB | DEFER | Triggered benchmark/fallback if CS gates fail |
| PAwR/connectionless CS | DEFER (research) | Promising 2026 PoC, not Production V1 dependency |
| Cloud | KEEP, NON-AUTHORITATIVE | Booking/history/fleet/rewards; local game survives WAN loss |
| Movement Signature | RESEARCH ONLY | Generic motion okay; hole-specific authority needs FTO review |
| Rechargeable/wireless-charge ball | REJECT V1 | Mechanical, service, power and IP complexity without evidence |

---

## 20. Official and primary references

- Bluetooth SIG, *Bluetooth Core 6.0 feature overview — Channel Sounding*: https://www.bluetooth.com/core-specification-6-feature-overview/
- Bluetooth SIG, *Channel Sounding*: https://www.bluetooth.com/learn-about-bluetooth/feature-enhancements/channel-sounding/
- Nordic, *Channel Sounding*: https://www.nordicsemi.com/Products/Wireless/Bluetooth-Low-Energy/Channel-Sounding
- Nordic, *nRF54L15*: https://www.nordicsemi.com/Products/nRF54L15
- Nordic, *nRF54L15 Tag*: https://www.nordicsemi.com/Products/Development-hardware/nRF54L15-Tag
- Silicon Labs, *Channel Sounding performance metrics*: https://docs.silabs.com/rtl-lib/latest/rtl-lib-channel-sounding-dev-guide/07-channel-sounding-performance-metrics
- Schex et al., *Connectionless Bluetooth LE Channel Sounding via PAwR* (research, not Production V1): https://arxiv.org/abs/2605.17094
- Qorvo, *DWM3001C* (UWB comparison): https://www.qorvo.com/products/p/DWM3001C
- Zephyr, *TF-M / MCUboot secure boot*: https://docs.zephyrproject.org/latest/services/tfm/overview.html
- TI, protected/isolated RS-485 references: https://www.ti.com/tool/TIDA-00333 and https://www.ti.com/tool/TIDA-00731
- Google Patents, `US9808677B2` and `US11724172B2`: https://patents.google.com/patent/US9808677B2/en and https://patents.google.com/patent/US11724172B2/en

Public Puttshack implementation details not disclosed in these sources are marked as unknown and are not architecture facts.
