# Hole / Zone Gateway Architecture

## 1. Decision

The first physical pilot uses one available Ethernet controller per hole for simplicity. Production may later group approximately 2–3 neighbouring holes behind a zone cabinet/gateway if cable routes, maintenance and fault-domain evidence justify it.

The gateway is primarily a **wired field-I/O and event boundary**. Channel Sounding scheduling is an optional later responsibility, not a V0/V1 requirement.

Rejected defaults:

- every field sensor home-run directly to the Edge server;
- Wi-Fi/BLE as the scoring-critical fixed-sensor backbone;
- a Linux SBC at every hole;
- a gateway that owns final score authority.

---

## 2. One-hole V0 role

Pilot hardware: existing Waveshare ESP32-S3 PoE/Ethernet 8DI/8DO.

Responsibilities:

- read and debounce eight optical inputs;
- timestamp edges and maintain source sequence numbers;
- recognise simple legal patterns such as tee launch and ordered cup passage;
- publish semantic evidence to Venue Edge;
- drive simple local feedback outputs;
- monitor field-sensor/controller health;
- buffer/retry short Ethernet outages;
- never own authoritative score.

The controller does not need CS, NFC or smart-ball connectivity to run the first hole.

---

## 3. V0 input/evidence flow

```text
24 V optical sensors
        |
        v
8 isolated DI
        |
Waveshare hole controller
        |
semantic events
        |
wired Ethernet
        |
Venue Edge / Gameplay Engine
```

Typical events:

```text
tee.presented
tee.launch_confirmed
zone.entered
feature.confirmed
cup.entry_candidate
cup.confirmed
sensor.fault
```

The controller should not send only opaque GPIO snapshots when it can provide a well-defined semantic candidate/event with the raw channel/timing diagnostics attached.

---

## 4. Field I/O expansion

When more than eight I/O channels are needed, use protected RS-485/Modbus remote I/O.

```text
hole/zone controller
       |
RS-485 / Modbus
       +---- remote DI/DO A
       +---- remote DI/DO B
```

Benefits:

- mature industrial I/O modules;
- simple multidrop addressing;
- differential long-line transport;
- easier maintenance/commissioning than custom CAN nodes for basic sensors;
- remote I/O can be located near optical sensor clusters.

CAN remains optional for future intelligent motor/actuator subsystems.

---

## 5. Production zone grouping

Do not freeze one gateway per 2–3 holes before the physical pilot.

Evaluate after real installation data exists:

- controller and cabinet cost;
- copper routes and conduit;
- RS-485 lengths/fanout;
- local power domains;
- maintenance access;
- how many holes a single gateway failure should affect;
- whether individual holes have local mechanisms needing independent control.

A likely venue may still use several zone cabinets, but this is an installation optimisation rather than a prerequisite of the core game model.

---

## 6. Time / event ordering

For optical V0:

- maintain a monotonic controller clock;
- attach boot ID + source sequence + source timestamp;
- preserve ordered beam sequences locally where latency matters;
- send events idempotently to Edge;
- report explicit queue overflow/gaps.

Global sub-millisecond synchronisation is not required for ordinary single-hole optical event logic. Add stricter synchronisation only for a later feature that proves it needs it.

---

## 7. Buffering and recovery

- keep a bounded queue during short LAN/Edge outages;
- preserve event order and source timing;
- retry using stable event IDs;
- controller reboot must not duplicate gameplay score;
- field faults should emit explicit health/fault evidence;
- a spare controller should be replaceable with a documented I/O map/configuration restore.

The controller cannot invent authoritative score while Edge is unavailable.

---

## 8. Smart-ball V1 extension

When smart balls are introduced, gateway/controller responsibilities may add:

- Tee NFC reader adapter;
- BLE receiver/gateway transport;
- smart-ball health and session-association forwarding;
- optional Hole NFC identity reader.

Optical event acquisition remains unchanged.

The smart ball does not need to connect to the same ESP32 controller if a separate BLE/NFC gateway architecture is operationally better; both paths converge at Venue Edge through semantic events.

---

## 9. Optional CS V2 extension

If Channel Sounding is promoted into a real product feature, a zone gateway may additionally own:

- CS link/session lifecycle;
- optional Anchor scheduling;
- timestamped range ingestion;
- local RF diagnostics/buffering.

Those responsibilities exist only for CS-enabled zones/features. They are not reasons to complicate the V0 optical gateway.

---

## 10. Production hardware direction

Pilot hardware is already available. Production controller selection should wait until the I/O, enclosure, bus and maintenance requirements are measured.

Minimum likely characteristics:

- wired Ethernet/PoE or robust Ethernet + local 24 V power;
- hardware watchdog/brownout recovery;
- secure/signable firmware update path;
- protected isolated DI and RS-485;
- nonvolatile configuration/buffer storage;
- sufficient industrial temperature/environmental suitability;
- optional CAN only if intelligent local mechanisms require it.

Do not lock an MCU vendor before the pilot proves the required I/O and operational model.

---

## 11. Revisit triggers

Change topology if:

- one-controller-per-hole materially increases cost/maintenance;
- RS-485 wiring makes shared zone cabinets clearly superior;
- a gateway failure affects too many holes;
- presentation/evidence latency misses targets;
- future smart-ball/CS features introduce measured scheduling requirements;
- motorised attractions justify CAN/intelligent local nodes.
