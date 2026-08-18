# Keep / Change / Defer / Reject Matrix

| Topic | Disposition | Architecture effect | Revisit evidence |
|---|---|---|---|
| nRF54L15 | KEEP | Ball/Anchor research and first custom-ball candidate | EVT RF/power/security |
| Nordic nRF54L15 Tag | KEEP — research | moving golden reference | custom EVT parity |
| Bbo nRF54L15 | KEEP — research | five homogeneous Anchor rig + spare | production Anchor design |
| Five Anchors | CHANGE | research ablation only | Phase 2 P95/no-fix |
| Centre Anchor | CHANGE | optional RF-optimal/elevated reference | site heatmap |
| Ball Reflector | KEEP | low-power endpoint | Phase 5 link/energy |
| Anchor Initiator | KEEP | powered infrastructure owns procedure | Phase 5 scheduler |
| Bluetooth CS | KEEP — conditional | Production V1 candidate | accuracy/NLOS/load/energy |
| Dual antenna | DEFER | retain in research/EVT | P95/no-fix ablation |
| IMU | KEEP | generic states/scheduling/evidence | sensor/power ablation |
| Separate wake sensor | DEFER | retain in EVT | energy/classification |
| nPM2100 | KEEP — candidate | primary-cell PMIC | workload replay |
| CR2447 | KEEP — candidate | Ball power source | shell/RF/battery gates |
| Rechargeable ball | REJECT V1 | no charging infrastructure | <2-year life or business case |
| Wireless charging rack | REJECT V1 | no production dependency | mechanical/FTO gate |
| Gateway | CHANGE | Zone Gateway per ~2–3 holes | 2–3-hole pilot |
| ESP32-S3 Gateway | DEFER/EVT | acceptable pilot candidate | deterministic/security test |
| RS-485 | KEEP | protected local field bus | wiring/fault test |
| CAN | DEFER | subsystem alternative | machinery need |
| PoE | KEEP | Gateway/display/network endpoints | site power plan |
| Ethernet | KEEP | venue authoritative backbone | none unless site dictates fibre |
| Fibre | DEFER | surge/distance isolation only | site survey |
| Edge PC | KEEP | local authority and research compute | venue-load/resource test |
| Modular monolith | KEEP | initial software topology | independent split trigger |
| Camera GT | KEEP | research/calibration/replay | none for production XY |
| Camera production XY | REJECT V1 | no runtime dependency | special future product |
| Tee sensor | KEEP | arming authority | fallback validation |
| Cup sensor | KEEP | scoring-critical authority | long-term alternate evidence proof |
| Feature sensors | CHANGE | physical for narrow critical gates; geometry for broad zones | per-feature policy |
| Robust multilateration | KEEP/reposition | initialization/static/reacquisition | algorithm comparison |
| Range-domain EKF | CHANGE/KEEP | primary dynamic tracker | dynamic GT tests |
| IMM | DEFER | add only on measured benefit | ablation |
| ML | DEFER/constrain | bias/variance/NLOS only | physics-baseline improvement |
| End-to-end AI score/XY | REJECT V1 | no opaque authority | major architecture review |
| UWB | DEFER | benchmark/fallback | CS decision gate |
| PAwR/connectionless CS | DEFER — research | scalability experiment | standard/product maturity |
| Cloud | KEEP — non-authoritative | booking/history/fleet/release | local operation remains mandatory |
| Hole-specific movement signature | REJECT production / KEEP research | isolated benchmark | claims-based FTO |
| Generic motion states | KEEP | hole-independent physical context | classifier gates |
