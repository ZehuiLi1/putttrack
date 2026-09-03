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
`|rpm| <= 300`、最长 30 秒，
每次运行到时强制停止。负 RPM 表示相反方向。第一次机械测试应从
`motor run 30 3` 开始，并随时准备发送 `motor stop`。电机运行期间固件暂停 NFC
轮询，以便约 2 ms 一次检查自动停止期限和 USB 急停命令。

也可以在仓库根目录使用带二次确认和相同限幅的电脑端工具：

```bash
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 probe
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 scan
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 status
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 run \
  --rpm 30 --seconds 3 --confirm-clear
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

没有 ESP32-C3 到 nRF54L15 的额外 UART，也不需要单独的唤醒 GPIO。PN532 开启 RF 场并轮询 NFC-A；nRF54L15 侧用 `NFC_T2T_EVENT_FIELD_ON`（具体名字以所用 NCS 版本 API 为准）作为被场唤醒/进入服务态的事件，并在 `FIELD_OFF` 后按产品电源策略恢复低功耗。真正的 System OFF 唤醒能力必须在所用 XIAO/nRF54L15 板、NCS 版本和外接线圈上实测电流与行为，不能只靠串口日志宣称通过。

## 当前边界

- 已实现 PN532 SPI bring-up、UID、50 连读、Type 2 NDEF Text/URI、`BALL_ID`，以及严格的 PuttTrack service URI、opaque `device_id` 和固件版本提取。
- 已实现并实机验证 Emm_V5 只读探测/状态、双动作门控的定时速度模式、显式停止和失能；2026-09-04 在约 18.7--18.9 V 下完成正反向 30 RPM/3 s、超时自动停止、回读 0 RPM/失能且无堵转。300 RPM 仍只是固件 bring-up 硬上限，不代表滚轮或带球工况已获准使用该速度。
- Wi-Fi/HTTP/MQTT 暂不加入，避免硬件 bring-up 被网络问题干扰。
- 配套的正式 nRF54L15 NFC service 位于 `../nrf54l15_tag_app/`，硬件和唤醒验证边界见 `../../docs/hardware/NRF54L15_TAG_NFC.md`；它属于 NCS/Zephyr 工程，因此没有混入这个 PlatformIO 环境。
- 生产绑定不能只信任可复制的 UID/NDEF 明文；后续需要应用层签名/挑战或受控后台授权。当前实现是实验和身份链路 bring-up，不是生产安全方案。
