# ESP32-C3 + PN532 NFC reader

这是 PuttTrack 的 NFC Reader 与滚轮测试台 bring-up 工程。当前职责为：

1. 合宙 AirM2M CORE ESP32-C3 通过 SPI 驱动 PN532；
2. 连续读取普通 NFC-A Tag 的 UID，自动完成 50 次稳定性计数；
3. 读取 NFC Forum Type 2 Tag 的 NDEF Text Record；
4. 从文本中提取 `BALL_ID=...`，或从正式 PuttTrack service URI 中提取 opaque `device_id`，为后续玩家与智能球绑定提供确定身份。

5. 通过第二路 UART 安全控制一台 ZDT/张大头 Emm_V5 闭环步进驱动器，用于生成可重复的真实滚动 IMU 数据。

定位、BLE Channel Sounding 和运动分类不放进本工程；本工程只产生带已知速度和时长的机械刺激。

## 接线

先把 PN532 模块的拨码/滑动开关切到板上丝印所示的 **SPI** 模式。兼容板的开关方向可能与网上图片不同，以自己模块的丝印为准。

| PN532 长排端子 | 合宙 AirM2M CORE ESP32-C3 | 说明 |
|---|---:|---|
| `VCC` | `3V3` | 只使用 3.3 V |
| `GND` | `GND` | 必须共地 |
| `SCK` | `GPIO6` | SPI clock |
| `MISO` | `GPIO10` | PN532 -> ESP32-C3 |
| `MOSI` | `GPIO3` | ESP32-C3 -> PN532 |
| `SS` | `GPIO2` | SPI chip select；建议约 10 kΩ 上拉到 3.3 V |
| `IRQ` | 不接 | 第一阶段不用 |
| `RSTO` | 不接 | 第一阶段不用；这是模块输出信号，不要当普通 reset 输入 |

GPIO6 和 GPIO2 均在合宙 CORE ESP32-C3 上正常引出；程序通过 ESP32-C3 GPIO Matrix 显式映射 SPI，不依赖 Arduino variant 的默认 SPI 脚。GPIO2 同时是 ESP32-C3 strapping pin，PN532 的 SS 端不应主动驱动它；为避免上电采样期间悬空或干扰，建议 SS/GPIO2 使用约 10 kΩ 上拉到 3.3 V。若你的合宙载板丝印或硬件版本不同，先核对原理图，再在 `platformio.ini` 的 `build_flags` 中覆盖 `PT_PN532_*`，不要直接散改业务代码。

### 张大头 Emm_V5 TTL UART

| Emm_V5 端子 | 合宙 AirM2M CORE ESP32-C3 | 方向 |
|---|---:|---|
| `Gnd` | `GND` | 必须共地 |
| `R/A/H` | `GPIO4` | 驱动 TX -> ESP RX（实机确认） |
| `T/B/L` | `GPIO5` | ESP TX -> 驱动 RX（实机确认） |

驱动器使用自己规定的 7–32 V 电机电源，**不能**从 ESP32 的 3.3 V/USB
给电机供电。驱动器菜单必须设为 `P_Serial=UART_FUN`、默认
`Baud=115200`、`ID_Addr=1`、`Checksum=0x6B`、`Response=Receive`，并按
Emm_V5 手册保留 TTL 模式的两只横向跳线帽。这里接的是 TTL 端子，不是
RS232/RS485 模块端子。

**不要使用 GPIO11。** ESP32-C3 的 GPIO11 默认是 Flash 的 `VDD_SPI`；把它
改成 GPIO 需要确认特殊供电硬件并烧写不可逆 eFuse，不值得为测试台冒险。若之前
接在 IO11，断电后改用上表的 IO4/IO5。GPIO4/GPIO5 与上面的 PN532 SPI 无冲突。

固件上电/重启会先发送 `STOP + DISABLE` 进入已知安全状态，绝不会自动使能或转动
电机。控制命令通过 USB 串口逐行输入：

```text
motor probe
motor scan
motor status
motor arm
motor run 30 3
motor run 60 3 20
motor run 60 3 20 5
motor stop
motor disable
```

`probe` 是按当前 115200/地址 1 进行只读固件/硬件版本查询；`scan` 复用已在
`esp32s3_eth_ball_BACK` 实机使用的诊断策略，只发送 `0x1F` 版本读取命令，遍历
Emm_V5 菜单提供的 9 种波特率、地址 1–16 和
fixed-0x6B/XOR/CRC-8/Modbus 四种校验。扫描前还会验证 ESP32 UART 内部回环、
RX 空闲电平和静默字节数，便于区分软件、浮空/噪声与驱动无响应。非 0x6B
应答只用于指出菜单配置，不会解锁运动。只有最近 60 秒内 fixed-0x6B 探测成功才能
`arm`；一次
`arm` 只允许随后 10 秒内执行一次 `run`。当前 bring-up 硬限制为
`|rpm| <= 300`、最长 30 秒。`run` 的可选第三个参数是 Emm_V5 的
`acceleration` 档位（`0..255`，默认 `20`）；它是驱动协议参数而不是物理加速度，
必须通过 IMU/编码器实测标定。`0` 表示直接加速，机械冲击最大，只能在低速、固定良好
且防护到位时用于受控实验。可选第四个参数是 `deceleration`
（`0..255`）；提供时，到时用 `F6` 受控降到 0 RPM，4 秒内未归零则
自动回退到冗余立即 STOP。不提供时保持原来已验证的立即 STOP行为。

每次运行到时发送三次冗余 STOP，在仍保持驱动使能的短窗口内轮询实时速度，
确认 `0 RPM` 后才失能；750 ms 内不能归零会明确报告失败。`motor status` 同时
返回编码器累计 `position_raw`，因此 ACK、速度和实际位置变化可以交叉验证。
负 RPM 表示相反方向。第一次机械测试应从
`motor run 30 3` 开始，并随时准备发送 `motor stop`。电机运行期间固件暂停 NFC
轮询，以便约 2 ms 一次检查自动停止期限和 USB 急停命令。

也可以在仓库根目录使用带二次确认和相同限幅的电脑端工具：

```bash
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 probe
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 scan
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 status
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 run \
  --rpm 30 --seconds 3 --acceleration 20 --confirm-clear
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 run \
  --rpm 60 --seconds 3 --acceleration 20 --deceleration 5 --confirm-clear
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 stop
```

省略 `--port` 时，电脑端工具只会在恰好发现一块 Espressif USB 串口设备时自动
选择，避免把命令误发给 XIAO/nRF52840 HCI 串口。

ESP32 重启后能发停止命令，但 **ESP32 完全掉电时无法停止仍由独立电源供电的
驱动器**。首次以及所有有人值守的测试，电机电源开关/急停必须伸手可及；在增加
具有默认失能电平的硬件 `EN` 联锁之前，不允许无人值守运行。

## 构建、烧录和串口

在仓库根目录运行：

```powershell
pio run -d firmware/esp32c3_pn532_reader
pio run -d firmware/esp32c3_pn532_reader -t upload
pio device monitor -d firmware/esp32c3_pn532_reader
```

如果电脑上有多个串口，用 `pio device list` 找端口，然后为 upload/monitor 命令增加 `--upload-port COMx` 或 `--port COMx`。

启动成功时应看到：

```json
{"event":"pn532_ready","chip":50,"firmware_major":1,"firmware_minor":6}
{"event":"scan_ready","technology":"NFC-A"}
```

同时还会看到 `motor_uart_ready`，其中明确打印 RX/TX 引脚。它只代表 UART 已准备，
不是电机已通信；必须以 `motor probe` 返回 `"ok":true` 为准。

完全看不到 `boot` 通常是串口/端口问题；看到 `pn532_not_found...` 则优先检查 3.3 V、共地、四根 SPI 线和接口模式开关。

## 两阶段验证

### 连续高速读卡测试（当前默认）

`PT_NFC_STRESS_TEST=1` 用于保持小球不动、反复完成 UID + NDEF 读取：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `PT_SCAN_TIMEOUT_MS` | 250 ms | 寻卡时传给库的等待超时，不是固定读取周期 |
| `PT_SCAN_GAP_MS` | 5 ms | 每轮结束后的间隔 |
| `PT_PN532_READY_POLL_MS` | 1 ms | ESP32 检查 PN532 就绪的间隔（build flag） |
| `PT_TYPE4_FIELD_OFF_MS` | 8 ms | 读到目标后主动断场，随后重新开场 |
| `PT_TYPE4_COMMAND_WINDOW_MS` | 0 ms | 压测不等待主机迁移命令 |

每轮仍读取完整 NDEF；寻卡失败、NDEF 失败后也会断场重试，避免停在旧会话。
PN532 被动激活额外重试设为 0，由主循环负责下一轮重试。实际周期还包括寻卡、
APDU、SPI、RF 开关命令和串口输出耗时，**不等于 5 ms，也不能按 250 ms
直接推算读取频率**。用监视器 JSONL 中相邻 `nfc_tag` 的主机时间测量吞吐量，
并同时检查 `ndef_ok`、`scan_miss` 和 `rf_cycle_failed`；50 连读仍只证明 UID
连续读取，完整 NDEF 压测还要求每条 `ndef_ok=true`。8 ms 断场和 1 ms 就绪
检查是待实机验证的测试参数，需以持续读取结果确认稳定性。

XIAO 的 Type 4 回复由 NFC 栈/NFCT 事件驱动；应用回调只计数、恢复身份缓冲区
或提交后台工作，没有固定回复周期，也没有每次回复前的 sleep。此次不需要
修改或重刷 XIAO。滚轮运行时仍暂停 NFC 扫描。

压测模式的 `nfc migrate` 明确返回 `stress_test_read_only`。需要迁移时，在
`platformio.ini` 的 `build_flags` 增加 `-DPT_NFC_STRESS_TEST=0` 并重新构建烧录，
恢复每轮 40 ms 的迁移窗口；主机必须在有效会话内发送，错过窗口需要重试。
启动的 `scan_ready` JSON 会报告实际压测开关和各项扫描参数。

2026-09-15 初版高速配置（100 ms 超时，仅发现目标后断场）完成编译、烧录与实机采集，XIAO
报告固件 `0.2.6`。两段记录中标签可读期间约 7.8–7.9 次/秒，典型间隔约
127 ms；第一段 177 次读取中有 1 次 NDEF 失败、5 次连续读取中断，最长 UID
连读 110 次。第二段 60 秒记录共 88 次读取、3 次 NDEF 失败，后半段没有读到
标签。用户确认标签保持不动，因此该初版未通过稳定性验证。原始记录为
`runs/nfc_fast_boot_validation.jsonl` 和 `runs/nfc_fast_60s_validation.jsonl`。

随后改为上述 250 ms 超时、0 次额外被动激活重试，并在每轮（包括寻卡失败）
结束后断场恢复。重新编译烧录后的 60 秒采集，排除启动前残留串口数据和约
5.5 秒启动过程，连续完成 **430 次完整 UID + NDEF 读取**，约 **7.86 次/秒**、
间隔中位数 **127 ms**，未出现 `scan_miss`、NDEF 失败、`tag_removed` 或
`rf_cycle_failed`。有效连续观察约 54.6 秒，尚不代表长时间耐久测试通过。
记录：`runs/nfc_fast_recovery_validation.jsonl`（统计从最后一个 `boot` 起算）。

### 桌面实时监视器

射频驱动只读诊断：启动后第一次成功读取 Type 4 NDEF 时自动输出 `rf_status`；
串口命令 `nfc rf status` 会安排下一次成功读取后重新采样，不写射频配置。
2026-09-15 实机读回：`TxControl=0x83`、`TxAuto=0x4B`、`RFCfg=0x59`、
`GsNOn=0xF4`、`CWGsP=0x3F`、`ModGsP=0x11`、`RxThreshold=0x85`。
载波 P/N 驱动字段分别为 63/63、15/15，已无增大这两个字段的余量；接收增益
为 38 dB。这是寄存器读回，不是天线输出功率、场强或匹配质量的测量。
来源：[PN532 数据手册 §8.6.23.36–39](https://www.nxp.com/docs/en/nxp/data-sheets/PN532_C1.pdf)。
原始日志：`runs/nfc_web_20260915_022153.jsonl`。

浏览器可视化：在仓库根目录运行 `.venv/bin/python tools/run_nfc_status_web.py`，
打开 `http://127.0.0.1:8765/`。显示近 10 秒完整读取频率、读取间隔、60 秒趋势、
完整身份连读、NDEF 失败及读取中断。启动服务会重启 ESP32 并清除积压串口数据，
统计从新 `boot` 开始；浏览器刷新不会重启硬件。串口日志自动写入 `runs/nfc_web_*.jsonl`。
成功率仅针对已发现标签的身份解析，不能当作所有 RF 轮询的成功率。

页面同时提供 USB 供电下的“放球识别”：校验 NFC URI 后寻找对应 BLE 广播，
读取 GATT 与加密 SMP 状态，确认完整 `device_id` 一致后显示“识别完成”。
同一次放置保持一个 BLE 连接，每 2 秒读取状态；移除、换球、超过 3 秒无有效
NFC 身份会取消旧流程。连接失败间隔 5 秒重试，单次放置最多 3 次。
这一步不关联玩家、不激活球洞、不清除配对或迁移所有权。

放球统计按本次页面服务运行累计，与每秒 NFC 连读计数分开：第一次有效身份
开始一次放球，首次 BLE 核对成功计为成功一次，3 次连接尝试均失败计为失败，
完成前拿走/换球/读卡器断线计为中断。成功率分母为已出结果的成功、失败和
中断次数，尚在识别中的放球暂不计入。耗时从首条有效 NFC 身份到首次 BLE
核对完成计算，包含重试等待；无法代表物理放球到第一次 NFC 发现的时间。
成功后的 BLE 断连单独累计，不重复增加成功次数。

短暂 `scan_miss` / `tag_removed` 不立即取消识别流程；连续 3 秒没有有效 NFC
身份后才结束当前放球，不同有效设备身份则立即切换。页面展示最近 8 次，
导出包含本次运行累计统计和最近 50 次；完整过程保存在识别 JSONL 的
`placement_started`、`placement_result`、`placement_closed` 等事件中。
服务重启开启新的统计，旧日志保留。自动回归涵盖 1,000 次注入故障的模拟放球、
旧异步结果隔离、换球取消、重试上限和成功后的 BLE 中断；不代替硬件耐久测试。

System OFF 按钮测试：先完成身份核对，把球拿离发球垫并等待 3 秒，点击
“进入 System OFF”；固件能力、设备身份、加密状态和无 NFC 场均核对后，
发送现有的显式休眠命令。命令接受后至少等待 3 秒，再放回发球垫。
页面只有在同球 BLE 身份再次匹配、`boot_id` 变化且
`nfc_system_off_wake=true` 时才报告唤醒验证通过。命令 ACK 本身不等于睡眠
或唤醒成功；USB 测试也不验证电池功耗。识别状态日志另存为
`runs/nfc_web_*.recognition.jsonl`。

2026-09-15 USB 实测：设备 `4d53cd7b5c288607`、固件 `0.2.6`，首次 BLE
核对约 1.61 秒、加密等级 2；连续 NFC 读取期间维持同一次连接。新增按钮的
完整拿离/休眠/放回实机测试仍待操作；身份隔离、旧结果丢弃和休眠门控有自动测试。

后续用户实测更新：02:47:45 读到新 `boot_id=12122265bbd2631b` 且 NFC 唤醒
标志为 true；02:48:01 变为 `e502dc553c809295` 且标志为 false，02:48:10 与
02:48:24 仍是同一启动标识。BLE 状态读回 `reset=32`（当前 Zephyr 的
`RESET_DEBUG`）、`system_off_pending=false`、`system_off_entry_error=0`。
用户确认只执行拿离/点击/放回，未操作复位、USB 或调试工具。该次启动是调试
类原因，不能算作 NFC 唤醒通过；具体调试请求来源尚未定位。旧版本没有逐次
保存休眠命令结果，无法完整重建每一次点击。页面现已记录请求、ACK/错误和
复位原因，并明确提示非 NFC 唤醒，避免持续保留“命令已接受”。证据保存在
`runs/nfc_failed_wake_snapshot.json` 与 `runs/nfc_failed_wake_ble_status.json`。

在仓库根目录运行 `.venv/bin/python tools/run_nfc_monitor.py` 打开本机窗口，
自动连接唯一的 Espressif USB 串口；多块设备时用 `--port /dev/cu.usbmodem1101`
指定。需要 Python Tk 和 `pyserial`。窗口显示当前读取状态、连续计数、
最长连续计数、成功读取总数、漏读事件、最近球身份及固件版本。

连续达到 50 次时显示达标；漏读、移开或连接中断会清除当前达标状态。
超过 3 秒没有新的标签数据会显示读取超时，避免把旧读数当作当前状态。
漏读事件仅表示固件报告的连续读取中断，不代表所有失败轮询，不能据此计算
完整成功率。原始串口数据带主机时间保存在 `runs/nfc_monitor_*.jsonl`。
重新连接会重置窗口计数，并继续追加本次日志；关闭窗口会释放串口。
打开串口可能触发 ESP32 重启；不要同时运行其他占用该串口的采集工具。

### 1. 普通卡 UID

先用 NTAG213/215、NFC 钥匙扣或其他 NFC-A 卡。保持卡不动，串口会输出结构化 JSON：

```json
{"event":"nfc_tag","uid":"04A1B2C3D4E5F6","consecutive_reads":1,"stable_target":50,"ndef_ok":false,"ndef_error":"not_type2_ndef"}
{"event":"stability_pass","uid":"04A1B2C3D4E5F6","reads":50}
```

任意一次 NFC-A 轮询失败都会输出 `scan_miss` 并把连续计数清零，因此 `stability_pass` 代表真正连续完成了 50 次 UID 读取，而不是累计成功次数。

普通 MIFARE 卡不能按 Type 2 NDEF 读取时，`ndef_ok=false` 是正常的；UID bring-up 仍然有效。完成一次 50 连读后，再在 0/10/20/30/40 mm 记录成功率。测试台若为金属，PN532 下方先垫塑料、泡棉或纸盒。

nRF54L15 Type 2 仿真在本次实测中声明了 992 字节用户区，但服务 URI
只需读取前 60 字节。程序会按需逐页加载 TLV，不会因为声明容量大于本地
`PT_MAX_NDEF_BYTES` 就拒绝目标，也不会每次扫描读取完整用户区；单个 TLV
仍必须完整落在本地上限内。

### 2. nRF54L15 智能球身份

nRF54L15 端应运行 NFC-A Type 2 Tag/NDEF，并通过 13.56 MHz NFC 线圈暴露身份。早期原型可使用 UTF-8 Text Record，例如：

```text
PUTTTRACK
BALL_ID=PT-B001
HW_REV=PROTO01
```

成功读取时会多出：

```json
{"event":"nfc_tag","uid":"...","consecutive_reads":1,"stable_target":50,"ndef_ok":true,"ndef_text":"PUTTTRACK\nBALL_ID=PT-B001\nHW_REV=PROTO01","ball_id":"PT-B001"}
```

仓库当前正式的 nRF54L15 Tag service 使用 URI Record：

```text
putttrack://service/tag/<opaque-device-id>?fw=<version>
```

对应输出包含 `ndef_uri`、`service_uri_ok`、从路径中提取并规范化的
`device_id` 以及 `firmware_version`。正式 service URI 必须严格满足：设备
ID 为 1–16 字节的偶数长度十六进制，且存在 1–8 个安全 ASCII 字符的
`fw` 参数；格式错误会明确失败，不能进入后续绑定/OTA 决策。普通非
PuttTrack URI 仍可作为 NDEF bring-up 读取，但 `service_uri_ok=false`。
UID 只作为射频/协议诊断值，不作为 PuttTrack 权威身份。

```json
{"event":"nfc_tag","uid":"...","consecutive_reads":1,"stable_target":50,"ndef_ok":true,"ndef_uri":"putttrack://service/tag/0123456789abcdef?fw=0.1.15","service_uri_ok":true,"device_id":"0123456789abcdef","firmware_version":"0.1.15"}
```

此处的通信链是：

```text
ESP32-C3 --SPI--> PN532 --13.56 MHz NFC-A--> nRF54L15 NFC Tag
```

没有 ESP32-C3 到 nRF54L15 的额外 UART，也不需要单独的唤醒 GPIO。PN532 开启 RF 场并轮询 NFC-A；nRF54L15 侧用 Type 4 的 `NFC_T4T_EVENT_FIELD_ON` 作为被场唤醒/进入服务态的事件，并在 `FIELD_OFF` 后按产品电源策略恢复低功耗。Type 4 服务平时提供身份 URI，也允许迁移工具写入一次带目标设备 ID 和随机数的 NDEF 命令。真正的 System OFF 唤醒能力必须在所用 XIAO/nRF54L15 板、NCS 版本和外接线圈上实测电流与行为，不能只靠串口日志宣称通过。

## 当前边界

- 已实现 PN532 SPI bring-up、UID、50 连读、Type 2/Type 4 NDEF Text/URI、`BALL_ID`，以及严格的 PuttTrack service URI、opaque `device_id` 和固件版本提取。读卡器还支持 `nfc migrate <device_id> <nonce_32_hex>`，用标准 Type 4 UPDATE BINARY 写入迁移命令。
- 已实现并实机验证 Emm_V5 只读探测/状态、双动作门控的定时速度模式、显式停止和失能；2026-09-04 在约 18.7--18.9 V 下完成正反向 30、60、120 RPM 分级测试。编码器位置变化与速度相符，用户确认机械运动；120 RPM 暴露的停止后瞬时 16 RPM 尾速推动了“三次 STOP、确认 0 RPM 后失能”的修复，复测通过且无堵转。300 RPM 仍只是固件 bring-up 硬上限，不代表滚轮或带球工况已获准使用该速度。
- Wi-Fi/HTTP/MQTT 暂不加入，避免硬件 bring-up 被网络问题干扰。
- 配套的正式 nRF54L15 NFC service 位于 `../nrf54l15_tag_app/`，硬件和唤醒验证边界见 `../../docs/hardware/NRF54L15_TAG_NFC.md`；它属于 NCS/Zephyr 工程，因此没有混入这个 PlatformIO 环境。
- 生产绑定不能只信任可复制的 UID/NDEF 明文；后续需要应用层签名/挑战或受控后台授权。当前实现是实验和身份链路 bring-up，不是生产安全方案。

### Mixed legacy Type 2 and Type 4 readers (2026-09-15)

Activation now preserves SEL_RES/SAK and selects ISO-DEP only when bit 5 is
set. Legacy Type 2 Tags receive page READ directly, without an initial Type 4
SELECT that can terminate the session. Type 2 READ uses `inDataExchange` to
wait for a complete 16-byte response before copying a page; the old NTAG
helper read immediately after ACK and could race the emulated Tag.

`nfc_tag` includes `sak` for diagnostics. SAK chooses the exchange protocol;
NDEF capability and content are still validated separately. This follows the
activation/exchange model in the [NXP PN532 user manual](https://www.nxp.com/docs/en/user-guide/141520.pdf).

### 电池 Tag 自动休眠测试

串口 `nfc rf pause` 关闭射频场并暂停寻卡，成功返回
`{"event":"rf_control","ok":true,"paused":true,"lease_ms":60000}`。
`nfc rf resume` 恢复射频场和寻卡；暂停最长 60 秒，固件到期自动尝试恢复。
断场状态不会被正常扫描末尾的 8 ms 场循环覆盖。该命令不修改射频功率，
不等同于物理移除，也不测量 Tag 的睡眠电流。测试时停止网页服务以避免串口/BLE 占用。

```sh
.venv/bin/python tools/check_tag_sleep_cycles.py \
  --device-id f383571202836e6f \
  --address A8E1A586-BB84-C5E6-122C-D36EFD9D9B71 \
  --serial-port /dev/cu.usbmodem101 --cycles 3 \
  --output runs/tag_sleep_cycles.json
```

将电池供电 Tag 留在垫上。脚本先核对 NDEF，再逐轮验证固件已确认、
无场休眠前置条件、休眠后 5 秒无广播、NFC 唤醒启动标识、保留配对后的加密身份、
以及 5 秒真实 IMU 与原电源策略恢复。任何失败都停止并保存报告；退出时尝试恢复射频。

APDU 失败诊断：`apdu_failure.diagnostic` 为 PN532 状态低 6 位（1 标签超时、
2 CRC、3 奇偶、6 位冲突等，见 NXP UM0701-02 表 13）；0x100–0x103 为本地主机阶段错误。
`status_word=-1` 表示没有取得有效 APDU 状态字。页面把诊断附到对应的失败读取，下一次读取会清除，
不会将上一颗球的错误显示成下一颗球的错误。
只读的定时对照采样工具与人工接线步骤见 `docs/hardware/NFC_CAPACITOR_AB_TEST.md`。

### NFC 配对恢复维护构建

默认 `airm2m_core_esp32c3` 环境为只读高速测试，不接受迁移写入。
明确需要恢复某颗球的旧配对时，可编译 `nfc_service` 环境；每次完整 Type 4 读取后
保留 1000 ms 的串口命令窗口，供既有身份锁定的 `nfc migrate` 写入使用。
此构建读取频率会变慢，不能与高速环境直接比较吞吐率。

```sh
pio run -d firmware/esp32c3_pn532_reader -e nfc_service -t upload --upload-port /dev/cu.usbmodem101
.venv/bin/python tools/prepare_tag_migration.py --device-id 4d53cd7b5c288607 --port /dev/cu.usbmodem101
```

先停止网页服务以独占串口/BLE，将指定设备置于 NFC 垫上。该操作会清除**指定球内全部旧 BLE 配对**，
并让当前电脑重新配对；不是一般的无副作用状态检查。工具等待完整、严格校验的 NDEF 身份，
忽略未完成的无线读取，发现其他完整身份则拒绝，配对后要求完整设备 ID 和 BLE 安全等级至少 2。
恢复完成后重新烧录默认环境，再启动页面，以恢复原高速只读参数。
