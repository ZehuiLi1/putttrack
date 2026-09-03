# Hardware and 18-Hole Venue Topology

## 1. Recommended production topology

The production planning baseline is one Zone Gateway per two to three neighbouring holes, not one Linux computer per hole and not a direct cable from every Anchor to the Edge server.

```text
                                     WAN
                                      |
                              Firewall / Router
                                      |
                        Managed core PoE switch (UPS)
        +-----------------------------+----------------------------+
        |              |              |             |              |
     Edge PC       Check-in HMI   Operator HMI   Hole displays   Zone GWs
                                                       PoE        Z1...Z6
                                                                    |
                                                         24 V local field PSU
                                                           + two RS-485 trunks
                                                                    |
               +---------------------------+------------------------+
               |                           |                        |
         Hole A Anchors              Hole B Anchors           Hole C Anchors
         Tee/Cup/Feature             Tee/Cup/Feature          Tee/Cup/Feature
```

Six Zone Gateways is only a first planning number for an 18-hole course. The site layout, cable routes, power domains and RF-cell tests determine the final count.

## 2. Physical device classes

### Smart Ball

Battery-powered nRF54L15 device with opaque identity, CS Reflector, BLE control/health and generic motion sensing.

### Anchor

Fixed CS Initiator with validated RF layout, protected 24 V power input and wired field-bus transport.

### Tee node

One fixed PN532-class start reader and indicator controller. Its immutable
`reader_id -> hole_id` installation mapping creates only a bounded NFC
activation request; Edge assignment and credential checks grant authority. It
may be combined with a nearby node enclosure only if failure and maintenance
remain separable.

### Cup / feature sensor node

The initial Cup is an optical entry sensor plus a PN532-class identity/presence
reader after the Ball settles. Both may use one ESP32 but keep distinct sensor
IDs and raw evidence. Completion requires the exact current Ball and active
hole lease. Other feature sensor choices remain hole-specific; every output is
timestamped and health-monitored.

### Zone Gateway

Coordinates 2–3 holes, schedules CS, synchronizes field timestamps, collects sensors, buffers, relays updates and forwards through Ethernet.

### Hole display / indicator

PoE or Ethernet-connected sunlight-readable display plus local ring/light/audio. It consumes presentation state and cannot mutate score directly.

### Edge server

Authoritative local compute and persistence on UPS-backed wired LAN.

## 3. Field wiring

### Ethernet / PoE

Use for:

- Zone Gateways;
- displays and check-in/operator terminals;
- optional cameras;
- Edge server and network infrastructure.

Benefits: standard diagnostics, managed switching, VLANs, time sync, remote update and replaceable endpoints.

### 24 V + protected RS-485

Use for Anchors and simple tee/cup/feature nodes:

- high noise margin and manageable voltage drop;
- multidrop field bus;
- lower connector/cabling cost than Ethernet at every node;
- suitable for isolated/protected outdoor branches.

Each Zone Gateway should have two independently protected/isolated buses so one cable fault does not remove the whole zone. Use fused branches, termination at the physical ends, biasing/failsafe design, TVS/surge components and labelled service disconnects.

### CAN

CAN is an acceptable alternative where deterministic arbitration and existing venue controls justify it. Do not mix CAN and RS-485 without a clear subsystem reason. RS-485 is the default because the traffic is scheduled and low bandwidth.

### Fibre

Use only where it solves a real electrical or distance problem:

- separate buildings;
- exposed long trunks with severe lightning/ground-potential risk;
- distance beyond practical copper Ethernet;
- need to isolate surge domains.

## 4. Outdoor installation requirements

- IP65 minimum, IP67 where washdown or pooling is credible.
- UV-resistant enclosures, cable glands and labels.
- Condensation management and drainage orientation.
- Shielding/grounding designed as a system, not ad hoc at each node.
- Surge protection at building entry, zone cabinet and exposed copper branches.
- Physical service access without dismantling course scenery.
- Replaceable modules with keyed connectors and persistent device labels.
- Spare conduit/cable capacity and managed-switch spare ports.
- Separate game low voltage from 240 V and comply with applicable Australian electrical rules.

## 5. Power domains

### UPS-backed

- Edge server;
- core switch/firewall;
- check-in/operator authority;
- selected Zone Gateways and displays where operational continuity warrants it.

### Zone 24 V supply

Provide local fused outputs for Anchors and sensors. A zone supply reduces voltage-drop and fault-domain size compared with a single long central low-voltage bus.

### Smart Ball

Primary-cell candidate; no field charging dependency in Production V1. Service process handles battery/service replacement or ball retirement.

## 6. Pilot evolution

### One-hole lab

```text
Nordic Tag
  <-> 5 Bbo boards over CS
Bbo USB serial -> PC
camera -> PC
simulated/real tee and cup inputs
```

### One-hole physical pilot

```text
custom/pilot anchors -> pilot Zone Gateway
cup + tee nodes       -> pilot Zone Gateway
Gateway -> Ethernet -> Edge
Hole display -> PoE
```

### 3–6-hole pilot

Validate Zone Gateway sharing, neighbouring RF cells, outdoor wiring, update recovery and staff workflows.

### Full 18-hole

Deploy only after the zone/fault and 20/40/80-ball models pass. Keep spare gateways, Anchors, displays and provisioned balls onsite.

## 7. Installation records

The Device Registry must retain:

- device ID and hardware revision;
- physical coordinates/height/orientation;
- zone/hole and bus address;
- cable/port/fuse mapping;
- firmware/config version;
- RF and range calibration;
- installation photos;
- service and replacement history.
