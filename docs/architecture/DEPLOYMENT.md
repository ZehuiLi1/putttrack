# Deployment and Hardware Evolution

## 1. Research Rig

### Hardware

- 1–2 Nordic nRF54L15 Tags;
- 5 identical Bbo nRF54L15 Anchors + 1 spare;
- PC/Linux host;
- overhead camera and sync LED;
- development tee/cup/feature sensors;
- power measurement equipment when available.

### Software

- Nordic official CS samples as baseline;
- structured range/IMU/camera logger;
- static robust WLS and asynchronous range EKF;
- simulator and existing Gameplay Engine;
- research dataset manifests.

### Exit

Pass Phase 0–4 of the verification matrix. No final PCB decision before representative dynamic and power data exists.

## 2. EVT

### Hardware

- first custom ball core with nRF54L15;
- candidate nPM2100/CR2447 power path;
- both motion-sensor candidates and both antenna paths retained;
- custom production-intent Anchor prototype;
- pilot Zone Gateway prototype;
- one physical hole with tee/cup/feature sensors and HMI.

### Goals

- RF performance inside shell;
- impact/balance/power;
- device identity and signed firmware;
- real gateway/RS-485/Ethernet interfaces;
- one-hole end-to-end score authority.

### Exit

- custom Ball RF/energy/impact gates;
- 1,000-round one-hole soak;
- update/rollback/fault injection;
- operator recovery without developer intervention.

## 3. DVT

### Hardware

- sensor/antenna set reduced to likely production BOM;
- production-like ball shell/core and manufacturing test jig;
- IP-rated Anchors/Gateways/sensors/displays;
- managed PoE/24 V/RS-485 installation;
- 3–6-hole representative outdoor pilot.

### Goals

- thermal/UV/water/impact/endurance;
- multi-hole RF coexistence and zone scheduling;
- production provisioning/calibration;
- staff workflows, spares and replaceability;
- security and OTA release process.

### Exit

- reliability and environmental gates;
- 20/40-ball representative load;
- maintenance MTTR and replacement procedure;
- production BOM/supply review;
- pre-commercial FTO checkpoint.

## 4. Pilot Venue

### Stage 1: 3–6 holes

Validate pacing, check-in, ball handoff, shared Zone Gateways, HMI visibility, network/UPS and fault recovery.

### Stage 2: 18 holes

Incrementally commission zones while preserving rollback to manual/degraded modes.

### Exit

- venue-scale simulation and measured operation agree;
- scoring integrity/uptime targets sustained for defined pilot period;
- staff can diagnose common faults without engineering access;
- customer onboarding and zero-touch play gates pass;
- release and data-retention processes approved.

## 5. Production

- qualified suppliers and alternates;
- manufacturing tests for identity, current, RF, IMU, battery, balance and secure provisioning;
- signed release train and staged rollout;
- documented installation/site calibration;
- spare-stock and RMA/service model;
- jurisdiction-specific regulatory and patent/FTO review;
- telemetry-driven maintenance and periodic architecture review.

## 6. BOM principles

Do not optimize research board cost as if it were production BOM. Cost decisions are made after requirements are known:

- Bbo/Nordic Tag are development expense;
- production Anchor count follows P95/no-fix evidence;
- sensor/dual-antenna/PMIC retained only when measured value exceeds cost;
- Zone Gateway and wired field bus may reduce total installation/service cost even if component BOM rises;
- physical scoring sensors are justified by lower dispute/support cost.

## 7. Release/rollback plan

Every stage uses:

- versioned hardware capability registry;
- signed firmware/software/config;
- compatibility checks;
- canary cohort;
- automated smoke/health verification;
- previous known-good image/config;
- explicit rollback/quarantine;
- no mass update during active sessions.

## 8. Site handover package

- as-built network/power drawings;
- device/port/fuse/cable map;
- Anchor coordinates/orientations and calibration;
- firmware/config baseline;
- spare inventory;
- recovery/rollback instructions;
- operator fault playbook;
- security credential/revocation procedures;
- test evidence and acceptance sign-off.
