# Hardware and Venue Topology

## 1. Current baseline

The venue is built around deterministic fixed sensors first. Smart-ball and CS infrastructure are added only when they provide additional value.

```text
                                     WAN
                                      |
                              Firewall / Router
                                      |
                        Managed core PoE switch (UPS)
        +-----------------------------+----------------------------+
        |              |              |             |              |
     Edge PC       Check-in HMI   Operator HMI   Hole displays   Hole/Zone GWs
                                                                       |
                                                               local 24 V PSU
                                                                       |
                                                          optical sensors / RS-485
```

For the first one-hole MVP, a single available Waveshare ESP32-S3 PoE/Ethernet 8DI/8DO controller is both the hole controller and field-I/O endpoint.

---

## 2. One-hole V0 physical topology

```text
                         Local Venue Edge
                              ^
                              |
                         Ethernet / PoE
                              |
               Waveshare ESP32-S3 8DI/8DO
                              |
                    8 isolated DI inputs
                              |
         +--------------------+--------------------+
         |                    |                    |
      Tee x2             Route/Zone x4          Cup x2
```

Recommended input allocation:

| DI | Sensor |
|---|---|
| 1 | tee ball-present beam |
| 2 | launch-confirmation beam |
| 3 | route/zone A |
| 4 | route/zone B |
| 5 | route/zone C |
| 6 | route/zone D |
| 7 | cup/return upper beam |
| 8 | cup/return lower beam |

This deliberate eight-input baseline avoids buying or integrating an expander before the physical game loop is proven.

---

## 3. Photoelectric sensing

### Sensor class

For outdoor deployment prefer industrial modulated through-beam photoelectric sensors with:

- 10–30 V DC supply, nominal 24 V installation;
- NPN output compatible with the isolated DI input;
- IP65 minimum, IP67 where appropriate;
- fast response suitable for golf-ball passage;
- stable operation in sunlight and normal outdoor conditions;
- accessible alignment/service indication where practical.

### Mechanical installation

Do not leave exposed transmitter/receiver posts where players, clubs or balls can easily knock them out of alignment.

Preferred arrangement:

```text
course sidewall                           course sidewall
     |                                          |
 recessed TX  --------------------------  recessed RX
     |                 ball                     |
```

Use protected optical windows, drain/condensation-aware cavities and serviceable mounting.

---

## 4. Controller roles

### Hole controller

Pilot: existing Waveshare ESP32-S3 PoE/Ethernet 8DI/8DO.

Responsibilities:

- read/debounce DI;
- timestamp edges;
- identify simple legal sequences;
- monitor input health;
- generate semantic evidence;
- buffer/retry short network interruptions;
- drive simple local DO triggers;
- forward through wired Ethernet.

It does not own authoritative score.

### Venue Edge

Authoritative local compute and persistence on the wired LAN.

Owns:

- active player/session;
- course/hole configuration;
- reward/penalty rules;
- deterministic Gameplay Engine;
- event audit/replay;
- HMI/player presentation state;
- operator correction workflow.

---

## 5. I/O expansion

### RS-485 default

When the onboard eight inputs are insufficient, use protected RS-485/Modbus remote I/O.

```text
Waveshare controller
       |
       +-------- RS-485 -------- remote 8/16 DI/DO
       |
       +-------- RS-485 -------- remote 8/16 DI/DO
```

Why RS-485 is the default for simple field I/O:

- mature 8/16-DI and mixed-I/O modules are widely available;
- long differential field wiring;
- simple addressable multidrop topology;
- easy commissioning with USB-RS485/Modbus tools;
- low bandwidth is sufficient for optical event inputs.

Prefer remote I/O near sensor clusters instead of pulling every individual sensor cable back across a long hole.

### CAN

CAN remains available for future **intelligent** distributed nodes such as motorised obstacles, actuators or mechanisms that benefit from asynchronous arbitration/local control.

Do not choose CAN merely to read simple optical DI.

---

## 6. Output / feedback topology

The onboard eight DO channels can initially trigger:

1. Tee READY cue;
2. Safe route feedback;
3. Bonus route feedback;
4. Jackpot feedback;
5. Hazard feedback;
6. cup/finish effect;
7. audio/effect input;
8. spare.

For richer RGB/DMX/Art-Net lighting, use a dedicated lighting controller. The hole controller should publish semantic triggers such as `BONUS_TRIGGERED` instead of timing complex animations itself.

---

## 7. Field wiring

### Ethernet / PoE

Use for:

- Hole/Zone controllers;
- displays and check-in/operator terminals;
- Edge server and core infrastructure;
- later smart-ball/NFC gateway infrastructure where useful.

### 24 V field power

Use local fused 24 V SELV distribution for photoelectric sensors and later remote I/O.

Benefits:

- good noise margin;
- manageable drop over field wiring;
- compatibility with industrial sensors;
- straightforward protected distribution.

### RS-485

Use termination at the physical bus ends, appropriate bias/failsafe design, surge/TVS protection, labelled addresses and service disconnects.

### Fibre

Reserve for real electrical/distance reasons: separate buildings, long exposed trunks, lightning/ground-potential isolation or copper-distance limits.

---

## 8. Smart-ball V1 hardware additions

The optical venue remains unchanged when smart balls arrive.

Smart-ball-side:

- nRF54L15;
- NFC/NFCT antenna;
- BLE;
- IMU;
- single primary cell;
- candidate direct battery or nPM2100 power path.

Venue additions may include:

- Tee NFC reader for wake/Ball ID;
- BLE receiver/gateway capability;
- optional Hole NFC identity station in the return chute.

None replaces the fixed optical cup/route sensors.

---

## 9. Optional CS V2 hardware

Existing Bbo/nRF54L15 hardware remains the research rig.

A production CS Anchor/RF-cell network is **not** a current baseline requirement. Add fixed CS nodes only if a validated product feature such as live trajectory or multi-ball association justifies the cost and RF/power/scheduling complexity.

---

## 10. Outdoor installation requirements

- IP65 minimum, IP67 where washdown/pooling is credible;
- UV-resistant enclosures, cable glands and labels;
- condensation/drainage strategy;
- service access without removing large course scenery;
- surge protection on exposed copper and zone feeds;
- spare conduit/cable capacity and Ethernet ports;
- low-voltage game wiring physically/electrically separated from 240 V as required;
- earthing/bonding/lightning protection designed for the actual Australian site.

---

## 11. Pilot evolution

### V0.1 — one-hole optical MVP

```text
ordinary ball
 -> 8 optical inputs
 -> Waveshare 8DI/8DO
 -> Ethernet
 -> local Edge/UI
```

### V0.2 — one-hole outdoor/reward soak

- protected sensor mounts;
- real 24 V field wiring;
- Safe/Bonus/Jackpot/Hazard effects;
- false-trigger/maintenance logging.

### V0.3 — I/O expansion

Add RS-485 remote I/O only if more sensors are justified.

### V1 — smart ball

Add NFC/BLE/IMU identity/state while preserving V0 sensing.

### V2 — optional CS

Add research/trajectory nodes only for features that have passed value and performance gates.

### 3–6-hole pilot

Replicate the proven hole-controller pattern, then decide whether grouping several holes behind a zone cabinet/gateway materially improves maintenance/cost.

### Full 18-hole

Scale after physical-sensor reliability, wiring/fault recovery, local Edge, staff workflow and smart-ball decisions pass their pilot gates. CS scalability is only a rollout blocker if the chosen commercial feature actually depends on CS.

---

## 12. Installation records

The Device Registry should retain:

- device/controller/sensor ID;
- hardware revision;
- hole/zone and DI/DO/bus mapping;
- cable/port/fuse mapping;
- firmware/config version;
- installation/alignment photos;
- service/replacement history;
- for smart balls: Ball ID, firmware, battery/service status;
- for optional CS nodes: coordinates/orientation and RF/range calibration.
