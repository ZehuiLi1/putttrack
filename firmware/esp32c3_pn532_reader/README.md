# ESP32-C3 + PN532 NFC reader

这是 PuttTrack 的 NFC Reader 端 bring-up 工程。当前职责被刻意限制为：

1. 合宙 AirM2M CORE ESP32-C3 通过 SPI 驱动 PN532；
2. 连续读取普通 NFC-A Tag 的 UID，自动完成 50 次稳定性计数；
3. 读取 NFC Forum Type 2 Tag 的 NDEF Text Record；
4. 从文本中提取 `BALL_ID=...`，或从正式 PuttTrack service URI 中提取 opaque `device_id`，为后续玩家与智能球绑定提供确定身份。

定位、BLE Channel Sounding 和运动检测不放进本工程。

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

对应输出包含 `ndef_uri` 和从路径中提取的 `device_id`。UID 只作为射频/协议诊断值，不作为 PuttTrack 权威身份。

```json
{"event":"nfc_tag","uid":"...","consecutive_reads":1,"stable_target":50,"ndef_ok":true,"ndef_uri":"putttrack://service/tag/0123456789abcdef?fw=0.1.13","device_id":"0123456789abcdef"}
```

此处的通信链是：

```text
ESP32-C3 --SPI--> PN532 --13.56 MHz NFC-A--> nRF54L15 NFC Tag
```

没有 ESP32-C3 到 nRF54L15 的额外 UART，也不需要单独的唤醒 GPIO。PN532 开启 RF 场并轮询 NFC-A；nRF54L15 侧用 `NFC_T2T_EVENT_FIELD_ON`（具体名字以所用 NCS 版本 API 为准）作为被场唤醒/进入服务态的事件，并在 `FIELD_OFF` 后按产品电源策略恢复低功耗。真正的 System OFF 唤醒能力必须在所用 XIAO/nRF54L15 板、NCS 版本和外接线圈上实测电流与行为，不能只靠串口日志宣称通过。

## 当前边界

- 已实现 PN532 SPI bring-up、UID、50 连读、Type 2 NDEF Text/URI、`BALL_ID` 和 opaque `device_id` 提取。
- Wi-Fi/HTTP/MQTT 暂不加入，避免硬件 bring-up 被网络问题干扰。
- 配套的正式 nRF54L15 NFC service 位于 `../nrf54l15_tag_app/`，硬件和唤醒验证边界见 `../../docs/hardware/NRF54L15_TAG_NFC.md`；它属于 NCS/Zephyr 工程，因此没有混入这个 PlatformIO 环境。
- 生产绑定不能只信任可复制的 UID/NDEF 明文；后续需要应用层签名/挑战或受控后台授权。当前实现是实验和身份链路 bring-up，不是生产安全方案。
