# Multi-Ball and Channel Sounding Scalability

## 1. Constraint

Standard Bluetooth Channel Sounding operates between connected Initiator/Reflector peers. Current Production V1 must therefore assume sequential CS procedures and explicit scheduling; a one-ball demo does not automatically scale.

## 2. Key observation

Eighty balls present in a venue are not eighty high-rate tracking targets.

Locked gameplay provides one active player/ball per ordinary hole. Therefore the nominal maximum high-rate active set is the number of simultaneously active holes, not the total ball inventory.

Example full venue:

```text
18 holes
4-player group/hole
72 balls with groups on course
<=18 high-rate active balls
remaining balls low-rate assigned/stationary
```

## 3. RF-cell model

- Each ordinary hole is one logical RF cell unless site tests support a different boundary.
- Zone Gateway manages 2–3 cells.
- A Ball advertises low-rate identity/health; the local zone claims/schedules it only when assignment/position/tee context indicates relevance.
- High-rate CS remains local to the active hole/cell.
- Handoff is explicit: old zone releases high-rate links after the group/hole state completes; new zone associates at the next tee.

## 4. Production V1 scheduler

### Per ball

- at most one active CS procedure at a time;
- up to several pre-established ACL links only if NCS/controller tests prove stability and power;
- best three geometry Anchors high-rate during rolling;
- fourth Anchor at reduced cadence or when geometry/residuals need it;
- optional fifth/reference Anchor only on low confidence/reacquisition/settling.

### By state

| State | Suggested initial policy to test |
|---|---|
| Unassigned/storage | no CS; sparse advertisement |
| Assigned, not at active hole | coarse zone presence only |
| Presented/READY | establish local links; 1–2 Hz validation |
| Impact/rolling | target >=5 position updates/s; Anchor observations scheduled sequentially |
| Settling | temporary 4/best-4-of-5 confirmation |
| Stationary | 0.2–1 Hz until release/handoff |
| Pickup/carry | low/medium tracking sufficient to support recovery |

These are test starting points, not guaranteed SDK throughput.

## 5. 20/40/80-ball load cases

### 20 balls

- typical pilot load;
- up to 5 active holes/groups;
- validate connection setup, persistent-link option and neighbouring interference.

### 40 balls

- medium venue load;
- 10–12 active holes possible;
- validate Zone Gateway CPU/bus headroom, core LAN queues and 2.4 GHz coexistence.

### 80 balls

- full inventory/stress simulation;
- 18 active balls maximum under ordinary-hole lock;
- all other balls advertise/health only;
- validate assignment/handoff storms, restart/reconnect and bounded buffers.

## 6. Airtime model to implement

For each CS configuration measure:

- setup/security/configuration time;
- steps/channels/procedure duration;
- result transfer time;
- procedure success/missing rate;
- connection interval and other BLE traffic;
- energy at Ball and Anchor;
- scheduler overhead per partner switch.

Model per zone:

```text
required airtime = sum(active balls x scheduled Anchor procedures)
headroom = 1 - required airtime / usable radio budget
```

Production admission requires >=40% timing headroom under P95 representative load, not only mean lab load.

## 7. Wi-Fi/coexistence

- Keep Anchor backhaul wired.
- Prefer 5 GHz/6 GHz for venue Wi-Fi client traffic where practical.
- Survey 2.4 GHz interference at day/night/full occupancy.
- Coordinate CS channel-map strategy through Zone Gateway/Edge.
- Do not assume all neighbouring holes can run identical high-duty schedules without measurements.

## 8. Failure/degradation

When scheduler load or RF quality degrades:

1. reduce idle/stationary rates;
2. use best three Anchors for active movement;
3. preserve tee/stroke/cup critical evidence;
4. disable noncritical live-trajectory embellishment before score authority;
5. queue/retry noncritical analytics;
6. pause a hole rather than cross-associate balls or guess score.

## 9. Connectionless/PAwR path

A 2026 research proof of concept combines PAwR with CS test commands on nRF54L15 and reports large reductions in partner-switch overhead/active charge. Treat it as:

- Research V2 implementation;
- benchmark against connected V1;
- possible future standard/product input;
- not a Production V1 dependency or interoperability promise.

## 10. Gates

- zero cross-ball/cross-hole score mutation in stress simulation;
- active position update target >=5 Hz per active ball at 20/40/80-ball scenarios;
- confirmed-event presentation <=500 ms;
- bounded queues, no silent observation/evidence loss;
- Zone Gateway and Edge steady resource utilization <60%;
- >=40% measured scheduler headroom under representative P95 load;
- reconnect/handoff target <=2 s at next tee, with clear CHECKING state;
- battery/energy projection meets service-life gate.

If connected CS cannot meet these after adaptive scheduling and RF-cell partitioning, run the UWB and/or connectionless-CS decision gate before custom production hardware is frozen.
