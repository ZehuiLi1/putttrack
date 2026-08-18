# Zone Gateway Architecture

## 1. Decision

Production planning uses one Zone Gateway for approximately two to three neighbouring holes. The one-hole pilot may use one Gateway for convenience. A final site plan may adjust the ratio based on cable routes, RF-cell scheduling, power domains and failure containment.

Rejected defaults:

- no Gateway with every field node home-run directly to Edge;
- a Linux SBC at every hole;
- a Gateway that owns final score authority.

## 2. Why a Zone Gateway is required

It provides a deterministic boundary between radio/field timing and venue application software:

- local CS scheduling;
- pair/connection lifecycle;
- source timestamp coordination;
- tee/cup/feature sensor collection;
- bounded outage buffering;
- Anchor health and update relay;
- isolation of field-bus faults;
- one manageable Ethernet endpoint per zone.

Without it, the Edge server becomes tightly coupled to serial cables, GPIO and radio timing for 18 holes.

## 3. Zone size

Planning baseline:

```text
Zone Z1: H01-H03
Zone Z2: H04-H06
...
Zone Z6: H16-H18
```

The Gateway should be sized for approximately:

- 8–15 fixed Anchors/sensor nodes;
- up to three simultaneously active ordinary-hole balls;
- four-player groups where only one player per ordinary hole is high-rate active;
- two protected field-bus branches;
- local queues sufficient for a defined Edge interruption.

## 4. Responsibilities

### Scheduling

- discover assigned balls in its cells;
- request/maintain permitted connected-CS links;
- enforce one active CS procedure per ball at a time;
- choose best-N Anchors and update rate by motion/confidence state;
- coordinate neighbouring cell timing/coexistence policy;
- report actual airtime and missed deadlines.

### Field I/O

- read tee presence, cup and feature nodes;
- control READY light/ring/audio only through presentation/arming commands;
- never add points locally;
- timestamp sensor edges at the nearest deterministic device.

### Time

- maintain gateway monotonic clock;
- synchronize with Edge over Ethernet;
- distribute offset/sync frames to RS-485 nodes;
- attach boot ID, sequence and source time to every observation;
- expose clock health/uncertainty.

### Buffering

- persist a bounded append-only queue during short LAN/Edge interruptions;
- preserve event order and source timestamps;
- emit explicit gap/overflow records rather than silently dropping;
- replay idempotently after reconnect.

### Health and lifecycle

- register device versions and capabilities;
- watchdog field nodes;
- collect voltage/temperature/reset/counter metrics;
- quarantine incompatible or unstable nodes;
- relay signed updates in staged batches;
- support rollback/recovery and physical replacement workflow.

## 5. Hardware direction

### Pilot

An ESP32-S3 Ethernet-class controller or existing Ethernet MCU board is acceptable if it passes:

- deterministic scheduling/load tests;
- dual isolated/protected RS-485 integration;
- watchdog/brownout/recovery;
- signed update and version reporting;
- sustained operation in enclosure/temperature range.

### Production

Select an industrial MCU family only after requirements are frozen. Minimum characteristics:

- wired Ethernet MAC/PHY path with stable SDK;
- hardware watchdog and brownout reset;
- secure boot / signed update support;
- enough UART/SPI/DMA/timers for two field buses and deterministic timestamps;
- nonvolatile queue/config storage;
- optional CAN;
- long-term availability and industrial temperature rating.

Evaluate STM32, NXP and ESP32-S3-class options; do not lock the vendor before the Pilot Gateway verifier exists.

## 6. Interfaces

### Southbound RS-485

Scheduled binary protocol:

- address + device ID;
- message type and schema version;
- gateway epoch/sequence;
- source timestamp/uncertainty;
- payload length and integrity check;
- authenticated command/update envelope where practical;
- explicit ACK/retry for commands, streaming policy for observations.

### Northbound Ethernet

Authenticated versioned protocol to Edge, preferably over mTLS:

- device/zone registration;
- health snapshots;
- observations and physical events;
- scheduler state and commands;
- update/recovery jobs;
- buffered replay with idempotency keys.

## 7. Gateway state machine

```text
BOOT
 -> SELF_TEST
 -> REGISTERING
 -> SYNCING
 -> READY
 -> ACTIVE

side/degraded states:
 BUS_DEGRADED
 EDGE_OFFLINE_BUFFERING
 UPDATE_STAGED
 UPDATING
 ROLLBACK
 FAULT
 QUARANTINED
```

`READY` means field devices, clocks and protocol compatibility satisfy the zone policy. `ACTIVE` means at least one hole is running. A zone can remain operational with a degraded device only if score-authority rules explicitly permit it.

## 8. Failure containment

- Each RS-485 branch is independently fused/protected.
- A single short/open should not remove the second branch or Ethernet uplink.
- Gateway reboot must not duplicate gameplay events; source IDs/sequences and Edge idempotency enforce this.
- Gateway cannot create authoritative score while Edge is unavailable; it buffers confirmed physical observations and presentation may show a controlled pause/degraded message if required.
- A spare pre-provisioned Gateway must be replaceable without reconfiguring every field node manually.

## 9. Revisit triggers

Change zone size/topology if:

- measured scheduling headroom falls below 40%;
- RS-485 length/fanout or power drop exceeds design limits;
- a zone failure affects too many playable holes;
- per-hole local mechanics require independent control;
- shared Gateway latency exceeds evidence/presentation gates;
- site topology makes two-hole or four-hole zones materially simpler.
