# ADR-006 — Wired Field Bus and Ethernet/PoE Backbone

## Context

CS already consumes 2.4 GHz airtime. Outdoor nodes need robust power, diagnostics and maintainable wiring.

## Options

1. BLE/Wi-Fi Anchor backhaul.
2. Ethernet/PoE to every field node.
3. 24 V + protected RS-485 locally, Ethernet/PoE to Gateways/HMI.
4. CAN locally.

## Decision

Choose option 3 as baseline. CAN remains a justified alternative for a subsystem; fibre is used for surge/distance/domain isolation when required.

## Why

- does not compete with CS RF;
- RS-485 supports long multidrop industrial wiring;
- 24 V reduces distribution loss;
- Ethernet/PoE provides standard managed backbone and HMI power;
- Zone Gateway isolates protocol and fault domains.

## Risks

Outdoor surge/grounding, branch shorts and bus topology errors can cause field outages.

## Validation

Protected/isolated bus prototype, maximum-length/fanout/load test, fault injection, surge/environment engineering and as-built service records.

## Revisit trigger

- site distances/electrical separation require fibre;
- deterministic CAN arbitration materially improves a machinery subsystem;
- production Anchor Ethernet cost becomes justified by maintenance savings.
