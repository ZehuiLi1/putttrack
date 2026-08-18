# Architecture Implementation Issue Map

This file maps the accepted architecture to live GitHub work. Issue numbers are dependency ordered; work may overlap only where the input/output contracts are already frozen.

## Foundation

| Issue | Workstream | Depends on | Exit |
|---|---|---|---|
| [#6](https://github.com/ZehuiLi1/putttrack/issues/6) | exact-head Gameplay verifier, schemas, capture and replay | PR #5 architecture | green baseline and deterministic replay |
| [#1](https://github.com/ZehuiLi1/putttrack/issues/1) | Bbo/Nordic CS rig, version manifest and structured logger | #6 contract guidance | repeatable Bbo -> Tag ranging and parsable source-timestamped evidence |

## Localisation and evidence

| Issue | Workstream | Depends on | Exit |
|---|---|---|---|
| [#7](https://github.com/ZehuiLi1/putttrack/issues/7) | calibrated 3/4/5-Anchor static benchmark | #1, #6 | static gate and evidence-backed Anchor count decision |
| [#8](https://github.com/ZehuiLi1/putttrack/issues/8) | asynchronous range-domain EKF + camera GT | #6, #7 | dynamic tracking gate and UWB trigger decision |
| [#9](https://github.com/ZehuiLi1/putttrack/issues/9) | generic motion states + conservative evidence fusion | #6, #8 | stroke/pickup/cup evidence gates |

## Field and scale

| Issue | Workstream | Depends on | Exit |
|---|---|---|---|
| [#10](https://github.com/ZehuiLi1/putttrack/issues/10) | Zone Gateway, protected 24 V/RS-485 and Ethernet/PoE pilot | #1, #6 | one-hole then 2–3-hole Gateway/fault/timing gate |
| [#11](https://github.com/ZehuiLi1/putttrack/issues/11) | connected-CS 20/40/80-ball scheduler and venue simulator | #1, #6, #10 | bounded load/latency/energy and final Zone-size evidence |

## Product vertical slice

| Issue | Workstream | Depends on | Exit |
|---|---|---|---|
| [#3](https://github.com/ZehuiLi1/putttrack/issues/3) | guest check-in, Ball assignment and tee-screen gameplay UI | #6; can use simulated evidence first | sensing-independent customer-facing flow |
| [#12](https://github.com/ZehuiLi1/putttrack/issues/12) | one authoritative physical hole + 1,000-round soak | #3, #8, #9, #10 | complete local/WAN-offline physical-hole gate |

## Product hardware

| Issue | Workstream | Depends on | Exit |
|---|---|---|---|
| [#13](https://github.com/ZehuiLi1/putttrack/issues/13) | custom Smart Ball EVT power/RF/motion/impact/balance/security gate | #7, #8, #9, #11, #12 | Phase 8/9 custom-core evidence |

## Architecture tracking

- [#4](https://github.com/ZehuiLi1/putttrack/issues/4) tracks Architecture Constitution review and PR #5.
- [PR #5](https://github.com/ZehuiLi1/putttrack/pull/5) contains this convergence pass.

## Critical path

```text
#6 schema/replay
  |\
  | #1 CS rig/logger
  |    |\
  |    | #7 static localisation -> #8 dynamic tracking -> #9 evidence fusion
  |    |
  |    +-> #10 Zone Gateway -> #11 multi-ball/venue model
  |
  +-> #3 simulated gameplay/HMI

#3 + #8 + #9 + #10 -> #12 physical one-hole soak

#7 + #8 + #9 + #11 + #12 -> #13 custom Smart Ball EVT
```

## Parallelism rules

- #3 may implement check-in/HMI against simulated evidence while localisation work proceeds.
- #10 may build its protocol simulator before real Anchor firmware is complete, but final field-bus acceptance needs #1 data.
- #9 may begin dataset tooling before #8 passes, but production evidence thresholds require timestamped track quality.
- #13 must not start PCB layout merely because components are available; it begins only when its dependency gates provide measured requirements.
