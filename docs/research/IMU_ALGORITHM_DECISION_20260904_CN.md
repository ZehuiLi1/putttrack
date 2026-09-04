# PuttTrack Research Ball IMU 状态识别算法决策 — 2026-09-04

**基线仓库：** `ZehuiLi1/putttrack`  
**基线 HEAD：** `bf31248618f3494381935d93dbc79c9f7d81712e`  
**实现分支：** `research/imu-pg-dh-hsmm-v1-20260904`  
**状态：** 研究架构收敛；没有商业精度声明；`authority=false`

## 1. 决策

当前最适合 PuttTrack 的完整 IMU 状态识别路线不是单一阈值、Random
Forest、LSTM 或端到端神经网络，而是：

> **Physics-Guided Dual-Head Hidden Semi-Markov Recognizer**  
> **物理引导、双输出头、显式时长半马尔可夫状态识别器（PG-DH-HSMM）**

推荐链路：

```text
ADXL367 low-power wake
    -> BMI270 active window
    -> identity / sequence / time / validity / clipping quality gate
    -> causal multi-scale physics features
    -> regularized Logistic persistent-state emission head
    -> regularized Logistic transient-event heads
    -> explicit-duration HSMM / Viterbi
    -> calibrated confidence + first-class UNKNOWN
    -> generic motion evidence
    -> Tee / Cup / hole context / future spatial evidence fusion
    -> Gameplay Engine
```

Ball/Edge 只提供 generic motion evidence，不直接改变杆数、分数或整局状态。

## 2. 当前数据支持的结论

第一批 canonical archive 包含 161 个唯一 raw JSONL capture 和 113,867 条
`tag_motion`。随后已经版本化的关键 Research Ball 数据还包括：

- 10 次 strict no-lift handling；
- 10 次 rolling pickup；
- 10 次 stationary-start pickup/carry/gentle placement；
- 10 次 pickup/carry/low-height drop；
- 11 次 gentle putt；
- 10 次 rail collision；
- 11 次 course-step run；
- 86 次 programmable-roller characterization；
- 更早的 stationary、manual roll、pickup/carry、repeated taps 和 nominal putt。

这些数据足以选择架构、实现 frozen evaluator、发现硬阈值问题，但仍不足以
声称产品精度。主要缺口仍包括：不同日期、不同操作者、第二颗 Ball、不同
surface、逐段/逐事件独立 timestamp truth，以及真实 Cup truth。

完整历史证据继续以以下目录为准：

```text
docs/research/imu_analysis_20260904/
datasets/putttrack_imu_dataset_20260904.zip
experiments/research_ball_r1_*/
```

## 3. 22-episode baseline 给出的关键信号

仓库保留的三特征 baseline 使用：

```text
positive vertical impulse over ~0.6 s
gyro mean norm over 1 s
gyro axis consistency over 1 s
```

对应的 reproducible Leave-One-Episode-Out Logistic 结果为：

```text
TN = 10
FP = 1
FN = 0
TP = 11
pickup precision = 0.9167
pickup recall    = 1.0000
pickup F1        = 0.9565
```

唯一共同 false positive 是 `restrained-repeated-taps-r01`。Logistic、linear
SVM、RBF SVM 和 small Random Forest 在这组数据上没有产生有意义的差异，
说明当前瓶颈不是增加模型复杂度，而是 negative diversity、时序结构和独立
验证。

当前最强物理信息是：

- 地面滚动通常表现为持续、主轴稳定的旋转；
- 人手 pickup/carry 通常角速度较低且更明显是多轴旋转；
- upward impulse 是支持证据，但 putter/collision 也可以产生很大的加速度；
- gravity reversal 不能单独用于 pickup，因为自由滚动也会改变球体坐标系中的
  重力方向。

新 `pickup_drop` 中已经出现真实 pickup 的 axis consistency 约 `0.7516`，略高
于旧 post-hoc `<0.75` 边界。这证明冻结 V0 应被真实 holdout 挑战，而不是在
看过新数据后简单把阈值改宽。

## 4. 为什么完整系统必须是“双头”

持续状态和瞬态事件不是同一个分类问题。

### Persistent-state head

```text
STATIONARY
ROLLING
SETTLING
CARRIED
AIRBORNE
UNKNOWN
```

### Transient-event head

```text
MOTION_ONSET
IMPACT_CANDIDATE
PICKUP_TRANSITION
ROLLING_PICKUP
COLLISION_OR_STEP_CANDIDATE
DROP_LANDING_CANDIDATE
```

例如一个真实轨迹可以是：

```text
STATIONARY
  -> IMPACT_CANDIDATE
  -> ROLLING
  -> COLLISION_OR_STEP_CANDIDATE
  -> ROLLING
  -> SETTLING
  -> STATIONARY
```

另一个轨迹可以是：

```text
STATIONARY
  -> PICKUP_TRANSITION
  -> CARRIED
  -> AIRBORNE
  -> DROP_LANDING_CANDIDATE
  -> SETTLING / STATIONARY
```

rolling pickup 应作为：

```text
ROLLING
  -> rolling-model departure
  -> PICKUP_TRANSITION
  -> CARRIED
  -> emit ROLLING_PICKUP
```

因此 flat multiclass classifier 不适合最终结构；它会被迫在“正在滚动”和
“发生碰撞”之间二选一。

## 5. 为什么用 Logistic emission + HSMM

### Logistic 适合作为当前 emission model

- 当前小数据下已经和 SVM/RF 同级；
- 输出概率，便于 calibration、margin 和 UNKNOWN；
- 系数方向可解释；
- 容易在 Edge/MCU 上转换为固定点或轻量 C；
- 不需要把当前稀少 episode 扩成大量伪独立窗口。

Logistic 不是完整 recognizer。它只负责把物理 feature frame 映射为状态/事件
概率。

### HSMM 负责状态持续时间与合法转移

普通 HMM 的隐式 duration 分布不适合同时表示：

- 短瞬态 impact；
- 数百毫秒到数秒 rolling；
- 更长时间 carried；
- settling 后稳定 stationary。

显式时长 HSMM 可以把 duration 作为独立物理约束，并使用 Viterbi 消除窗口
级别的抖动和不合法跳转。

当前 `configs/research/hsmm_v1_template.json` 中的 duration/transition 都只是
**unvalidated physical priors**，不是产品参数。

## 6. V1 多时间尺度 feature 设计

推荐 causal windows：

```text
80 ms
200 ms
600 ms
1.0 s
2.0 s
```

### 80–200 ms：短瞬态

- accel norm peak / RMS / p95；
- jerk peak / RMS / p95；
- gyro onset；
- clipping onset/fraction；
- change-point/impulse asymmetry。

### 600 ms：pickup / freefall / landing

- pre-action gravity vector；
- gyro-propagated venue-up；
- positive vertical impulse；
- near-weightless dwell；
- freefall-to-landing pair。

### 1 s：旋转 shape

- gyro mean/RMS/p95/max；
- axis consistency；
- dominant-axis eigenvalue ratio；
- first-half vs second-half axis drift；
- angular-energy decay；
- gyro clipping fraction。

### 1–2 s：rolling coherence

- accelerometer vector autocorrelation；
- rotating-gravity periodicity；
- candidate rotation period；
- dominant-axis stability；
- activity persistence；
- rolling-model departure；
- time-to-still。

86 个 roller capture 的重点价值是帮助建立 clipping-aware rolling model，而
不是只学一个 gyro peak threshold。

## 7. Clipping 策略

冻结 pickup V0 按原设计处理：feature window 内 BMI270 gyro clipping 就返回
`UNKNOWN`，不为了 coverage 修改旧规则。

Full-state V1 不能简单把所有 clipped putt 丢弃，因为现有 gentle putt 和 rail
collision 已经频繁触及 ±2000 dps 边界。V1 应把 clipping 视为 censored
information：

```text
true angular rate >= configured sensor range
```

因此保留：

- clip fraction；
- clip axis pattern；
- time since clip；
- accelerometer periodicity；
- state duration / coherence；

同时降低需要精确 gyro amplitude 的 feature confidence。

## 8. UNKNOWN 必须是一等状态

以下情况不能强行分类为普通 negative：

- missing device-side GO marker；
- pre-GO baseline 不稳定；
- sequence gap / time regression；
- BMI270 invalid / sensor error；
- feature window 不完整；
- frozen V0 feature window clipping；
- model posterior 或 top-two margin 太低；
- unsupported rolling-start pickup path；
- mixed / ambiguous truth。

产品指标必须单独报告 UNKNOWN/coverage，而不是把 UNKNOWN 当成正确的
`NOT_PICKUP`。

## 9. 训练与验证纪律

禁止把 10 秒 episode 的标签复制给每个 20 ms window 后随机切训练/测试。
必须使用独立的 segment/event truth，并按真实 leakage boundary 分组：

```text
day / session
operator
Ball / core / shell
surface
venue geometry
battery / temperature band
```

建议三层冻结：

1. development groups：特征与架构探索；
2. calibration groups：概率 calibration、threshold 和 UNKNOWN policy；
3. prospective product holdout：不用于任何调参，只运行一次。

任何看过 holdout 后发生的 feature/threshold 修改都必须创建新 detector/model
ID，并使用未来新的 untouched holdout。

## 10. 产品指标

不要只报告 accuracy/F1。至少报告：

- per-class precision / recall / F1；
- false pickup per player-hour / per hole；
- false stroke per round；
- rolling-pickup recall；
- collision/step false-pickup；
- stationary false alarm per hour；
- event latency；
- UNKNOWN rate / definitive coverage；
- Brier score / reliability / ECE；
- clipping-conditioned metrics；
- day/operator/Ball/surface subgroup；
- Wilson/bootstrap confidence intervals。

对会自动处罚玩家的事件，优先目标是极低 false positive，而不是追求一个漂亮
平均 accuracy。

## 11. Sampling 建议

当前 50 Hz 对 stationary、sustained rolling、carried、settling、粗 pickup 和
freefall/landing candidate 有研究价值，但不适合作为最终依据解析极短 impact、
wall/putter collision waveform 或高速滚动真实 peak angular rate。

建议未来 active mode：

```text
ADXL367 wake
    -> BMI270 200–400 Hz active streaming/FIFO
    -> 1–2 s pre-trigger
    -> 3–4 s post-trigger
    -> impact vicinity accel burst 800–1600 Hz where practical
    -> stable state -> lower-power mode
```

提高 ODR 改善时间分辨率，但不会扩大 ±2000 dps gyro range，因此 clipping-aware
feature 仍是必要的。

## 12. 本分支实现

```text
src/putttrack/motion/pickup_v0.py
src/putttrack/motion/recognizer_v1.py
configs/research/pickup_detector_v0_eval_profile.json
configs/research/motion_recognizer_v1.json
configs/research/hsmm_v1_template.json
tools/evaluate_pickup_detector.py
tools/train_grouped_logistic_emissions.py
tests/test_pickup_v0.py
tests/test_recognizer_v1.py
```

已有冻结文件保持不变：

```text
configs/research/pickup_detector_v0.json
```

已有 22-episode baseline 和模型复现结果继续使用：

```text
docs/research/imu_analysis_20260904/pickup_binary_research_set.csv
docs/research/imu_analysis_20260904/model_benchmark_reproduced_3f.csv
docs/research/imu_analysis_20260904/model_benchmark_fold_predictions_3f.csv
```

初始分支本地 unit/compile 验证：

```text
10 tests run
10 passed
Python compilation passed
```

这些测试验证代码路径和 fail-closed 行为，不是商业性能验证。

后续 hardening 已扩展到 21 个 pickup/recognizer/trainer 集成针对性测试，并加入
全仓库及 GitHub Actions 门槛。测试数量增加仍不等于产品性能验证。

## 13. 已完成的冻结 V0 实证回放

已经在真实 repository checkout 中对 reviewed manifests 运行冻结 evaluator：

```bash
PYTHONPATH=src python tools/evaluate_pickup_detector.py \
  experiments/research_ball_r1_pickup_precision_1a/manifest.json \
  experiments/research_ball_r1_pickup_precision_1c/manifest.json \
  experiments/research_ball_r1_pickup_precision_1c_drop/manifest.json \
  experiments/research_ball_r1_pickup_precision_1d_gentle/manifest.json \
  experiments/research_ball_r1_pickup_precision_1e_rail/manifest.json \
  experiments/research_ball_r1_pickup_precision_1e_step/manifest.json \
  --output-dir docs/research/imu_analysis_20260904/pickup_v0_holdout_eval
```

结果已保存在
`docs/research/imu_analysis_20260904/pickup_v0_holdout_eval/`，并单独报告
`rolling_pickup` 为 unsupported path，没有错误计入 stationary-start classifier
accuracy。

本次结果：60 个 metric-eligible episode 中 41 个明确判定、19 个 UNKNOWN；
TP=20、TN=21、FP=0、FN=0。这个结果仍受同日、同操作者、同一 Ball 和缺少独立
真值限制，不是产品准确率声明。

后续需要：

1. 检查每个 UNKNOWN，特别是 gyro clipping 的 rail/gentle-putt；
2. V0 失败也不回改 frozen threshold；
3. 只有真实失败模式需要时才建立 V1 detector/model ID；
4. 然后再收集新的 day/operator/second-Ball/surface prospective holdout。

## 14. 最终边界

### 当前可以确认

- 单一硬阈值不是最终商业方案；
- Logistic 适合作为当前 probability emission model；
- 显式时长 HSMM 和合法 transition 对完整状态识别是必要的；
- persistent state 与 transient event 应分开；
- rolling pickup 必须识别 `ROLLING -> CARRIED` transition；
- gyro clipping 必须作为 censored evidence；
- UNKNOWN 必须保持一等输出；
- Ball motion evidence 不能直接成为 Gameplay/scoring authority。

### 当前不能确认

- 任何最终 commercial accuracy 百分比；
- rolling pickup 的逐帧 recall；
- 50 Hz 下可靠细分 putter/rail/step/cup bounce；
- second Ball、different operator/surface/temperature 的泛化。

因此当前最短、最可信的商业化路径是：

```text
frozen raw evaluator
    -> measured failure audit
    -> independent segment/event truth
    -> Logistic dual-head emissions
    -> explicit-duration HSMM
    -> prospective multi-group holdout
    -> Tee/Cup/context fusion
    -> only then authority gate
```
