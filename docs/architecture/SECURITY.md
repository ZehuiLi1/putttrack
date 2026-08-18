# Security, Identity and OTA Architecture

## 1. Security goals

- prevent an unauthorised ball/device from changing score;
- prevent unsigned/rolled-back firmware from running where platform support allows;
- protect operator/admin functions;
- maintain serviceability without adding player friction;
- contain a lost/stolen/faulty device;
- preserve evidence integrity and update audit.

## 2. Identity model

Each physical device has:

- immutable/opaque `DEVICE_ID`;
- device class and hardware revision;
- provisioned credential/key material;
- firmware compatibility and security epoch;
- service/revocation state.

A Ball has a separate human label/colour/number. BLE MAC address and printed label are not authoritative identity.

## 3. Trust relationships

```text
Ball <encrypted/authenticated BLE> Anchor/RF cell
Anchor <authenticated field protocol> Zone Gateway
Gateway <mTLS> Venue Edge
Edge <outbound TLS/mTLS> Cloud
Operator <role-authenticated local session> Edge
```

RS-485 is physically local but not assumed trustworthy; commands/updates use authenticated envelopes and anti-replay sequences.

## 4. Boot and firmware

### Ball/Anchor/Gateway

- signed image verification with MCUboot/secure boot;
- rollback counter/policy where supported;
- separate development and production signing keys;
- protected production debug access;
- known-good recovery image or dual-slot rollback;
- version/capability compatibility checked before active play.

nRF54L15 provides TrustZone, KMU/cryptographic facilities, immutable boot-region options and authenticated debug mechanisms; the exact production chain must be verified against the selected NCS release and provisioning process.

### Key handling

- private release keys remain offline/HSM-controlled;
- CI/release service receives least-privilege signing access;
- factory/service provisioning has audited key/certificate issuance;
- revocation lists synchronize to Venue Edge;
- no shared universal operational key across all devices if avoidable.

## 5. OTA policy

### Ball

- update at service/assignment station or controlled idle window;
- never during a live stroke/active player state;
- verify power threshold before update;
- post-update self-test and version report;
- rollback or quarantine on failure.

### Anchor/Gateway

- staged by zone and device cohort;
- do not update every node in a hole simultaneously;
- retain enough healthy nodes for degraded operation;
- pre/post health and ranging sanity checks;
- automatic rollback/quarantine if verifier fails.

### Edge/HMI

- signed packages/images;
- database migration backup/rollback;
- canary deployment and local smoke test;
- no cloud dependency for rollback.

## 6. Operator and admin authorization

Roles:

- play attendant: normal recovery/pause;
- supervisor: audited score correction/session decisions;
- maintainer: device/firmware/calibration;
- administrator: policy/users/releases.

Every privileged action records actor, reason, timestamp, target, previous/new state and trace ID.

## 7. Lost/stolen device handling

- revoke the device credential/assignment eligibility;
- block from READY/scoring while still allowing a diagnostic discovery state if safe;
- remove cloud/venue assignment links;
- preserve historical audit under the immutable device ID;
- re-provision only through authenticated service workflow.

## 8. Network segmentation

Suggested VLANs/firewall zones:

- venue control (Gateways/Edge);
- HMI/player displays;
- cameras/research;
- operator/admin;
- guest Wi-Fi;
- cloud/WAN edge.

Guest networks cannot address control devices. HMI can consume only required presentation APIs.

## 9. Threat-driven requirements

| Threat | Control |
|---|---|
| BLE spoofed ball ID | authenticated association; opaque provisioned identity |
| replayed sensor packet | boot ID + sequence + event idempotency/anti-replay |
| compromised display | read-only presentation authority |
| malicious score edit | role auth + explicit operator event + audit |
| unsigned firmware | secure boot / signed update |
| downgrade | rollback policy/security counter |
| stolen Anchor/Gateway | credential revocation and protected debug |
| WAN/cloud compromise | local score authority and outbound-restricted trust |
| partial update | cohort staging, health gate, rollback/quarantine |

## 10. Verification gates

- unsigned and modified image rejected;
- rollback/downgrade rejected according to policy;
- duplicate/replayed device messages cannot mutate score;
- revoked ball cannot arm;
- lost Edge/WAN does not bypass local auth/audit;
- update recovery exercised on each hardware class;
- credentials can be rotated/revoked without replacing every device.
