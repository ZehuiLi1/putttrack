# PuttTrack IMU 数据全方位分析报告

**分析日期：** 2026-09-04  
**主要数据包：** `putttrack_imu_dataset_20260904.zip`

> 复核说明：本报告随 PR #21 保存的是分析快照。模型汇总缺少生成代码、
> 逐回合特征/折叠清单和完整超参数，因此下述小模型分数尚不能由仓库独立
> 复现。`imu_data_20250306_161150.csv` 不属于已确认的 PuttTrack 数据来源，
> 保持隔离且不参与任何结论。

## 1. 结论

现在不应该直接做一个端到端神经网络，也不应该让 IMU 直接决定计分。

当前数据最支持的路线是：

```text
ADXL367 低功耗唤醒
    -> BMI270 事件窗口
    -> 可解释的物理特征
    -> 小型二分类器（规则 / Logistic / Random Forest）
    -> 时序状态机与迟滞
    -> 场地上下文和实体传感器融合
    -> generic motion evidence
    -> Gameplay Engine
```

现阶段优先任务是把 `PICKED_UP / CARRIED` 的高精度识别做成一个独立、可验证的能力。完整的 `IMPACT / ROLLING / COLLISION / CUP` 多分类仍缺少足够的干净标签、高采样率和独立真值。

## 2. 数据包审计

- 唯一原始捕获文件：**161**
- `tag_motion` 记录：**113,867**
- 总记录时长：**38.1 分钟**
- 绝大部分文件：**50 Hz**
- 正式滚轮夹具：**86 次**
- 最新 pickup/carry：**10 次**
- 最新 nominal putt：**10 次**
- BMI270 加速度计裁剪文件：**0**
- BMI270 陀螺仪裁剪文件：**10**
- 最新真实推杆中陀螺仪裁剪：**8/10**
- ADXL367 裁剪文件：**69**

`113,867` 是采样点数量，不是 `113,867` 个独立训练样本。真正决定模型泛化能力的是独立动作回合、不同日期、不同操作者、不同球体结构、不同速度和不同表面。

### 最新推杆标签质量

- r01–r04：怀疑包含障碍碰撞，不能作为“干净推杆”真值；
- r05：实际静止，标签无效；
- r06：动作/计时不正常；
- r08：GO 前污染，但 GO 后滚动段仍可研究；
- r07、r09、r10：当前最干净的 3 个候选；
- 8 个动态回合触及 BMI270 `±2000 dps` 边界。

因此，当前数据可以形成研究假设，但不能形成正式产品准确率。

## 3. 当前最强的 pickup 区分信息

单独使用以下特征都不够：

- 重力方向翻转：真实滚动也会让球体坐标中的重力方向大幅变化；
- 加速度峰值：推杆撞击可以比手拿起更大；
- “是否有运动”：普通触碰、滚动、碰撞和拿起都会触发。

当前最清楚的差异来自一秒旋转形态：

| 特征 | 当前 pickup | 可用 putt |
|---|---:|---:|
| 一秒平均陀螺模长 | 约 3–7 rad/s | 约 32–45 rad/s |
| 旋转轴一致性 | 0.25–0.60 | 0.88–1.00 |
| 正向竖直冲量 | 有，但与推杆重叠 | 同样可能很大 |

球在地面滚动时通常保持一个主旋转轴；人手拿起时速度较低且更明显是多轴旋转。这是当前最有价值的物理解释。

## 4. 探索性规则与模型结果

探索性三条件规则：

```text
0.6 s 正向竖直冲量 > 0.5 m/s
AND 1 s 平均陀螺模长 < 10 rad/s
AND 1 s 旋转轴一致性 < 0.75
```

在当前刻意选出的 22 个语义回合中：

- pickup：11/11 命中；
- 非 pickup：0/11 误报；
- 表面准确率：100%。

但阈值是在查看数据后选的，所以这是 **in-sample、post-hoc** 结果。即使观测到 11/11，双侧 95% 精确置信区间的成功率下限也只有约 **71.5%**。0/11 误报对应的真实误报率上限仍可达约 **28.5%**。

按整回合 leave-one-episode-out **报告值**比较（当前缺少生成代码，不能独立复现）：

| 方法 | Pickup F1 | 错误 |
|---|---:|---|
| 后验物理规则 | 1.000 | 后验、训练内观察，不属于真正 LOEO |
| Logistic，3 个核心特征 | 0.957 | 连续轻敲被误判 |
| Linear/RBF SVM | 0.957 | 连续轻敲被误判 |
| Random Forest | 0.957 | 连续轻敲被误判 |
| 深度 2 决策树 | 0.909 | 1 FP + 1 FN |

更复杂的特征集没有超过 3 个核心物理特征，说明当前瓶颈不是模型复杂度，而是标签覆盖和独立验证。

## 5. 为什么现在不推荐神经网络

神经网络会把 50 Hz 相邻窗口当成大量样本，但这些窗口来自极少数相同回合，极易产生数据泄漏。一个 15 秒回合切成 100 个窗口，不等于 100 个独立动作。

现在还缺少：

- 严格 no-lift 操作；
- rolling pickup；
- 多操作者；
- 多日期；
- 多起始方向；
- 干净碰撞和台阶跌落；
- 独立视频/实体真值；
- 第二颗机械不同的球；
- 对 impact 足够高的采样率。

因此现在训练 1D-CNN、TCN 或 LSTM，得到的高准确率大概率只是在记忆当前操作者、球壳和动作节奏。

## 6. 推荐算法分层

### V0：现在实施

- stationary detector；
- motion onset；
- 正向竖直冲量；
- 一秒 gyro energy；
- 主旋转轴一致性；
- 时序 FSM、迟滞、refractory period；
- 两条 pickup 路径：
  1. stationary -> lift；
  2. rolling -> roll-model departure -> lift。

当前规则只放在 host/Edge research evaluator，不进入 Gameplay authority。

### V1：有独立 holdout 后

比较：

- Logistic Regression；
- 小型 Random Forest；
- 可选线性 SVM。

首选 Logistic 或小型 RF。它们容易解释、容易校准概率、容易转换为嵌入式 C，而且足以判断当前三特征能否泛化。

### V2：数据规模扩大后

只有当 V1 在独立 holdout 上仍对特定类别混淆，才比较：

- tiny 1D-CNN；
- TCN。

优先 TCN/1D-CNN，而不是 LSTM/Transformer。模型输入应是短时原始/低通后的 IMU 窗口，输出 generic state，不输出分数。

## 7. 要达到 Puttshack 式能力的实际系统

公开信息只能证明类似系统会识别 moving、picked up、slowing、stationary、feature context 等状态；公开资料没有证明其内部一定使用神经网络。

PuttTrack 应追求功能等价，而不是猜测其算法：

```text
Ball IMU:
  stationary / impact candidate / rolling / settling / pickup / drop

Physical hole sensors:
  tee presence / narrow feature / cup entry + identity

Venue context:
  active player / active Ball / hole state / timing

Optional future RF:
  coarse zone / trajectory / localisation evidence

Evidence fusion:
  confirmed stroke / feature / cup / pickup policy
```

IMU 最适合提供“什么时候发生了什么运动”的证据，不适合单独证明“进入了哪个洞”“穿过了哪个奖励门”或“每一次撞击都是一次有效击球”。

## 8. 采样率与传感器建议

50 Hz 对以下任务已经有价值：

- 静止/活动；
- 持续滚动形态；
- 人手拿起；
- 粗略 settling。

50 Hz 不适合：

- 准确解析极短的球杆撞击波形；
- 区分球杆撞击与墙/球碰撞的瞬态细节；
- 精确给出 impact timestamp。

下一版建议：

- 常规运动研究：BMI270 约 200–400 Hz；
- impact 试验：尽可能使用 800 Hz–1.6 kHz 加速度 burst/FIFO；
- 保留 1–2 秒 pre-trigger 和至少 3 秒 post-trigger；
- 若 BLE 带宽不足，先在球内 FIFO 保存，事件后批量上传；
- 继续记录 clipping counter；
- 只有实验证明 `±16 g` 信息不足，才增加高 g 加速度计；
- `±2000 dps` 对快速高尔夫球滚动确实偏小，但对 pickup 分类仍可使用“是否持续单轴高速/已裁剪”的形态特征。

## 9. 下一轮实验

第一批不要铺开十几个类别。先完成 pickup precision gate：

1. 30 次 strict no-lift：触碰、原地旋转、轻推、拖动，但球始终接触地面；
2. 30 次 rolling pickup：慢/中/快滚动中拿起；
3. 30 次新的 pickup：慢拿、正常拿、快速抓，变化握法和初始方向；
4. 30 次干净推杆：弱/中/强，无障碍，并用视频作真值；
5. 30 次碰撞/台阶：墙、护栏、球与球、课程台阶；
6. 30 次杯洞序列：擦边、未进、进洞、弹跳、静止、取出。

关键要求：

- 先冻结当前规则，不再看新数据改阈值；
- 换一天，至少增加一名操作者；
- holdout 完成前不解封标签给调参过程；
- 按 session/operator/ball 分割，绝不随机拆相邻窗口；
- 视频画面需同时看到 GO 提示和球；
- 每次动作后留出静止尾段；
- 标记 surface、orientation、strength、operator、ball/core revision。

## 10. 验收指标

不要只报 accuracy。至少报告：

- pickup precision / recall / F1；
- false pickup per non-pickup episode；
- false pickup per player-hour；
- rolling-pickup recall；
- event timestamp error；
- 按操作者、日期、球、表面的分组结果；
- clipping rate；
- UNKNOWN / review rate；
- 95% 置信区间；
- CPU/RAM/flash 和每事件能耗。

产品级自动处罚应优先追求 precision。漏掉一次拿起可以进入 review；错误地把正常推杆判成违规会直接破坏玩家体验。

## 11. GitHub 状态与建议

当前仓库方向与这次数据一致：

- motion 是 generic evidence，不直接计分；
- 活跃 MVP 是 BLE + motion + physical sensors；
- Channel Sounding 暂不在关键路径；
- 当前文档已经诚实记录了 3 个干净推杆、4 个疑似碰撞、2 个无效回合和陀螺裁剪；
- 数据打包和离线分析管线已经合并；

下一次代码更改应是“holdout evaluator”，不是“把阈值塞进 firmware/gameplay”。

建议实现文件和 merge gate 已写入 `GITHUB_NEXT_CHANGE_RECOMMENDATION.md`。

## 12. 外部 CSV 的隔离处理

`imu_data_20250306_161150.csv` 不在当前 PuttTrack 原始数据包或仓库中，
也没有已确认的来源、设备、动作标签、session、球体结构、固件和 clipping
元数据。它可能属于此前误发的另一项目。

因此它没有被混入本次模型比较，也不作为 PuttTrack 的 legacy reference。
除非未来能够独立证明来源，否则不要重新引入。
