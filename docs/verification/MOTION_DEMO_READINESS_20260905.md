# 最新 MCU Demo 下载准备与实球健康复查

日期：2026-09-05。

## 结论与来源

本轮实球试运行采用 [PR #25](https://github.com/ZehuiLi1/putttrack/pull/25)
连续 Motion Demo，来源 `3a8be1b3f2cf5943bc7a8d2838e9ebe486feea94`。
该提交的 GitHub Verify、Pre-Hardware Readiness、NCS Tag Motion Demo Build
均成功；PR #25、另一实现 PR #24 仍未合并。

**已完成 OTA test-boot；现场拿起验收失败，未确认，已回退到 `0.1.17`。**
新版只作为失败试验镜像保留，不作为通过验收的下载推荐。

## 现场验收结果

原有 `0.1.17` 健康检查、包哈希和槽位检查通过后，经加密 BLE 上传，设备端
摘要与候选包一致。`0.1.18` 以未确认镜像启动，`0.1.17` 保留在回退槽。
双传感器、50 Hz、NFC 初始化通过，首轮 20 秒观察始终 STATIONARY、事件数 0，
watcher 退出后验证 auto 恢复成功。NFC 实际读卡和物理唤醒未完成。

用户确认完成五次拿起，球端 event_count 只从 0 到 1；较长时间保留
CARRIED_CANDIDATE，无法凭稀疏 snapshot 为每次漏检确定原因。
在重新观察到 STATIONARY 后，用户再确认完成一次拿起、放回、松手静止，
球端依次 ACTIVE_PENDING → ACTIVE_UNKNOWN → STATIONARY，event_count 未增加：

| 特征 | MCU 值 | 冻结规则 | 结果 |
|---|---:|---|---|
| positive vertical impulse | 1.360 m/s | > 0.5 | 通过 |
| mean gyro norm | 3.59 rad/s | < 10 | 通过 |
| axis consistency | 0.837 | < 0.75 | 未通过 |

64 条现场 snapshot 来自同一 boot，quality_flags=0、sensor_errors=0。
这证明该次漏检不由已报告的传感器健康或削顶质量错误解释，不能说明所有
传感器物理误差均已排除。用户标签无独立视频，未采集本轮原始 IMU，不能将
本轮结果泛化为准确率或据此重调冻结阈值。

记录：[trial-summary.json](motion-demo-readiness-20260905/trial-summary.json)、
[现场 snapshot](motion-demo-readiness-20260905/operator-trial.jsonl)、
[回退后健康](motion-demo-readiness-20260905/rollback-status.json)、
[回退槽位](motion-demo-readiness-20260905/images-rollback.txt)。

下一项算法工作是定向采集“重新静止后高轴一致性拿起”和多次拿起之间的
松手静止原始 IMU，附设备 GO 和实际动作时刻，复现漏检及重新进入静止条件。
冻结 V0 不变；若需改规则，使用新 detector ID 和独立 holdout。其余 no-lift、
滚动和 NFC 现场门仍为未完成，不应在失败后确认镜像。

旧 shadow 分支与 PR #25 都使用 `0.1.18+0`，但命令 24 不兼容：旧分支是
write/arm，PR #25 是 read/连续 snapshot。不能仅按版本号选包。

本次以原有设备实验签名密钥、NCS v3.4.0、NFC overlay 构建，imgtool 已验证
签名。GitHub CI 使用一次性密钥，其产物不用于本球 OTA。

- 路径（相对本 worktree）：
  `build/nrf54l15-tag-demo-3a8be1b/nrf54l15_tag_app/zephyr/zephyr.signed.bin`
- 文件 SHA-256：`cdf44659094412a9de548ccc301e327f1aea8c29e9d64162e40e49cfe65c9009`
- Flash：207,064 / 696,176 B（29.74%）；RAM：217,180 / 262,144 B（82.85%）。
- 来源、MCUboot digest 和安装状态：[candidate.json](motion-demo-readiness-20260905/candidate.json)。

算法仍为 candidate-only、`authority=false`。最新 clipping lower-bound helper
是独立研究 primitive，不能当作已接入的产品识别功能。

## 本次实球发现

目标 `f383571202836e6f`，BLE `DA:88:62:A1:D3:40` / random。

1. 两次读取发现 ADXL367 未就绪、三次恢复失败、quarantined、stream=0，
   自动重启 guard 已设置。
2. 核对 MCUboot 确认态及无 pending image 后执行一次加密 SMP reset。
3. 新 boot `174904b233035578` 双传感器 healthy、50 Hz、capture-safe，
   sensor/PM errors=0。
4. 约 150 秒 uptime 复查仍为同一 boot，auto/idle、ADXL interrupt wake 开启、
   BMI SPI suspended、sensor/PM errors=0、电压 2,942 mV。
   idle 的 capture_safe=false 是采样停止后的正常状态。

原始状态：[故障前](motion-demo-readiness-20260905/before-reset.json)、
[重启后](motion-demo-readiness-20260905/after-reset.json)、
[恢复 idle](motion-demo-readiness-20260905/settled-after-reset.json)。

这只证明本次远程重启可恢复，未定位根因。当前 recovery 中 device_is_ready
检查本身不是驱动重新初始化；仍需密封球启动重复性、供电与初始化故障验证。

## Host 修复与验证

监看工具要求明确 BLE 地址和完整 ID；power write 前验证只读 Demo 协议和冻结
配置哈希。输出前检查 boot、固件、sensor recovery generation、健康状态，
将来源 status 写入可选 JSONL。

研究模式写入/等待失败时仍执行 auto cleanup；进入工具时已在 research 也会
恢复 auto。cleanup 失败返回错误退出。健康 idle 可进入 preflight，quarantine
不能。`python tools/verify.py`：221 个测试、11 个 verifier 检查通过，包括 C
原始数据回放及新失败路径回归；不等于实球动作验收。

## 复测命令参考（先完成失败分析，不确认本候选）

核对包哈希、设备身份、健康和槽位后，上传 signed application 并标记 test。
日常 OTA 不使用 first-install HEX。test-boot 后检查身份和 Demo read contract：

```bash
python tools/watch_ball_motion_demo.py \
  --hci-port /dev/cu.usbmodem101 \
  --ble-address DA:88:62:A1:D3:40 --address-type random \
  --expected-device-id f383571202836e6f \
  --jsonl runs/mcu-motion-demo-first-trial.jsonl
```

按[现场矩阵](../research/MCU_MOTION_DEMO_V0_DECISION_20260905_CN.md)测试静止、
拿起、不离地触碰/旋转/滑动、推杆、碰轨和滚动拿起，另验 NFC、idle/wake 和
OTA 回退。监看日志是稀疏 snapshot，不能代替原始 IMU 真值采集。
全部通过后才确认镜像；失败保留日志并回退。

随后推进独立日期/操作者/第二球盲测，以及物理 Tee PN532 + Cup 光学/PN532
单洞闭环，再按实测决定网关、功耗策略和定制 PCB。
