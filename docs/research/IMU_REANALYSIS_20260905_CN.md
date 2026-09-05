# PuttTrack Research Ball IMU — 2026-09-05 再整理与算法再分析

**基线：** `main@c97f1b35c64a34afb67aeaf00a08ab93278d65cd`  
**状态：** research-only，`authority=false`，不修改冻结 Pickup V0 的历史结果。

## 1. 当前结论

目前更适合 PuttTrack 的方向不是直接换成更大的神经网络，也不是继续堆全局阈值，而是：

> **分层物理证据 + 状态/事件双输出 + 在线持续时间/上下文约束。**

现有数据已经足够支持一个真实 nRF54L15 Ball demo，并且支持继续验证以下候选：

- `STATIONARY`
- `ACTIVE_PENDING`
- `ROLLING_CANDIDATE`
- `CARRIED_CANDIDATE / PICKUP_FROM_REST`
- `ACTIVE_UNKNOWN`
- `UNKNOWN_QUALITY`

完整的 `ROLLING_PICKUP`、`SLOWING/SETTLING`、impact 来源分类、carried 静止保持仍属于后续验证范围。

## 2. 数据重新整理

仓库现有资料表明：历史归档包含 **161 个唯一 capture、113,867 条 tag_motion**；其中正式滚筒数据已经包含在 161 条内，不能再次累加。旧的 `imu_data_20250306_161150.csv` 不属于已接受的 PuttTrack Research Ball 数据源，不应混入当前训练。

后续 precision 数据共 **72 条回合**：

| 场景 | captures | 冻结 stationary-start V0 适用 | 明确判断 | UNKNOWN |
|---|---:|---:|---:|---:|
| 不离地触碰/旋转/滑动 | 10 | 10 | 10 | 0 |
| 滚动中捡起 | 10 | 0 | 0 | 不适用 |
| 拿起/携带/轻放 | 10 | 10 | 10 | 0 |
| 拿起后低高度放落 | 10 | 10 | 10 | 0 |
| 轻推 | 11 | 10 | 1 | 9 |
| 推球撞栏 | 10 | 10 | 0 | 10 |
| 过台阶/落差 | 11 | 10 | 10 | 0 |
| **合计** | **72** | **60** | **41** | **19** |

冻结 V0 在 60 条适用回合中为 TP=20、TN=21、FP=0、FN=0，但 19 条保持 UNKNOWN，因此真正应关注的是 **68.3% 的明确覆盖率**，而不是把 41/41 写成全场景 100% accuracy。

## 3. 本轮最直接的新改进：饱和数据仍保留下界信息

冻结 Pickup V0 的三个必要条件为：

```text
positive_vertical_impulse > 0.5 m/s
mean_gyro_norm            < 10 rad/s
gyro_axis_consistency     < 0.75
```

当前 clipping 边界为 `34.208453 rad/s`。设 1 s 特征窗口中有 `N` 个采样，其中 `k` 个采样至少一轴达到 clipping 边界，则无需恢复真实峰值就可得到：

```text
mean_gyro_norm >= (k / N) * 34.208453 rad/s
```

如果这个下界已经 `>= 10 rad/s`，则可以确定冻结规则中的 `mean_gyro_norm < 10` 不可能成立。

重要语义：这只表示 **当前 stationary-start pickup 规则被下界否决**。它不等价于 `ROLLING`，也不证明物理上“不可能被拿起”。快速旋转着拿起球仍然可能超过该阈值。因此推荐输出语义是：

```text
PICKUP_RULE_REJECTED_BY_BOUND
```

而不是 `NOT_PHYSICAL_PICKUP`、`VALID_STROKE` 或任何计分事件。

### 回顾性结果

对 19 条原本因 gyro clipping 为 UNKNOWN 的适用回合使用保存的 clip/sample 计数：

| 指标 | 冻结 V0 | 下界扩展（同一批已看过数据） |
|---|---:|---:|
| 适用回合 | 60 | 60 |
| pickup 正判断 | 20 | 20 |
| pickup 规则负判断 | 21 | **32** |
| UNKNOWN | 19 | **8** |
| 明确规则覆盖率 | **68.3%** | **86.7%** |
| 与现有回合标签不一致的明确判断 | 0 | 0 |

新增 11 条规则负判断由 **9 条轻推 + 2 条撞栏**组成；剩余 8 条撞栏仍保持 UNKNOWN。

这是一项**回顾性 coverage 改进**，不是新的盲测，也不是“86.7% 全状态识别准确率”。旧 V0 配置和报告保持冻结。

机器可读结果见：

- `docs/research/imu_reanalysis_20260905/clipping_bound_episode_results.csv`

MCU 可复用原语见：

- `firmware/nrf54l15_tag_app/src/pickup_rule_bound.h`

## 4. 分类器再比较

使用当前保存的三项特征：

- positive vertical impulse
- 1 s mean gyro norm
- 1 s gyro axis consistency

在 41 条未饱和、可明确判定的 precision 子集上，逐回合 LOEO 会出现几乎完美的结果；但整类动作留出后明显下降：

| 模型 | 41 条逐回合 LOEO F1 | 41 条 leave-scenario-out F1 |
|---|---:|---:|
| Logistic | 1.000 | 0.818 |
| Linear SVM | 1.000 | 0.837 |
| RBF SVM | 1.000 | 0.837 |
| depth-2 tree | 0.976 | 0.816 |
| RF-200 | 1.000 | 0.844 |

这说明当前瓶颈主要不是“模型还不够复杂”，而是：

1. 动作族覆盖不足；
2. 同日/同球/同操作者相关性；
3. 饱和、窗口完整性和特征质量；
4. 缺少完整连续状态真值；
5. rolling pickup / collision / settling 等困难路径样本太少。

因此当前 MCU production candidate 仍应优先保持**物理约束 + 小模型边界判断**。RF/Extra-Trees/RBF-SVM 可以继续作为 Edge challenger，但不因局部 F1 更高就替换可审计的 MCU 路径。

机器可读结果见：

- `docs/research/imu_reanalysis_20260905/model_comparison.csv`

## 5. 识别架构建议

```text
ADXL367 motion wake / low-power guard
        ↓
BMI270 active FIFO / event capture
        ↓
quality + continuity + clipping semantics
        ↓
physics evidence bank
  exact / lower-bound / unavailable / unreliable
        ↓
state evidence + transient event evidence
        ↓
small state-specific classifier where needed
        ↓
online dwell / hysteresis / context memory
        ↓
MotionEvidence (authority=false)
        ↓
Venue / tee / cup / feature context
        ↓
Gameplay authority
```

持续状态和瞬态事件应分开。例如球可以保持 `ROLLING`，同时发生 `COLLISION_CANDIDATE`。

对于 carried 状态还应保留“支撑/持有上下文”。球在手里不动与球放在地面不动都可能接近 1 g、零角速度，因此不能只因短时间安静就自动把 `CARRIED` 变回“地面静止”。

## 6. 现在最该做的物理 Ball 测试

本 PR 的 MCU Motion Demo V0 可以直接用于 Research Ball 测试，但必须保持 `candidate_only`。

优先测试以下顺序：

1. **Stationary：** 不同球姿、静止 20–30 s，确认不会自己进入 pickup/rolling。
2. **普通 pickup from rest：** 正常、慢速、快速各至少 10 次。
3. **no-lift handling：** 触碰、原地旋转、地面滑动，不允许产生 pickup event。
4. **gentle / normal putt：** 查看 `ROLLING_CANDIDATE`、clip/UNKNOWN 和恢复过程。
5. **rail collision / step：** 不要求当前版本强行给出 collision subtype；重点看是否错误发 pickup。
6. **rolling pickup：** 记录完整流，但当前仍属于 HOLD；不要用旧 stationary-start 规则判成功。
7. **carried then still：** 拿起后手持不动，再轻放，检查状态机是否过早回到 ground stationary。
8. **反例：** 快速旋转着拿起；非常慢、尽量不转的直线提起。这两项分别挑战 gyro 和 impulse 假设。

每次测试都保存原始 IMU、sequence/time、clip counters、状态转移和观察到的真实动作；尽量同步视频或至少人工按时刻记录。

## 7. 什么时候才应该换 IMU

**不要现在因为仍有 UNKNOWN 就直接换 IMU。** 先用现有 Nordic Research Ball 把失败原因分清。

如果误差主要来自：

- 标注不足、动作覆盖不足、状态机/特征逻辑问题 → **先改算法/数据，不换 IMU**；
- BLE/采样链路、时间戳、FIFO/同步问题 → **先修固件/采集链路**；
- gyro 经常物理饱和，且需要恢复真实高速旋转值 → 下一版 PCB 应提高 **gyro 量程/带宽/ODR**；
- impact/collision 的瞬态被 50 Hz 和当前加速度量程压平或饱和 → 下一版 PCB 应增加/选择更合适的 **高带宽、高动态范围 accelerometer path**；
- 噪声、偏置、温漂导致低速 rolling/settling 分不开 → 优先选低噪声、更稳定的 IMU，并重新验证功耗；
- 现有传感器已经能稳定提供所需状态证据 → **不应为了“规格更高”而换芯片**。

最终 PCB 选型应按测得的 failure budget 决定，而不是先找一颗“更贵/更强”的 IMU。

## 8. 当前 GO / HOLD

### GO

- 继续用现有 nRF54L15 Research Ball 做真实物理测试；
- 使用 PR #25 MCU Motion Demo V0；
- 保留 frozen pickup V0；
- 加入独立的 clipping lower-bound research primitive；
- 记录 UNKNOWN 原因，而不是把 UNKNOWN 算成 negative；
- 重点采集反例和连续混合动作。

### HOLD

- rolling-pickup 产品确认；
- impact vs rail/ball contact 的来源分类；
- slowing/settling 商业状态；
- tiny CNN/TCN；
- IMU-only scoring/cup authority；
- 在没有独立多日、多操作者、多 Ball 验证前声称 Puttshack-equivalent accuracy。

## 9. 最终判断

现有 IMU 数据**已经可以用来做下一轮真实 Ball demo**。当前最合理的路径是先用真实测试回答“现有传感器能不能稳定提供足够的物理证据”。

如果能，就继续优化算法并沿用该传感器路线；如果不能，再依据实际失败模式为自研 PCB 选择更合适的 gyro/accelerometer/IMU 组合。

因此硬件决策顺序应固定为：

```text
现有 Ball 实测
→ 量化失败模式
→ 判断是算法/数据问题还是传感器物理极限
→ 只有确认是物理极限时才升级 IMU / accelerometer
→ 用同一套测试矩阵复测新 PCB
```
