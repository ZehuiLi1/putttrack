# PuttTrack Research Ball MCU Motion Demo V0 — 决策与结论

**日期：** 2026-09-05  
**分支：** `demo/mcu-motion-state-v0-20260905`  
**目标固件：** `nrf54l15_tag_app` 0.1.18  
**目标硬件：** Nordic nRF54L15 Tag / PCA20072 Research Ball  
**权威边界：** `authority=false`，Ball 端只输出 generic motion evidence，不得修改杆数、分数、球道状态或处罚。

## 1. 结论先行

当前已经收集的 IMU 数据**足够做一个真实 MCU 小 Demo**，但还不足以把一个“十状态通用 AI 分类器”作为产品算法固化进 Ball。

当前最合理的工程决策是：

> **先把已被当前真实数据支持的物理特征 + 小型状态机写入 nRF54L15，做一个可回放、可 OTA、可现场观察、fail-closed 的 Demo V0。**

第一版 Demo 只需要可靠展示：

- `STATIONARY`；
- `PICKUP_FROM_REST` / `CARRIED_CANDIDATE`；
- `ROLLING_CANDIDATE`；
- `ACTIVE_UNKNOWN`；
- `UNKNOWN_QUALITY`。

明确暂不把以下状态固化成确认事件：

- rolling pickup；
- putter impact vs rail / ball collision；
- track step / bounce source；
- cup entry / cup rest；
- authoritative stroke / score mutation。

## 2. 为什么现在可以直接上 MCU Demo

当前冻结的 stationary-start pickup V0 已经有可复现的 raw-source replay，并且 C 版本已经直接用 repository 中的真实 JSONL 做 streaming replay。

当前 Demo C replay 覆盖 72 个 reviewed precision episodes：

| 检查 | 结果 |
|---|---:|
| stationary-start pickup positive episodes | 20 |
| `PICKUP_FROM_REST` events detected | 20 |
| other / unsupported-path episodes | 52 |
| false `PICKUP_FROM_REST` events | 0 |
| gentle-putt + rolling-pickup display scope | 21 |
| observed `ROLLING_CANDIDATE` | 21 |
| episodes that visited `UNKNOWN_QUALITY` | 8 |
| C motion-state context | 6,232 bytes |

这组结果说明：

1. 当前冻结 Path A 可以被移植为流式 C，而没有在现有 reviewed 数据上立即产生 pickup false positive；
2. gentle putt 和 rolling-pickup 都能出现 sustained dominant-axis rotation，因此 `ROLLING_CANDIDATE` 适合作为展示状态；
3. clipping / timing / unsupported evidence 可以安全落到 `UNKNOWN_QUALITY`；
4. MCU RAM 负担很小，不需要在 Ball 上保存完整训练集或运行大型神经网络。

这些仍然是**同日、同操作者、同一 Ball/core 为主的研究证据**，不能称为商业准确率。

## 3. MCU Demo V0 的推荐算法

### 3.1 Stationary eligibility

使用动作前紧邻的一段稳定窗口作为运行时 baseline：

- 至少 40 个样本；
- 至少 0.9 秒；
- acceleration norm standard deviation `<= 0.15 m/s²`；
- gyro RMS `<= 0.08 rad/s`。

连续运行时没有实验 GO marker，因此 Demo 使用“动作前紧邻的一秒合格静止窗”代替 pre-GO baseline。**Pickup 决策阈值本身不重新调参。**

### 3.2 Motion onset

10 个连续样本中至少 6 个满足任一条件：

- `|acceleration norm - g| >= 0.5 m/s²`；
- `gyro norm >= 0.25 rad/s`。

### 3.3 Frozen pickup-from-rest rule

确认 `PICKUP_FROM_REST` 需要同时满足：

- 约 0.6 秒 positive vertical impulse `> 0.5 m/s`；
- onset 后 1 秒 mean gyro norm `< 10 rad/s`；
- onset 后 1 秒 gyro-axis consistency `< 0.75`；
- 必需 feature window 内不能有 BMI270 gyro clipping；
- sensor / sequence / timestamp / timing quality 必须有效。

Frozen detector config canonical SHA-256：

```text
62c82c1a313f70912a5bb6c2f53c635fe179c537cdb3738dbc5d2a347050c8ad
```

### 3.4 Rolling display candidate

作为**展示候选状态**而非权威语义：

初始约 1 秒：

- mean gyro norm `>= 8 rad/s`；
- axis consistency `>= 0.90`。

后续 tracking：

- mean gyro norm `>= 2 rad/s`；
- axis consistency `>= 0.85`。

该规则只表示“持续主轴一致旋转”，不能被解释为 stroke、速度、碰撞来源或 rolling-pickup confirmation。

## 4. 推荐状态机

```text
BOOTSTRAP
    ↓
STATIONARY
    ↓
ACTIVE_PENDING
    ├─ frozen pickup rule pass → CARRIED_CANDIDATE + PICKUP_FROM_REST event
    ├─ dominant-axis rotation → ROLLING_CANDIDATE
    ├─ unsupported / ambiguous → ACTIVE_UNKNOWN
    └─ invalid / clipped / timing fault → UNKNOWN_QUALITY
    ↓
qualified quiet dwell
    ↓
STATIONARY
```

`PICKUP_FROM_REST` 只允许从合格的 `STATIONARY` 前状态产生。滚球后拿起当前必须保持未支持，不能复用 stationary-start detector 冒充确认结果。

## 5. 为什么暂时不用神经网络作为 Demo 核心

现有全量分析已经表明：

- no-lift handling 与 pickup 在低速、多轴 gyro 特征上存在重叠；
- rail collision、step/drop、putt 会产生很大的 acceleration / jerk，单一峰值不能代表 pickup；
- rolling disruption 也会由 rail / step 触发，所以 `ROLLING -> disruption` 不能直接等于 rolling pickup；
- 现有数据的 session / operator / Ball / surface diversity 仍然不足以证明 tiny CNN/TCN 的真实跨条件泛化。

因此第一版 MCU 的正确职责是：

> **运行可解释、可审计、能 fail closed 的 physics/FSM baseline，同时继续保留 raw BMI270 evidence，后续再让 Edge/研究工具挑战它。**

## 6. 现场 Demo 验收建议

烧入 0.1.18 test image 后，先不要立即 confirm。

按以下顺序测试，每个动作前让球静止至少 2 秒：

1. 静止：应稳定进入 `STATIONARY`；
2. 从静止拿起并携带 5 次：5/5 应增加 pickup event count；
3. touch / rotate / slide 各 5 次但不离地：15 次中 0 次 pickup event；
4. gentle putt 5 次：应看到 `ROLLING_CANDIDATE` 或明确 `UNKNOWN_QUALITY`，0 次 pickup event；
5. rail collision 5 次：允许 rolling / active unknown / quality unknown，0 次 pickup event；
6. rolling pickup 5 次：允许先出现 rolling，然后 unknown / stationary；当前版本不得声称确认 rolling pickup；
7. watcher 退出后 Ball 必须恢复 `auto` power policy；
8. sensor health、sequence continuity、battery / advertising / OTA 行为不能回归。

只有以上 gate 同时满足，才考虑 `image-confirm`。失败时保留 test logs 并让 MCUboot rollback，**不要通过当天现场调低阈值来“修好演示”。**

## 7. 当前 Go / Hold / Reject

| 项目 | 决策 |
|---|---|
| 把 frozen stationary-start pickup 写入 MCU Demo | **GO** |
| MCU 输出 `STATIONARY` / `ROLLING_CANDIDATE` / pickup candidate / unknown | **GO** |
| 保留 raw BMI270 和 quality/clipping evidence | **GO** |
| 通过 BLE/mcumgr 展示 Demo snapshot | **GO** |
| 实体 Ball test-boot | **下一步最高优先级** |
| 自动 rolling-pickup confirmation | **HOLD** |
| slowing / settling 的产品化状态 | **HOLD** |
| putter / rail / ball-ball collision source classifier at 50 Hz | **HOLD / insufficient evidence** |
| tiny CNN / TCN on Ball | **HOLD** |
| IMU-only cup confirmation | **REJECT** |
| Ball 直接改 score / stroke | **REJECT** |
| UNKNOWN 强行转成 NOT_PICKUP | **REJECT** |

## 8. Demo 成功后的开发顺序

实体 Demo 通过后，不应马上增加更多状态。建议顺序：

1. 先冻结 MCU Demo V0 的现场行为；
2. 收集第二天 / 第二操作者 / 第二 Ball / 明确 surface 的 blind holdout；
3. 给 rolling pickup 增加独立 hand-contact / lift timestamp；
4. 给 clean roll / putt 增加 full-stop timestamp，建立 `ROLLING -> SLOWING -> STATIONARY`；
5. 再建立新的 rolling-pickup detector ID；
6. 之后比较 FSM / Logistic emission / HSMM / tiny causal TCN；
7. 最终由 physical Tee/Cup/feature sensor 与 Venue Edge 做 evidence fusion，Gameplay Engine 保持唯一计分权威。

## 9. 当前工程状态

`demo/mcu-motion-state-v0-20260905` 已包含：

- `motion_demo_v0.c/.h` MCU streaming state machine；
- encrypted mcumgr group 64 command 24 Demo snapshot；
- watcher；
- C raw-JSONL replay harness；
- replay regression tests；
- machine-readable Demo config；
- NCS target build workflow；
- 现场 test-boot / OTA 说明。

当前 GitHub `NCS Tag Motion Demo Build` 已在该分支成功完成，说明 source-level nRF54L15 target build 已通过。下一步真正需要的是**在实体 Research Ball 上做 MCUboot test upgrade + 现场动作 Demo**。

## 10. 最终一句话决策

> **现在不要继续等更多数据才开始 MCU。当前数据已经足够做一个有意义的小 Demo：先把 frozen pickup-from-rest + conservative rolling candidate + UNKNOWN 写进 nRF54L15，验证“球真的能自己理解一部分运动状态”；实体 Demo 通过后，再用新的独立数据逐步扩展 rolling pickup、settling 和 impact。**
