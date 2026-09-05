# BMI270 球端计杆与拿起识别：Shadow V1 实现和全原始数据回放

日期：2026-09-05。来源基线：PR #25 `ad566404272dc6f5695cb84fd551df5921f7f619`。

## 结论

继续使用现有 Nordic Research Ball 的 BMI270 + ADXL367，不更换芯片。本轮把推杆次数作为首要研究输出，把拿起作为独立的嫌疑事件。已经提供真正执行在 MCU 采样路径的 C 实现、独立协议、原始数据回放、现场采集命令及真值复核工具。

**这是一套可进入受控实球测试的候选系统，不是已经验证的自动计杆/作弊处罚系统。** 球端没有修改 Gameplay 的接口；`authority=false`；`confirmed_stroke_count=null`。之前失败的 `0.1.18` 不会因此自动通过，本轮也不修改冻结 Pickup V0。

## 1. 数据没有被放弃

合并检查仓库实验目录和首轮 ZIP 归档，按完整原始文件 SHA-256 去重：

| 项目 | 数量 |
|---|---:|
| 实验目录中原始 capture | 84 |
| 历史归档新增唯一 capture | 152 |
| 被排除的完全重复路径 | 9 |
| 实际重放的唯一 capture | **236** |
| 实际送入 C 引擎的 tag_motion 样本 | **168,142** |

其中包括 86 条正式滚筒记录、旧固件/裸板探索、静止、人工滚动、拿起、轻推、正常推、撞栏、台阶和诊断数据。它们的证据等级不同：诊断、错误标签、无可靠动作真值的记录不会冒充商业准确率测试。旧 `imu_data_20250306_161150.csv` 仍不混入本项目。

程序从原始 JSONL 提取 SI 单位向量、时间戳、序号和质量字段。**GO、场景名、计划杆数、标签都不送入 C 引擎**；它们只用于报告分组和截取观察区间。每份原始文件均可从结果表追溯 SHA-256 和来源。

- [最终逐回合结果](replay_v1/capture_results.csv)
- [最终完整事件日志](replay_v1/events.jsonl)
- [机器可读摘要](replay_v1/summary.json)
- [初始实现结果](replay_initial/summary.json)

## 2. 实际发现与修正

### 2.1 一秒平均把击球与后续反弹混在一起

初始实现中，10 条撞栏回合只有 5 条产生一次击球候选。例如 `putt-rail-light-r01`：起始约 0.2 秒的方向一致性约 0.986，而一秒整体约 0.492。先向前滚动、再反弹，不能因此否认先前发生过一次发起运动的事件。

修正为两阶段：

1. 约 **200 ms** 保存初始接触瞬态与持续旋转，输出 `STROKE_PENDING_NOT_COUNTED`，**不增加计数**。
2. 约 **1 s** 检查拿起路径；若符合拿起证据，转为 `PICKUP_SUSPECTED`，不把早期 proposal 计作一杆。否则保留早期启动证据，产生 `STROKE_LIKE_CANDIDATE`。

开发中曾尝试直接在 200 ms 增加计数；全量归档随即暴露两条早期拿起被误认的情况。因此最终实现保留短窗口信息，但不提前确认计数。这个过程本身说明全量旧数据有实际价值。

### 2.2 静止基线不能紧扣一个理想 1g 数值

初始实现漏掉 `pickup-drop-r09`。原始数据表明动作前很稳定：加速度模长约 9.995 m/s²，标准差约 0.0087 m/s²，gyro RMS 约 0.0070 rad/s。相对理想 9.80665 的硬边界却反复切断静止累计。

新路径在合理的模长范围内识别局部稳定性，建立本次测得的基线，不把稳定的模长偏移当作运动。此修改不等于完整传感器标定，也不证明所有慢动作能识别。

### 2.3 拿起不能被轴一致性一票否决

独立 Shadow V1 使用可解释的研究评分组合；方向一致性只是辅助，不再是必要条件。旧 V0 的 `.75` 阈值、配置和历史结论保持原样。评分不是校准过的概率。

保留方向一致性与轴向集中程度两个不同特征。后者采用 `tr(M²)/tr(M)²`，不是特征值比；单轴正反转的轴向集中程度仍然高。

### 2.4 削顶、手持和二次接触不能强行解释

逐轴 near-rail 被保留。削顶后的方向统计只是受截断的测量描述；不恢复真实峰值，也不把削顶直接叫作“滚动”。依赖重力传播的冲量在必要区间削顶后标为不可用。

球在手里静止与在地上静止可能产生相同 IMU 输出。因此 `held_hint` 与运动是否静止分开；仅安静不会清除持有上下文。显式命令 26 只用于操作者已经放球、松手后的新 bench trial，不是球自动知道自己已落地。

运动中的再次瞬态输出 `MOTION_TRANSIENT_UNRESOLVED`。它可能是撞栏，也可能是滚动中再击一杆，不能直接多计，也不能静默当作零杆。计数结果会同时给出 unresolved 状态。

## 3. 原始数据开发回放结果

以下均为已查看过数据上的回顾性开发结果，不是新的盲测或商业准确率。

| 回合类别 | 初始实现 | 最终 Shadow V1 |
|---|---:|---:|
| 10 条干净轻推：恰好一次击球候选 | 10/10 | **10/10** |
| 10 条推球+撞栏：恰好一次击球候选 | 5/10 | **10/10** |
| 20 条静止起始拿起/拿起后放落：至少一次拿起嫌疑 | 19/20 | **20/20** |
| 10 条严格不离地对照：误发拿起/击球候选 | 0/10 | **0/10** |
| 86 条正式滚筒：击球候选 | 0 | **0** |

**不能省略的失败：**

- 归档中 10 条 normal putt 仍只有 **8 条**得到一次击球候选。
- 两条 reviewed 人工滚动都触发击球候选：**手推与球杆接触来源尚未解决**。
- 10 条 rolling pickup 未产生已支持的 pickup 事件：**滚球中拿起仍未解决**；不能把初始滚动候选当作该任务的成功。
- 没有独立 putter-contact / collision-contact 时刻，不能用整段标签推导“球杆和碰撞分类准确率”。
- 真正停球后第二杆的 2 次计数目前只有合成回归测试；现有资料不是独立两杆现场真值。
- 很慢、基本不旋转的拿起，以及弱击球不滚动，仍可能落入 UNKNOWN 或漏检。
- 大量滚筒中的瞬态会被列为待判扰动，它们不是已证实的物理碰撞。

因此当前目标是实球 **shadow 对照**，而不是把候选杆数直接展示成玩家正式杆数。

## 4. 球端实际实现

- C 核心：`firmware/nrf54l15_tag_app/src/stroke_pickup_v1.c/.h`
- 配置：`configs/research/stroke_pickup_shadow_v1.json`
- 生成配置哈希：`tools/generate_stroke_pickup_config.py`
- 固件编译配置：`stroke_pickup_v1.conf` / `stroke_pickup_v1_nfc.conf`
- 新测试固件身份：**0.1.19**；旧默认 V0 构建仍是 0.1.18。
- 自定义加密 SMP group 64：**25 只读事件日志；26 写入新 bench trial**。
- 16 条有序事件环形日志，明确事件 ID、source 时间/序号、generation、覆盖数量、质量与原因。
- 早期 pending 与最终 candidate 共用 onset 序号，便于关联；前者永不直接增加候选杆数。
- 本次 host C `sizeof(context)` 为 **1256 B**。这不是整机 RAM 数字，也不是 Cortex 实时执行耗时测量。
- 当前仍是 100 Hz 传感器 ODR / **50 Hz 算法输入**。没有冒充已经实现 400 Hz FIFO；错误的输入速率会被拒判。

## 5. 现在怎样进行实球测试

### A. 软件验证

```bash
python3 tools/verify.py
python3 tools/generate_stroke_pickup_config.py --check
python3 tools/replay_stroke_pickup_v1.py --output-dir runs/shadow-replay
```

初始算法可重现：

```bash
python3 tools/replay_stroke_pickup_v1.py --initial-baseline --output-dir runs/shadow-initial
```

### B. 构建与 OTA

使用这颗球**已有的签名密钥**及现有 NCS v3.4.0 环境：

```bash
export SIGNING_KEY="/path/to/existing-device-signing-key.pem"
bash scripts/nrf54l15_tag/build_stroke_pickup_v1.sh
```

输出在 `build/nrf54l15-stroke-pickup-v1/`。沿用现有已验证 OTA 流程，只上传 signed application BIN，以 MCUboot **test** 方式启动。核对设备、包哈希、槽位、健康和新协议后再测试。

**CI 一次性密钥签出的文件不能给现有球 OTA；不要刷 first-install HEX，不要自动 image-confirm。** 本研究提交不修改签名信任、bootloader、采样量程或 Gameplay。

### C. 一条命令完成一次试验

关闭其他占用 HCI 的监看/采集窗口。放球、松手；每次使用一个新目录：

```bash
python3 tools/test_ball_stroke_pickup_v1.py \
  --hci-port /dev/cu.usbmodem101 \
  --ble-address DA:88:62:A1:D3:40 --address-type random \
  --expected-device-id f383571202836e6f \
  --ball-on-surface --scenario stroke_one_clean \
  --seconds 12 --output-dir runs/shadow-one-001
```

命令会先只读核对完整设备 ID、boot、固件及配置哈希，再切研究模式、显式开始新 trial、检查静止、给 GO、冻结完整原始历史、立即抓取球端事件，再下载原始样本。结束时恢复 auto。错误不会静默改成零杆。

保存 `raw.jsonl`、`preflight.json`、`mcu-snapshot.json`、`trial-result.json` 和 `cleanup.json`。原始数据与结果用 SHA-256 关联。16 条日志被覆盖时明确报告 INCOMPLETE_LOG；不能据此当作完整计数。最后两秒保持不动，冻结后不要拿起球。

### D. 第一次测试矩阵

每类先 3 次，优先录视频，不需要重做全部历史数据：

| 场景 | 人工真值 | 主要目标 |
|---|---:|---|
| 单杆无障碍 | 1 杆 | 基础计数与事件时刻 |
| 停球、松手静止后第二杆 | 2 杆 | 连续重新建立基线 |
| 一杆后多次撞栏 | 1 杆 | 多峰不能重复计杆 |
| 另一颗球撞到静止研究球 | 0 杆 | 接触来源反例 |
| 手推滚动 | 0 杆 | 当前已知误报，必须如实记录 |
| 正常拿起再放回 | 0 杆、1 次拿起 | 嫌疑事件与击球互斥 |
| 不离地触碰/旋转/滑动 | 0 杆、0 次拿起 | 拿起误报 |
| 滚球中再击/滚球中拿起 | 按录像 | 当前未支持路径，应保留待判证据 |

最后两类困难动作不要求旧规则“演示成功”。球端自动判断与人工真值分开，操作者不按算法提示修改动作标签。

### E. 独立复核与计数/时刻联合评估

```bash
python3 tools/review_shadow_trial.py runs/shadow-one-001 \
  --session day2-a --operator A --split prospective_holdout \
  --putter-times 1.20 --pickup-times "" --collision-times "" \
  --truth-source video_review --reference "video-001, GO aligned"

python3 tools/evaluate_shadow_trials.py runs/shadow-one-001 \
  --output runs/shadow-one-001-audit.json
```

两杆写两次真实球杆接触时刻，碰撞时刻另填。复核文件禁止覆盖；默认时间匹配容差 0.25 s，是研究评估容差，不是已达到的产品延迟。等量总杆数也可能掩盖一次漏检和一次误报，所以同时报告一对一事件匹配、误报、漏检、UNKNOWN、丢日志和 session 分组。

## 6. 下一阶段的明确边界

只有新的独立时刻真值能够决定手推、其他球撞击、滚动中第二杆和滚动拿起的剩余区分方式。先测试此版本，不追加硬件成本。若高频/预触发采样成为必要条件，下一版单独改变采样路径与缓存预算，不把这版 50 Hz 模型直接喂成 400 Hz。

Tee 身份、洞内活动状态、Cup/feature 和人工纠错仍由 Edge 管理。拾球嫌疑需要结合当时玩法和是否允许取球来处理，不自动宣布玩家作弊。
