# PuttTrack Research Ball MCU Motion Demo V0

**目标固件：** `nrf54l15_tag_app` 0.1.18  
**目标硬件：** Nordic nRF54L15 Tag / PCA20072 Research Ball  
**状态：** 可构建、可原始数据回放、等待实体 Ball 测试  
**权威：** `authority=false`，不得修改杆数、分数、球道或处罚

## 1. 现在为什么可以做 Demo

当前数据还不足以训练一个可宣称产品精度的十状态分类器，但已经足够把两类证据放入 MCU：

1. 冻结的 `stationary-start pickup V0`；
2. 持续、主轴一致旋转的 `ROLLING_CANDIDATE` 显示状态。

这不是把训练集或一个大型模型复制进 MCU。固件只实现一组可审计的流式物理特征、状态持续时间和 fail-closed 规则。原始 50 Hz BMI270 数据仍保留，后续可以继续在 Edge 侧开发 PG-DH-HSMM。

## 2. Demo 能显示什么

### Persistent candidate states

```text
BOOTSTRAP
    -> STATIONARY
    -> ACTIVE_PENDING
       -> CARRIED_CANDIDATE       when PICKUP_FROM_REST passes
       -> ROLLING_CANDIDATE       when dominant-axis rotation passes
       -> ACTIVE_UNKNOWN          otherwise
       -> UNKNOWN_QUALITY         on unsupported/invalid evidence
    -> STATIONARY                 after a qualified quiet dwell
```

### Event

```text
PICKUP_FROM_REST
```

这个 event 只允许从合格的 `STATIONARY` 前状态产生。滚球后拿起不会被该路径误称为 `PICKUP_FROM_REST`。

## 3. 使用的判据

### Stationary eligibility

- 前置静止窗：至少 40 个样本、至少 0.9 秒；
- acceleration norm standard deviation `<= 0.15 m/s²`；
- gyro RMS `<= 0.08 rad/s`。

### Motion onset

10 个连续样本中至少 6 个满足任一条件：

- `|acceleration norm - g| >= 0.5 m/s²`；
- `gyro norm >= 0.25 rad/s`。

### Pickup from rest

- 约 0.6 秒正向竖直冲量 `> 0.5 m/s`；
- onset 后 1 秒平均 gyro norm `< 10 rad/s`；
- onset 后 1 秒 rotation-axis consistency `< 0.75`；
- 必需窗口内 gyro clipping 时，禁止确认 pickup。

这些判据来自 `configs/research/pickup_detector_v0.json`。MCU header 固定记录其 canonical SHA-256：

```text
62c82c1a313f70912a5bb6c2f53c635fe179c537cdb3738dbc5d2a347050c8ad
```

连续运行时没有实验 GO marker，因此 MCU 用“动作前紧邻的一秒合格静止窗”代替 pre-GO baseline。阈值和 feature equation 没有借此重新调参。

### Rolling candidate

初始一秒显示门限：

- mean gyro norm `>= 8 rad/s`；
- axis consistency `>= 0.90`。

后续半秒 tracking 门限：

- mean gyro norm `>= 2 rad/s`；
- axis consistency `>= 0.85`。

这是从当前数据提出的 post-hoc Demo gate，只表示 sustained dominant-axis rotation。它不是 stroke、速度、碰撞类型或 rolling-pickup confirmation。

## 4. 当前 C 回放结果

运行：

```bash
python tools/replay_mcu_motion_demo_v0.py \
  --output-dir docs/research/mcu_motion_demo_v0_replay_20260905
```

当前 72 个 reviewed precision episodes 的结果：

| 检查 | 结果 |
|---|---:|
| stationary-start pickup positives | 20 |
| pickup events detected | 20 |
| other / unsupported-path episodes | 52 |
| false `PICKUP_FROM_REST` events | 0 |
| gentle-putt + rolling-pickup display scope | 21 |
| observed `ROLLING_CANDIDATE` | 21 |
| episodes that visited `UNKNOWN_QUALITY` | 8 |
| C state context | 6,232 bytes |

这只是同日、同操作者、同一 Ball/core、表面信息不充分的数据回放。它证明 C port 没有立即破坏当前 evidence boundary，不是产品准确率。

## 5. Firmware integration

新增：

- `motion_demo_v0.c/.h`：MCU 流式状态机；
- mcumgr group `64`, read command `24`：读取 Demo snapshot；
- `watch_ball_motion_demo.py`：自动切换 research mode、显示状态并在退出时恢复 auto；
- `mcu_motion_demo_v0.json`：机器可读的 scope、阈值和限制；
- C replay regression：直接读取 repository raw JSONL。

Command 24 返回：

- state / last event；
- quality flags；
- event and transition counts；
- vertical impulse、gyro mean、axis consistency；
- frozen pickup-config hash；
- `authority=false` 和 `candidate_only=true`。

## 6. Build

必须继续使用第一次 commissioning 时的同一 private signing key：

```bash
SIGNING_KEY=/absolute/path/to/private-key.pem \
  scripts/nrf54l15_tag/build_tag_app.sh
```

输出：

```text
build/nrf54l15-tag-app/nrf54l15_tag_app/zephyr/zephyr.signed.bin
build/nrf54l15-tag-app/first_install.hex
```

首次或恢复写入使用 `first_install.hex`。已存在并确认 MCUboot baseline 的实体 Tag 优先使用 signed BIN 做 BLE test upgrade。

## 7. BLE OTA test sequence

下面示例沿用 XIAO nRF52840 USB HCI 路径；实际地址必须换成目标 Ball：

```bash
nrfutil mcu-manager ble \
  --hci-serial-port /dev/cu.usbmodem101 --timeout 30 \
  image-upload --address DA:88:62:A1:D3:40 --address-type random \
  --pair --secure-connection \
  --firmware build/nrf54l15-tag-app/nrf54l15_tag_app/zephyr/zephyr.signed.bin \
  --image-number 0
```

随后执行既有 `image-list -> image-test -> reset` 流程。先保持 test boot，不要立即 confirm。

## 8. 启动现场 Demo

```bash
python tools/watch_ball_motion_demo.py \
  --hci-port /dev/cu.usbmodem101 \
  --ble-address DA:88:62:A1:D3:40 \
  --address-type random \
  --expected-device-id f383571202836e6f \
  --jsonl runs/mcu-motion-demo-v0.jsonl
```

工具会：

1. 验证完整 device ID；
2. 把 Ball 切换到强制 50 Hz `research` policy；
3. 轮询 encrypted command 24；
4. 仅在 state/event/quality 变化时打印；
5. Ctrl+C 后恢复 `auto` policy。

## 9. 第一次实体测试脚本

按以下顺序进行，每个动作前让球静止至少 2 秒：

1. 静止：应显示 `STATIONARY`；
2. 轻推杆 5 次：应经过 `ACTIVE_PENDING -> ROLLING_CANDIDATE`，最后回到 `STATIONARY`；
3. 从静止拿起并携带 5 次：event count 每次增加，出现 `CARRIED_CANDIDATE`；
4. 只触碰、原地转动、轻滑但不离地各 5 次：不得增加 pickup event count；
5. 推杆撞边 5 次：允许 `ROLLING_CANDIDATE`、`ACTIVE_UNKNOWN` 或带 clipping 的质量提示，不得增加 pickup event count；
6. 球在滚动时拿起 5 次：允许先显示 rolling，之后变成 unknown/stationary；当前版本不得假装确认 rolling pickup。

## 10. Test-boot acceptance gate

只有以下条件同时满足，才考虑 `image-confirm`：

- command 24 连续读取稳定；
- 5/5 静止拿起产生 pickup event；
- 15 次 no-lift control 中 0 次 pickup event；
- 5 次 gentle putt 中均可见 rolling candidate 或明确 quality/unknown，不出现 pickup event；
- 5 次 rail collision 中 0 次 pickup event；
- 退出 watcher 后 Ball 成功恢复 `auto`；
- sensor health、sequence continuity 和 battery behavior 没有回归。

失败时保留日志并让 MCUboot test image rollback，不要放宽阈值来通过当天测试。

## 11. 明确不做的事情

- 不识别 authoritative stroke；
- 不区分 putter impact、rail、step 和 ball-ball collision source；
- 不确认 cup entry；
- 不自动加杆或处罚；
- 不把 `UNKNOWN` 改成 `NOT_PICKUP`；
- 不把本次 20/20、0/52 回放称为商业准确率。

下一步若 Demo 实体通过，应先收集第二天、第二操作者、第二 Ball 和命名 surface 的冻结盲测；rolling pickup 则必须增加独立 hand-contact/lift timestamp 后再建立新的 detector ID。
