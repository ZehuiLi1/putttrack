# ADR-011 — Primary-Cell-First Ball Power Architecture

## Context

A sealed impact-resistant ball is difficult to charge/service. Wireless charging adds coil, alignment, thermal, mechanical and infrastructure complexity. Public Puttshack material shows a CR2447+nPM2100 route is plausible, but PuttTrack needs its own power evidence.

## Options

1. CR2447/primary cell with efficient PMIC.
2. Rechargeable Li cell + inductive charging rack.
3. Replaceable consumer battery holder.
4. Wired/contact charging.

## Decision

Use option 1 as the EVT/Production V1 candidate: nPM2100 + CR2447 subject to measured duty cycle. Reject removable spring holders in the final ball. Defer rechargeable/wireless charging.

## Why

- simplest sealed/impact architecture;
- no daily charging operation;
- low quiescent-current PMIC candidate;
- avoids charging-coil mass and venue infrastructure;
- supports multi-year target if scheduling succeeds.

## Risks

Battery may be non-serviceable or require ball retirement; actual CS workload may miss life target; metal cell affects RF/balance.

## Validation

Measured current waveform and venue workload replay, temperature/pulse/brownout tests, mechanical/RF-in-shell tests, >=2-year conservative projection and >=5-year stretch.

## Revisit trigger

- projection <2 years;
- replacement economics/environmental impact unacceptable;
- safe serviceable primary-cell core is achieved;
- rechargeable architecture passes mechanical, operational and FTO gates.
