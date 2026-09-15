# NFC 电容对照测试

目标：区分同一颗原版 Tag 上两个 220 pF 电容的影响。现有 Tag 与 XIAO 的比较同时改变了板子、供电与固件，不能单独证明电容失配。

## 当前已知状态

- 原版 Tag 0.1.20：3 轮电池 System OFF / NFC 唤醒 / 原配对 L2 BLE / IMU 均通过。
- PN532 诊断已区分无线 CRC、奇偶校验、响应超时与主机收发失败；NDEF 读取失败不等于格式不正确。
- XIAO 0.2.6：BLE ATT 0x0F 已通过 NFC 重配对恢复。macOS 原先无 XIAO 配对记录，XIAO 拒绝新安全协商；按完整 NFC ID 发送一次迁移命令清除该球旧配对后，重新建立 L2 加密、安全错误归零。断开后重连并采集 10 秒 IMU，501 帧、约 50 Hz、无断点/无效样本、恢复 auto。该修复未改 XIAO 固件或降低加密要求。详见 runs/xiao_nfc_repair_third_20260915.json。
- 电压/SOC 经 BLE 读取，NDEF 仅包含设备 ID 和固件。SOC 是估算值；XIAO USB 供电下电池端电压不能证明接了电池。

## 到实验室后操作

1. 固定同一颗 Tag 的天线位置、角度、引线、供电、电池位置和 PN532 设置。拍照或标记位置，记录实际电容值。
2. A：保持两个 220 pF，记录 60 秒。不要在采样时拿放。
3. 断电后断开两个外接电容，保持 NFC1/NFC2 与线圈相连；检查没有短路。重新供电、等设备上线，按相同位置复原。
4. B：断开电容，记录同样 60 秒。
5. 断电后恢复两个电容；A2：再次记录 60 秒，排除摆放或偶然波动影响。
6. 先比较完整 NDEF 比例、完整读数/秒、错误码；再用同一套休眠循环比较开场至 NDEF、NDEF 至 BLE。不同方案都能正常工作后，才比较距离与角度。

网页服务保持运行。只读采样命令（在仓库根目录）：

```sh
.venv/bin/python tools/check_nfc_window.py --device-id f383571202836e6f --condition tag_220pf_A --duration 60 --output runs/tag_caps_A.json
.venv/bin/python tools/check_nfc_window.py --device-id f383571202836e6f --condition tag_no_caps_B --duration 60 --output runs/tag_caps_B.json
.venv/bin/python tools/check_nfc_window.py --device-id f383571202836e6f --condition tag_220pf_A2 --duration 60 --output runs/tag_caps_A2.json
```

以上命令依次对应三次物理接线状态，不能不改接线连续运行并称为电容对照。

报告以目标设备 ID/UID 筛选，避免把另一块板的成功混入。完整率分母仅含已经发现该 UID 后的读取尝试，未发现 UID 的扫描无法分配给某颗球，不能称为总体寻卡成功率。
`first_success_after_window_start_s` 是采样窗口开始后首次成功，**不是**放球时间或硬件唤醒时延。
没有读数时比例为 null、valid_observation=false；读卡器重启/设置变化/服务更换也会标记无效。
保存报告与引用的原始日志一起比较，勿只截取好看的单段。

## 若要实测谐振点

优先用覆盖 13.56 MHz 的 VNA 配合弱耦合小线圈扫频；测量时关掉 PN532 射频，避免读卡器主动信号影响测量。用固定耦合位置比较配置，保留实际装配的天线、板子和电池邻近关系。
普通示波器直接接天线会引入额外电容；只看到 13.56 MHz 载波不能证明标签谐振点正确。
Nordic 调谐说明：https://devzone.nordicsemi.com/nordic/nordic-blog/b/blog/posts/nfc-tag-antenna-tuning
