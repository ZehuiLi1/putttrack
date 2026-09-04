# PuttTrack Research Ball IMU 全状态算法发现：独立复核与最终收敛

**日期：** 2026-09-04  
**复核基线：** `c97f1b35c64a34afb67aeaf00a08ab93278d65cd`  
**实现分支：** `research/full-imu-state-recognition-20260904`  
**权威边界：** `authority=false`；Ball IMU 只提供 generic motion evidence

## 1. 复核结论

当前最合理的完整识别架构是：

> **Physics-Guided Dual-Head Hidden Semi-Markov Recognizer（PG-DH-HSMM）**

但这个名称不能被理解成“当前已经训练并验证出一个商业化 HSMM”。现阶段真正得到数据支持的是一个分层结构：

```text
ADXL367 low-power wake
    -> BMI270 retained event window
    -> source identity / sequence / time / validity / clipping gate
    -> causal multi-scale physical features
    -> persistent-state emission head
    -> transient-event head
    -> explicit-duration FSM / HSMM decoding
    -> confidence + first-class UNKNOWN
    -> generic motion evidence
    -> Tee / Cup / feature / Ball identity / active-hole context fusion
    -> Gameplay Engine
```

当前应先用可解释的规则和 FSM 实现这个结构。Regularized Logistic 是第一候选 emission model；tiny causal TCN 只有在新的跨日、跨操作者、跨球、带 frame-level transition truth 的数据上显著优于它时才进入部署候选。

## 2. 全量数据计数如何解释

对 archive 与当前 `experiments/research_ball*` 按原始 JSONL SHA-256 去重后：

- **236 个唯一捕获文件**，其中包括 3 个自动拒绝后保留的 diagnostic captures；
- **233 个可进入 discovery parser 的唯一 episode**；
- **168,142 条 `tag_motion` 记录**；
- 约 **56.2 分钟**；
- BMI270 accelerometer clipping：**0 个文件**；
- ADXL367 与 BMI270 gyro clipping 在真实滚动、碰撞和 step 数据中很常见。

因此 `236` 与 discovery audit 的 `233` 并不冲突：前者把 rejected diagnostics 也作为数据治理证据计入，后者是用于状态发现的 episode 数。

当前语义数据仍基本来自：

- 同一天；
- 同一颗 Research Ball / core / shell；
- 一个已知 operator，另有大量旧 archive metadata 为 unknown；
- surface、初始姿态和真实 transition timestamp 经常未记录。

所以目前可以讨论 same-day prospective engineering evidence，不能讨论跨场地或商业化泛化精度。

## 3. 冻结 V0 边界修正

`configs/research/pickup_detector_v0.json` 在 holdout 采集前已经冻结。后续执行所需的 stationary baseline coverage、数值 clipping boundary 和 source-rate tolerance 不应追加回冻结 detector 文件。

本分支做两件事：

1. 将 `pickup_detector_v0.json` 恢复为冻结时的原始内容；
2. 将执行元数据放在 `pickup_detector_v0_eval_profile.json`。

冻结 detector 的 canonical JSON SHA-256 为：

```text
7add18c4c4a23df0f26674a020f2d0ab78cae7de041467e7db71655aa27b000d
```

执行 profile 中的 `0.15 m/s²` stationary accel-norm standard deviation 和 `0.08 rad/s` gyro RMS 来自冻结前已存在的 `ProvisionalStationaryThresholds` 默认值。它们用于判断输入是否满足 V0 的 stationary-start 前提，不是看过 holdout 后新增的 pickup decision threshold。

## 4. Stationary-start Pickup Path A

冻结规则保持：

```text
positive vertical impulse over about 0.6 s > 0.5 m/s
AND one-second mean gyro norm < 10 rad/s
AND one-second gyro-axis consistency < 0.75
```

### 4.1 Prospective clean set

去掉 rolling-pickup unsupported path、invalid 和 mixed episodes 后，当前 clean prospective set 包含：

- 20 个 stationary-start pickup positives：10 pickup/carry + 10 pickup/drop；
- 40 个 negatives：10 no-lift handling + 11 gentle putt + 10 rail collision + 9 clean original step controls；
- 另有 clean step replacement 作为附加 hard negative；
- mixed step-plus-obstacle 和 rejected diagnostics 不进入 clean metric。

独立复算结果：

```text
positive: 20 PICKUP / 0 NOT_PICKUP / 0 UNKNOWN
negative: 0 PICKUP / 21 NOT_PICKUP / 19 UNKNOWN
```

因此：

- observed pickup recall：20/20；
- observed false-pickup output：0/40；
- decision coverage：41/60；
- 19 个 UNKNOWN 主要来自 gentle-putt / rail 的 gyro clipping；
- 20/20 的双侧 95% Clopper-Pearson recall lower bound 约 0.832；
- 0/40 的双侧 95% false-pickup upper bound 约 0.088。

正确表述是：

> Frozen Path A 已出现同日 prospective engineering evidence；它尚未达到商业精度证明，且当前保守性通过大量 UNKNOWN 换取了零观察到的 false-pickup output。

### 4.2 Physics gate 与纯 ML

将冻结前保存的 22-episode 三特征 development ledger 用作固定训练集，再一次性测试后采 62 episodes，多个 Logistic/SVM/Tree/Forest 模型仍产生 false pickup。独立复核中最佳纯 ML 结果约为：

```text
20 TP / 7 FP / 0 FN
precision about 0.741
F1 about 0.851
```

主要原因是 no-lift handling 的低速、多轴 gyro shape 与 pickup 有重叠。没有“真实离地/向上运动”的必要物理条件时，模型容易把手摸、原地转动或短距离滑动学成 pickup。

结论：

> Path A 应采用 physics-gated detector + FSM。ML 只能处理已经通过必要物理条件的 ambiguous candidates，不能替代 leave-ground gate。

## 5. Rolling Pickup Path B

Stationary-start V0 不适用于 rolling pickup。rolling pickup 的第一个 onset 是推球/滚动，而不是后来的手部拿起。

正确问题是：

```text
ROLLING
    -> DISRUPTION
    -> POST_TRANSITION CONTEXT
    -> {ROLLING_RESTORED, SETTLING, COLLISION/STEP, CARRIED, UNKNOWN}
```

### 5.1 Disruption-only 规则被否定

在当前数据中，先确认 sustained dominant-axis rolling，再寻找 axis collapse + acceleration disturbance：

- rolling pickup：10/10 出现 disruption candidate；
- rail/step/clean-roll negatives：也有多个出现；
- disruption-only 在当前 Path-B set 中产生 6/35 false positives。

所以以下等式必须明确 REJECT：

```text
rolling model departure != rolling pickup
```

### 5.2 Post-transition persistence 是当前最强候选

当前 post-hoc 对齐显示，disruption 后约 2 秒内：

- rolling pickup 的 irregular hand-motion window fraction 中位数约 **0.875**；
- rail collision 约 **0.25**；
- clean step 约 **0**。

一个便于下一轮冻结前讨论的 hypothesis 是：

```text
ROLLING confirmed
 -> disruption candidate
 -> observe about 2 s
 -> low quiet-window fraction
 -> at least about 0.4 s persistent irregular non-rolling motion
 -> rolling-pickup candidate
```

它在定义它的同一批数据上得到 10/10 positives 和 0/35 negatives，但这不是 validation，因为：

- pickup transition 没有独立 marker 或视频 timestamp；
- disruption time 由同一 IMU 数据推断；
- threshold 是看过相同 episodes 后提出；
- 没有新的 operator、Ball、surface group。

Path B 必须保留为 HOLD，并以新的 detector ID 进入下一轮 untouched timestamped holdout。

## 6. Flat multiclass 为什么不能成为最终产品模型

当前 whole-episode multiclass competition 可以获得较高 macro-F1，但一个 episode 并不等于一个 state：

- pickup episode 包含 stationary、lift、carry、placement；
- putt episode 包含 impact、rolling、slowing、stationary；
- rolling-pickup episode 包含 rolling 与 pickup/carry；
- rail/step episode 包含 rolling、disruption、impact 和 settling。

此外，当前 class 与 session 高度绑定。即使没有随机切相邻窗口，episode-level cross-validation 仍可能学习 session、动作长度和采集流程。

因此 flat classifier 的作用仅是证明“数据中存在结构”，不能把其 macro-F1 宣称为 Ball state accuracy。

## 7. HMM / HSMM 的正确用法

无监督 Gaussian HMM 能发现近静止、持续滚动、中等手持运动和高能 transient 等 latent regimes，但没有 frame truth 时不能把 latent state 命名为 stroke、cup 或 collision。

HSMM 的价值是：

- 显式 dwell duration；
- 对短瞬态与持久状态分开建模；
- 把物理不可能的 transition 设为不可达；
- 在证据不足时进入 UNKNOWN；
- 同时输出 persistent state 与 transient candidate。

建议的 persistent states：

```text
STATIONARY
ROLLING
SLOWING / SETTLING
CARRIED
AIRBORNE
UNKNOWN
```

建议的 transient heads：

```text
MOTION_ONSET
IMPACT_CANDIDATE
PICKUP_TRANSITION
ROLLING_PICKUP_CANDIDATE
COLLISION_OR_STEP_CANDIDATE
DROP_LANDING_CANDIDATE
```

## 8. 当前各状态的 Go / Hold / Reject

| 状态/能力 | 决策 | 当前最合理方法 |
|---|---|---|
| STATIONARY | GO research | low accel/gyro + dwell/hysteresis |
| ACTIVE_MOTION | GO research | broad activity gate；无语义权威 |
| ROLLING candidate | CONDITIONAL GO | sustained gyro + dominant-axis coherence；clipping-aware |
| STATIONARY PICKUP | GO research / HOLD product | frozen physics Path A + UNKNOWN |
| CARRIED | HOLD | pickup 后 persistent non-rolling multi-axis state |
| SLOWING / SETTLING | HOLD | angular decay + explicit dwell；缺 timestamp truth |
| ROLLING PICKUP | HOLD | rolling -> disruption -> post-transition context |
| IMPACT candidate | CONDITIONAL GO | high-pass accel/jerk energy |
| PUTTER vs WALL/BALL IMPACT | REJECT at 50 Hz | 需要 high-rate transient + venue context |
| COLLISION / STEP / DROP | HOLD | transient + post-state；当前只够 generic candidate |
| CUP ENTRY / SCORE | REJECT IMU-only | physical cup/feature sensor + identity + context |
| UNKNOWN | REQUIRED | clipping、健康、unsupported path、低 confidence 时 fail closed |

## 9. 采样率与传感器结论

当前约 50 Hz 对 stationary、rolling envelope、pickup/carry persistence 和粗略 settling 有价值，但对极短 impact waveform、impact source 和准确 timestamp 不够。

建议：

1. general active-state capture：200 Hz；
2. rolling/temporal study：200–400 Hz；
3. impact campaign：BMI270 accelerometer 0.8–1.6 kHz FIFO/burst，gyro 200–400 Hz 起步；
4. 保留 1–1.5 s pre-trigger 和至少 4 s post-trigger；
5. 先在高 ODR 下重新测 BMI270 accel saturation，再决定是否增加 high-g accelerometer。

当前全部数据没有 BMI270 accelerometer clipping，因此现阶段没有实测证据要求立刻增加 high-g sensor。ADXL367 继续作为 low-power wake，不作为激烈动态幅值真值。

## 10. Ball / Edge 分工

### Ball side

- ADXL367 wake；
- BMI270 ring buffer / FIFO；
- timestamps、sequence、validity、clipping；
- lightweight norm、dwell、axis-coherence features；
- broad motion/impact candidates；
- frozen Path A 可在资源测量后下沉。

### Edge side

- multi-scale feature inference；
- HSMM / richer FSM；
- state-specific Logistic heads；
- confidence calibration；
- model/version management；
- Ball/player/hole context；
- tee/cup/feature evidence fusion；
- operator review and audit。

nRF54L15 的计算和存储资源足以容纳 FSM、固定点特征和小型线性模型；是否下沉由实测 CPU、RAM、event latency 和 energy gain 决定，而不是“能装下就装”。

## 11. 下一轮最低充分实验

优先顺序：

1. 另一天、至少第二位 operator、最好第二颗 Ball/core 的 30 次 pickup/carry/drop；
2. 同组条件下 30 次 strict no-lift handling；
3. 30 次带真实 impact 和 full-stop timestamp 的 clean putt/free-roll；
4. 30 次带真实 hand-contact/lift timestamp 的 rolling pickup；
5. 30 次带 collision/step timestamp 的 rail/step controls；
6. ball-ball、cup-lip/bounce hard negatives；
7. high-rate impact burst campaign；
8. physical cup sensor + Ball identity 的 cup fusion campaign。

若 0 次 observed false positive 的双侧 95% upper bound 需要低于 1%，至少需要约 368 个独立负 episodes；低于 0.1% 需要约 3,688 个。商业化验证最终必须按独立回合和 venue-hours 统计，不能靠重叠窗口扩大样本数。

## 12. 最终建议

**采用 PG-DH-HSMM 作为研究架构名称和实现方向，但当前先实现 physics-guided hierarchical FSM + Logistic heads。**

- Path A：继续冻结验证；
- Path B：建立新的 timestamped holdout 后再冻结；
- tiny TCN：只在跨组 holdout 明显改善 residual ambiguity 后比较；
- impact source：先提高采样率；
- cup/stroke/feature score：必须外部证据融合；
- `UNKNOWN`：始终保留。

本分支不合并任何商业精度声明，不给 IMU 计分权威，也不修改冻结 V0 决策定义。
