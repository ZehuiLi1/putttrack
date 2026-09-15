# 单球、单洞测试

当前收尾基线：原版 Tag 0.1.21、XIAO 0.2.7 均已装球壳、电池供电验证；自动休眠唤醒各 3/3 通过。原版 Tag 保留 v0 计杆，XIAO 使用专用 v1 实验计杆。Golf Up 光电已有正式使用基础，当前 PuttTrack 已保存的入洞结果仍为模拟。统一结论与后续工作见 [阶段收尾](SINGLE_HOLE_CLOSEOUT_20260915.md)。下方按时间追加的旧版本和待办只代表当时状态，以收尾说明和后续记录为准。

运行 `.venv/bin/python tools/run_nfc_status_web.py --serial-port /dev/cu.usbmodem101 --no-open`，打开 http://127.0.0.1:8765 。

1. 将已供电的小球放到发球垫，等待 NFC + 加密 BLE 身份核对完成。
2. 填玩家名，选择模拟入洞（未接光电时）或真实光电，点击“准备新一局”。本局绑定这颗球，拿离发球垫后保持 BLE 接收。开始一局自动切换持续采样 research 策略，结束或取消后恢复进入前策略。
3. 让球静止至少 0.6 秒，再击球。IMU 实验规则自动计杆，页面显示帧数、数据新鲜度及判定状态。漏判时可手动补记一杆；误判时取消本局重试。
4. 真实光电模式在第一杆后发送带局号的 `cup arm <round_id>`；先观察畅通，再出现遮挡才结算。未接线时点击“模拟入洞”。
5. 页面显示本局杆数和最近结果；再放球识别可开始下一局。全过程追加保存到 `runs/nfc_web_*.hole.jsonl`（包括本局原始 IMU）。页面会从已有单洞日志恢复最近 20 个已完成结果，可点击“导出本局与最近结果”。重启不会自动续接未完成的一局。

## 光耦输入

当前为与 PN532 共用 ESP32-C3 的 GPIO7，内部上拉、低电平遮挡、5 ms 去抖，独立任务轮询，不被 PN532 寻卡阻塞。采样事件排队后由串口发送；500 ms 状态心跳。GPIO 可由 PT_CUP_GPIO、极性由 PT_CUP_ACTIVE_LOW 配置。

用户将采用光耦；具体光耦型号和输出端接法尚未确认。输出侧应形成兼容 C3 3.3 V GPIO 的信号，不能根据传感器供电电压推定可直接连接。传感器侧驱动/限流及输出端引脚须按实际器件确定。Golf Up 光电本身已正式使用；本项目的局号绑定与真实入洞结算接入仍待联调。

## IMU 实验规则的边界

`bench-stroke-v0-unvalidated` 复用现有研究的静止→冲击候选→持续运动思路；不是加载已训练的击打模型。现有 recognizer_v1 不包含经过击打验证的商业模型系数。

试验阈值：加速度模长距重力 <1.5 m/s² 且角速度 <0.5 rad/s 持续 0.6 s；紧接着加速度模长 >14 m/s²；随后 0.7 s 内出现角速度 >2 rad/s 持续 0.16 s。低重力 <3 m/s² 拒绝候选。每杆后需重新静止，并至少间隔 1.5 s。无效数据、序号断点、时间间隔超过 100 ms、重连会清空判定状态。

这些是待实测阈值，尤其弱击打可能漏判，拿放/碰撞也可能误判；持续旋转仅为运动代理，尚不能证明纯滚动。页面保留人工补记。本模式只能验证一颗球的玩法链路，单光电无法识别球身份或区分手指遮挡。生产证据策略未修改，实验记录不具备生产计分权威性。

## 本次验证（2026-09-15）

39 项相关单元测试通过；C3 编译与烧录成功。浏览器通过模拟一杆入洞、390 px 页面无横向溢出、无 JS 异常。真实 XIAO 3 秒收到 139 帧有效 IMU，静止判定成立，取消后恢复 auto。真实击球计杆与真实光电入洞仍待现场验证。


## 双硬件准备与自动检查（2026-09-15）

- 原版 Tag：协议 v1，ADXL367 + BMI270，已知身份 `f383571202836e6f`。
- XIAO：协议 v2，LSM6DS3TR-C，身份 `4d53cd7b5c288607`。页面显示真实协议对应的硬件与固件版本；不同协议通知不能混用。
- BLE 断开后清空运动基线，本局继续尝试重连同一身份；使用已核对的 macOS 地址重连，仍重新验证全 ID 和加密状态。结束或取消后恢复进入前策略。正常 SIGTERM/Ctrl-C 退出也执行恢复；断电或强杀无法保证执行清理。
- 原版 Tag 构建修复了附加 overlay 参数覆盖和 Type 2/Type 4 链接不一致，准备了 `build/tag-singlehole-v0.1.19/nrf54l15_tag_app/zephyr/zephyr.signed.bin`。候选版本 **0.1.19 尚未安装到实机**。XIAO 继续使用 0.2.6。

可重复执行的真实链路检查（不创建游戏，自动恢复原电源策略）：

```sh
.venv/bin/python tools/check_tag_motion_link.py --device-id f383571202836e6f --duration 20 --output runs/tag_motion_check.json
.venv/bin/python tools/check_tag_motion_link.py --device-id 4d53cd7b5c288607 --address B4D14F5B-08AC-E5C6-139E-B94647BEFAAD --duration 20 --output runs/xiao_motion_check.json
```

运行前结束页面中的一局，并避免其他工具同时占用同一颗球的 BLE。已在页面完成 NFC 识别时，也可运行 `.venv/bin/python tools/check_single_hole_bench.py --duration 20 --output runs/hole_check.json`，自动创建检查局并取消，不产生入洞成绩。

本次追加验证：83 项相关测试通过；原版 Tag NFC 0.1.19 与 XIAO 0.2.6 均构建通过。XIAO 真实 20 秒采集 1001 帧，约 50 Hz、无序号断点、无无效样本、实验规则零触发，结束后恢复 auto。证据在 `runs/xiao_motion_link_20260915.json` 及同名 JSONL。页面浏览器模拟闭环通过，390 px 下无横向溢出及 JS 错误。

原版 Tag 经 10 秒和 20 秒扫描未发现，macOS 已连接的 PuttTrack 外设中也未发现，**尚不能确认它当前可连接或当前固件版本**。需供电/移近，必要时放到 NFC 垫上唤醒，之后才能验证和决定是否升级。候选固件清单与哈希在 `runs/tag_single_hole_readiness_20260915.json`。

对既有 Tag 数据的规则回放：9 段普通推击有 5 段触发，10 段轻推有 5 段触发；10 段拿放和 1 段静止均未触发。仅是 30 段录像标注片段的触发统计，没有精确事件时间真值，不能称为正式精度。规则未按这些片段调参，漏判明显；报告 `runs/bench_stroke_replay_20260915.json`。待真实光耦接线和两种球各自的击打数据后再调整。


## Tag 重新上线后的实机进展

原版 Tag 已通过 BLE 核对为 f383571202836e6f / 0.1.17；旧 NFC 为 Type 2。修复 C3 的 SAK 协议分流及 Type 2 READ 响应等待后，已读出完整服务 URI（旧版测试仍有间歇失败，不能称为稳定通过）。随后通过签名 OTA 上传并试启动 0.1.19；PN532 已实际读出该版本的 Type 4 服务 URI。

**0.1.19 当前尚未确认保留**：macOS 返回 `Peer removed pairing information`，重试和程序清理旧配对未恢复，需手动在蓝牙设置忽略 `PuttTrack-Tag-v0.1` 后重连。页面提供“重试 BLE”。清理后还须验证加密身份、IMU 采样、恢复电源策略和本局闭环，再用 MCUboot 活动镜像 hash 确认。验证前不要额外重启 Tag，以免试运行镜像回滚。相关记录：`runs/tag_019_upload_result.json`、`runs/tag_019_test_selected.json`、`runs/tag_019_live_check.json`。

确认结果：`runs/tag_019_confirm_result.json`（active=true、confirmed=true、pending=false）；链路证据：`runs/tag_post_user_pairing_check.json`、`runs/tag_019_single_hole_check.json`。


## 电池 System OFF 验证与配对持久化修复（2026-09-15）

0.1.19 第一轮：带电池 Tag 在无 NFC 场时接受 2 秒延迟的 System OFF；10 秒扫描无广播，主动连接超时。放回 NFC 垫后恢复 NDEF，重新配对后加密状态报告 boot 从 `4c46cf3fbc57d9f9` 变为 `2bf416d35b940df8`、reset=128、nfc_system_off_wake=true、加密等级 2、电池 2873 mV、传感器 healthy。因此 NFC 唤醒成立，但自动数据重连失败：该版本未启用 BT_SETTINGS，配对密钥随关机丢失。

0.1.20 修复：Tag 启用 SETTINGS/BT_SETTINGS/NVS/SETTINGS_NVS，在原有 64 KiB storage 分区保存配对；启用动态 BLE 名称；Tag 与 XIAO 均在连接后请求 L2 加密；状态新增 ble_bond_persistence。XIAO 原本已启用持久化，配置无需重复修改。构建成功，OTA 已上传并试启动，等待首次新配对与复测。旧版内存密钥不能被新固件自动恢复，首次升级仍需要清理旧 macOS 配对。

页面增加唤醒后交换的数据。耗时定义为本次命令后**首次有效 NDEF 到完成 BLE 核对**，包含人为配对等待；没有记录起点时不显示耗时。第一轮旧字段 997 ms 仅是最终一次识别尝试时长，不能作为完整唤醒通信延迟。原始日志保留，新的计时逻辑已修正。证据：runs/tag_sleep_command_20260915.json、runs/tag_sleep_ble_absence_20260915.json、runs/tag_first_sleep_wake_result.json；修复版构建和 OTA：runs/tag_020_build.log、runs/tag_020_upload_result.json。

第二轮准备已完成：0.1.20 首次新配对成功，加密等级 2、ble_bond_persistence=true；10 秒真实 IMU 检查收到 501 帧，50 Hz，无序号断点或无效帧，结束恢复 auto。MCUboot 已确认当前活动 0.1.20（confirmed=true）。用户拿离并保持电池供电后，休眠命令被接受，10 秒扫描无 Tag 广播，随后直接连接未找到设备；这仅是休眠侧证据，仍等待放回验证 NFC 唤醒和无需重新配对的数据恢复。证据：`runs/tag_020_pre_sleep_motion.json`、`runs/tag_020_confirm_result.json`、`runs/tag_020_sleep_command.json`、`runs/tag_020_sleep_ble_absence.json`。

第二轮最终结果：**0.1.20 的电池 System OFF → NFC 唤醒 → 自动加密 BLE 数据恢复已通过一次实机闭环**。用户放回 Tag、未复位且无需再次清理配对；boot_id 从 `2d19b7c54cdeb5fa` 变为 `d53f41881a0ce733`，reset=128、nfc_system_off_wake=true、ble_security_level=2、ble_bond_persistence=true。首次有效 NDEF 至加密身份核对完成 1554 ms；这是主机可观测通信耗时，不是射频场出现到硬件唤醒的精确时延。状态读回电池 2809 mV、两颗传感器 ready、sensor_health=healthy。唤醒后独立 10 秒采集 503 帧，约 50 Hz、零序号断点、零无效样本，结束恢复 auto。证据：`runs/tag_020_sleep_wake_result.json`、`runs/tag_020_post_wake_motion.json` 及同名 JSONL。此结果证明本轮配对跨休眠保留和数据恢复，尚不代表长时间循环可靠性或整板休眠电流测量通过；真实击球与杯口光电闭环仍待现场验证。

## 自动重复休眠工具（2026-09-15）

新增 `tools/check_tag_sleep_cycles.py`，配合已编译烧录的 C3 `nfc rf pause/resume`，
让电池 Tag 保持在垫上完成最多 10 轮功能验证（默认 3 轮）。暂停最长 60 秒，
异常退出尝试恢复射频；每轮要求活动固件已确认、无 NFC 场、加密身份一致，
休眠后扫描 5 秒无广播，恢复射频后 boot_id 改变且 NFC 唤醒标志为真，
固件不变、配对/配对失败计数均为零，随后真实 IMU 采集 5 秒并恢复原策略。
原始读卡事件和每轮状态/采样均保存。这里的扫描无广播只是辅助证据，不用于代替唤醒原因核对或电流测量。

30 项相关测试通过，C3 编译/烧录成功。首次自动运行未在 30 秒内读到目标 Tag，
停在 NFC 前置检查，cycles=[]、rf_restored=true，没有发送休眠命令，不能计为通过或 Tag 唤醒失败。
记录：`runs/tag_020_auto_sleep_cycles.json` 及 `.reader.jsonl`。等待用户将 Tag 放回后重新运行。

### 3 轮自动重复验证已通过（2026-09-15）

用户将电池 Tag 放回并保持不动后，第一次自动启动仍在 30 秒内未读出 NDEF，未发送休眠。
独立 BLE 诊断确认 0.1.20、L2 加密、配对计数 0、电池 2865 mV，随后 PN532 再次读出完整 NDEF。
脚本增加起始 3 秒断场清理，识别等待上限改为 60 秒，并增加阶段记录。
之后连续 **3/3 轮** System OFF → NFC 唤醒 → 原配对加密 BLE → 5 秒 IMU 检查通过。
每轮 boot_id 均变化、nfc_system_off_wake=true、新配对和配对失败计数均为 0，固件仍是 0.1.20。
IMU 分别 255、251、251 帧，均约 50 Hz、零序号断点、零无效样本，原 auto 策略恢复，测试结束射频恢复。

| 轮次 | 开场 ACK 到完整 NDEF | NDEF 到加密 BLE | 合计约 | IMU 帧 |
|---|---:|---:|---:|---:|
| 1 | 10.520 秒 | 2.065 秒 | 12.585 秒 | 255 |
| 2 | 10.396 秒 | 2.999 秒 | 13.395 秒 | 251 |
| 3 | 3.143 秒 | 2.990 秒 | 6.133 秒 | 251 |

开场 ACK 到 NDEF 由串口原始日志的主机墙钟重建，BLE 间隔为单调时钟；合计是主机观测的近似通信恢复时间，不是硬件实际唤醒时间。
**配对持久化与功能闭环通过，但 NFC 仍间歇漏读，不能称为即时识别或长期稳定性通过。**
后续优先查 PN532/Tag 的 NFC 事务稳定性，再做真实击球和杯口光电验证。

证据：`runs/tag_020_auto_sleep_cycles_field_reset.json`、对应 `.reader.jsonl` 和 3 份 `.motion.json`/JSONL；
精简统计 `runs/tag_020_auto_sleep_summary.json`；前置失败与 BLE 诊断分别保留在
`runs/tag_020_auto_sleep_cycles_retry.json` 和 `runs/tag_020_retry_diagnostic_status.json`。

### NDEF 失败的底层诊断（2026-09-15 09:50）

保持原扫描参数和硬件，C3 添加只在 APDU 失败时输出的 `apdu_failure`：
命令 INS/P1/P2、transport_ok、PN532 原始低 6 位错误码、可用时的 APDU status_word。
主机阶段错误另用 0x100–0x103，避免把控制器无线错误和主机收发失败混为一谈。
编译和烧录通过；sendCommandCheckAck 源码已确认会等待 ACK 后响应就绪，
不能将当前错误归因于“没有等待 ACK 后响应”。

新增诊断后的采样（日志 `runs/nfc_web_20260915_095043.jsonl`，启动后约 35 秒采样等待结束时）：
74 次完整 NDEF 成功，32 次正文读取失败。32 次 APDU 错误分别为 PN532 0x02 CRC 错误 26 次、
0x01 标签响应超时 4 次、0x03 奇偶校验错误 2 次，未得到 APDU 状态字。
NXP UM0701-02 表 13（PDF 第 67 页）定义这些状态为控制器报告的无线接收错误。
因此该段失败不是应用层 NDEF 格式解析失败；天线/调谐/耦合/干扰与射频会话时序仍需区分，
尚无同一 Tag 接/断电容对照证据，不能认定 220 pF 是根因。

## 等待实验室期间的软件完善（2026-09-15）

- 页面 NDEF 失败带上对应一次 APDU 的底层原因（CRC/奇偶/超时/位冲突等），诊断在下一次读取或扫描中断后清除；补充 NLEN 中文说明。
- BLE 主动清理连接不再用“连接已断开”覆盖身份核对的真实错误。ATT 0x0F 显示加密未完成，未据此断言旧密钥失效；确有旧配对错误时提示当前设备名称，避免指向另一块板。
- 连接核对完成时显示 BLE 回读的电压/估算电量/传感器状态；断开不保留成实时数据。移除页面要求 USB 供电的过时提示。
- `tools/check_nfc_window.py` 为只读采样，按目标身份/UID 汇总、记录接线条件与扫描设置、排除另一颗球，重启或无读数不判通过。
- 35 项相关测试通过；真实页面 390 px 无横向溢出、无 JS 错误。
- XIAO 加密连续 8 秒重试均返回 ATT 0x0F，证据 `runs/xiao_encryption_diagnostic.json`。
  对照 v0.2.6 符号表经板载调试口仅读取 0x20006120 起 5 个状态字，配对失败计数 20→21，配对成功 0、安全请求返回 0、安全错误 4（AUTH_REQUIREMENT），连接期间安全等级 1。
  这说明安全协商未完成，未读取密钥或擦除配对，也未降低安全要求；尚待解决。此调试操作不是休眠/功耗测试。
- 新工具实跑 30 秒未观测到 XIAO UID，报告 `runs/xiao_nfc_controlled_window_20260915.json` 明确 `valid_observation=false`，不作为性能结果。
- 人工实验步骤和采样命令见 `docs/hardware/NFC_CAPACITOR_AB_TEST.md`。电容未改动，当前仍不能归因电容。

## XIAO BLE 加密恢复成功（2026-09-15）

macOS 配对列表原先仅有原版 Tag，未保留 XIAO；XIAO 安全错误为 AUTH_REQUIREMENT。
与设备保留旧配对、拒绝新的 Just Works 覆盖相符；XIAO 和原版 Tag 的 SC/防覆盖配置一致。
用户确认 XIAO 一直在原位，恢复前两次完整 NFC 身份等待超时，未发送清理命令；
不能将这些超时归因为用户拿走。之后确认 XIAO BLE 广播存在、NFCT 数据计数增长，再试 NFC 恢复成功。

使用已有身份锁定的 NFC 迁移流程，对 XIAO 4d53cd7b5c288607 写入一次命令，清理该球旧 BLE 配对。
固件仍为 0.2.6，nfc_migrations=1、nfc_migration_commands=1、nfc_migration_error=0，
新配对成功、BLE security_level=2、安全错误归零，macOS 重新出现 PuttTrack-4d53cd7b 配对。
历史配对失败计数 21 不会因成功清零，不能将累计值当成恢复后的新失败。
独立断开重连后 10 秒 IMU：501 帧、50 Hz、0 序号断点、0 无效样本、auto→auto。
证据：`runs/xiao_nfc_repair_third_20260915.json`、`runs/xiao_recovered_macos_pairings.json`、
`runs/xiao_post_pair_recovery_motion_20260915.json` 和同名 JSONL。
没有修改 XIAO 固件或降低 BLE 加密要求；本次没有重启 XIAO，因此不新增跨重启持久化测试结论。

为复用修复流程，增加 PN532 `nfc_service` 维护构建，成功读卡后提供 1000 ms 命令窗口；默认高速构建仍拒绝迁移写入。
工具等待有效完整身份（失败的 RF 读取不授权写入），BLE 回读额外校验安全等级。22 项相关测试通过。
维护和默认固件均编译烧录通过；恢复后已重新烧录默认高速只读模式并重启网页。

## 显示与单洞链路复核（2026-09-15）

当前 XIAO 无电池，但 USB 下 BAT 端约 4.046 V 曾显示成 84%，容易被理解成电池实测剩余量。
页面现将 battery_presence_known 纳入回读；未确认电池接入时只显示 BAT 端电压，不显示 SOC 百分比。
该字段未上报时也按未知处理；断连后不把旧值显示为当前连接状态。

正常连接但未开局时，IMU 区显示“BLE 已连接，开局后启用采样”，不再沿用断连/数据中断提示。
加入最近 60 秒按设备 ID/UID 分开的统计；严格有效 NDEF 才绑定 UID，失败仍计入对应 UID，
不同球不混算，旧样本到期移除。累计卡片明确标注所有设备，避免切换球后误用累计率。

41 项相关测试通过；页面 390 px 无溢出、无 JS 错误，未知电池不显示 84% 的浏览器检查通过。
XIAO 实际单洞链路检查：10 秒 488 帧、约 50 Hz、零序号断点、零无效样本、实验计杆 0，
检查局自动取消且 auto→auto 恢复。没有模拟入洞或生成成绩。
证据：`runs/xiao_single_hole_after_ui_fixes_20260915.json`。
真实击球识别准确率、电容对照、实际光电入洞和最终电流仍未验证。
# 2026-09-15 XIAO temporary NFC read LED

Installed and confirmed signed XIAO firmware 0.2.7 over encrypted BLE after USB
was reconnected. Onboard `led0` pulses for approximately 150 ms on the tag-side
NDEF last-byte read event, at most once per second. It is not a reader CRC or BLE
success indicator. Original Tag configuration does not enable this feature.

Verification: `runs/xiao_027_confirmed_images.json` shows 0.2.7 active/confirmed;
`runs/xiao_027_led_verified.json` reports 148 NDEF read events, 24 LED pulses,
LED error 0 and BLE security level 2. These are firmware/GPIO operation counters,
not visual observation of the LED. `runs/xiao_027_motion.json` passed with 502
samples at 50 Hz, no sequence gaps or invalid samples, and auto policy restored.
Dashboard recognition also completed with firmware 0.2.7. Intermittent NFC read
timeouts still occurred; this indicator does not fix or certify RF reliability.
Battery-only boot/wake and consumption remain unverified by this USB-connected
check. Disable `CONFIG_PUTTTRACK_NFC_READ_LED` for final power measurements.
# 2026-09-15 Original Tag NFC read LED (0.1.21)

Extended the shared NFC indicator to the original nRF54L15 Tag. Its `led0`
is the blue user LED (active-low P2.09), with the same 150 ms pulse and 1 Hz
maximum rate as XIAO. NFC service builds enable the option; non-NFC base
builds leave it disabled. XIAO remains on 0.2.7.

Signed BLE OTA installed 0.1.21 on `f383571202836e6f` and confirmed the active
image (`runs/tag_021_confirmed_images.json`). A 10-second IMU check passed with
502 samples at approximately 50 Hz, zero sequence gaps/invalid samples and
auto policy restored (`runs/tag_021_motion.json`). After reset, encrypted BLE
restored at level 2 with zero new pairings/failures. First status recorded
two NDEF read events and two LED pulses, LED error 0, and healthy sensors
(`runs/tag_021_first_status.json`). Counters verify firmware triggering, not
visual LED observation. This change does not certify reader-side RF reliability
or repeat the earlier System OFF endurance tests. Disable the LED for final
power measurements.


## 2026-09-15 球内、纯电池实测基线

用户确认原版 Tag 与 NFC 天线已装入球内、纯电池供电；随后确认球放在发球垫中央保持不动、其他标签已拿远。未改变电容或射频参数。

固定条件 60.211 秒：检测到目标后的 191 次事务中，162 次完整 NDEF 成功、29 次失败，完成率 84.82%，平均 2.69 次完整读取/秒，读取器重启 0 次。观察开始至首次成功 13.03 秒，这不是从物理放球开始计时。无 UID 扫描不进入完成率分母。报告：`runs/tag_021_ball_battery_fixed_window.json`。之前位置未确认的观察单独保存，不能混入固定条件结果。

独立 BLE 检查：Tag 0.1.21，加密等级 2，配对失败 0；10 秒收到 501 帧、约 50 Hz，无序号断点或无效样本，boot_id 未变化，结束恢复 auto。电压有效样本 2820–2828 mV，不能据此估算续航；LED 触发计数 206→216，GPIO 错误 0。报告：`runs/tag_021_ball_battery_motion.json` 及同名 `.jsonl`。

结论：球内纯电池条件下 NFC、加密 BLE 和 IMU 均可工作，连续 NFC 仍有失败；未完成方向覆盖、球内 System OFF 唤醒、真实击球分类和真实光电入洞验收。优先固定条件排查 NFC，再做重复唤醒、姿态覆盖、真实击球与单洞闭环。当前光电心跳正常不能证明传感器已接线。


## 人工放球验收按钮

页面新增“放球验收 · 人工配合”。先拿离球，等待至少 3 秒无有效 NFC 身份，点击“开始本次放球”后立即放回。计时从服务器接到按钮请求开始，包含用户放球动作和网络延迟边界，不是精确物理接触计时。2 秒内为目标，3 秒内新的 NFC 身份与 BLE 核对完成为通过；无 NFC 也计超时，晚到结果不改判，成功后漏读不改判。

目标身份锁定为最近核对过的球（尚无历史身份时采用本次首次有效身份）。正在进行游戏或休眠唤醒时不能开始。每次单独点击，建议 30 次；重复请求 ID 不重复创建，取消单独列出、不进入成功率。刷新保留当前服务内记录；重启服务另起一组，原始开始/结果事件保存在 `.recognition.jsonl`。导出按钮包含本服务全部人工测试。自动 NFC 连读统计仍供诊断，不作为人工放球验收分母。

验证：33 项相关测试通过，覆盖完全无 NFC 超时、过期 BLE 结果、晚到成功不改判、成功后中断不改判、错误身份、重复开始、取消和游戏互斥。界面检查未执行真实人工放球，不计入验收次数。


## 球内放球体验：用户约 100 次测试反馈

用户报告约 100 次实际放球，约 99% 可识别，偶发未识别可通过微调角度恢复；接受此体验作为当前原型的放球识别阶段通过条件，不再以连续 NFC 100% 读取为目标。当前日志 `nfc_web_20260915_121838.recognition.jsonl` 记录 100 次自动识别全部完成，首次有效 NFC 后至 BLE 核对平均 1560.07 ms、最长 1926 ms；本服务人工按钮记录为 0。自动统计不覆盖首次有效 NFC 前的等待或完全未识别的放球，不能独立证明物理放球 99/100，99% 为用户实测反馈。历史其他服务的人工测试不混入本组。证据：`runs/ball_placement_100_review.json`。

后续灯光交互需求：黄色待机、识别中呼吸/闪烁、应用确认成功后常亮；超时提示轻转小球。成功灯应由 NFC 身份与加密 BLE 核对后的应用确认驱动，现有 NDEF 读取闪灯不等于完整应用成功。此次仅记录需求，未实现或升级灯光固件。接下来推进球内休眠唤醒和真实击球/单洞闭环；角度敏感性作为已知体验边界保留。


## 球内纯电池自动休眠唤醒与发球垫灯光预览

Tag 0.1.21 保持球内、垫上，PN532 软件断场/重新开场进行 3 轮 System OFF 测试，全部通过。每轮休眠后 5 秒扫描未发现该 Tag 广播，唤醒后 boot_id 改变且报告 NFC System OFF 唤醒，加密连接恢复，无需重新配对。开场到 BLE 核对分别 3205、3204、3559 ms；随后每轮 5 秒 IMU 分别 251、250、250 帧，检查通过，恢复 auto。射频场已恢复。此测试不是物理拿离放回计时，也不是低功耗电流测量。完整证据 `runs/tag_021_ball_sleep_cycles.json`。

用户确定灯光放在发球垫上，球内保留 NFC 读取闪灯。页面新增发球垫灯光预览，`/api/status.tee_indicator` 提供 mode/color/effect/title/hint 状态；待机黄、识别中呼吸、NFC/BLE 加密核对完成绿常亮，持续未完成提示轻转小球。硬件型号/GPIO 尚未确定，`hardware_connected=false`，未发送任何实体灯驱动命令、未改球固件。页面成功灯使用实时核对状态，人工验收历史成功不冒充当前可开局。实体灯驱动接入后应采用相同状态语义。

39 项相关测试通过；手机视口页面检查无 JavaScript 错误与横向溢出。后续仍需真实推杆验证 IMU 计杆、光电硬件信息/接线和真实入洞；软件状态心跳不能证明光电已安装。


## 用户单洞试玩记录核对

核对 `runs/nfc_web_20260915_124554.hole.jsonl`：原版球内 Tag 0.1.21 完成两局，分别 2 杆与 3 杆，五次计杆来源均为 `imu_experimental`，没有手动补杆事件。两局分别记录 1824、1218 条 IMU 样本，均正常结算保存。快照：`runs/single_hole_user_review_status.json`。用户反馈“差不多没问题了”；日志确认自动记杆流程，但没有独立视频或逐击标注来证明每次对应真实击球、无漏判/误判。

两局入洞来源都是 `simulation`，因此已跑通 NFC/BLE 识别→IMU 实验记杆→模拟入洞→结算的原型闭环；真实光电入洞和实体发球垫指示灯仍待硬件接入验证。不将这些结果表述为真实光电全链路验收完成。


## XIAO 装球壳后的电池测试

用户确认 XIAO 已装入球壳，电脑只枚举到 PN532 C3 USB。首次页面完成 XIAO 0.2.7 NFC/BLE 核对（有效 NFC 后 1674 ms），电压回读约 4105 mV；不能据此独立推断电池容量或续航。快照 `runs/xiao_enclosed_initial_dashboard.json`。

随后自动 RF 断场/开场的 3 轮 System OFF 测试全部通过，验证启动标识变化、NFC 唤醒标志、加密恢复和每轮唤醒后 5 秒 IMU。结果：[{"cycle": 1, "passed": true, "rf_to_ble_ms": 2629, "nfc_wake": true, "security": 2, "pairings": 0, "battery_mv": 4105, "samples": 251}, {"cycle": 2, "passed": true, "rf_to_ble_ms": 2732, "nfc_wake": true, "security": 2, "pairings": 0, "battery_mv": 4106, "samples": 251}, {"cycle": 3, "passed": true, "rf_to_ble_ms": 2629, "nfc_wake": true, "security": 2, "pairings": 0, "battery_mv": 4104, "samples": 251}]。完整报告 `runs/xiao_027_enclosed_battery_sleep_cycles.json`，射频场已恢复，页面已恢复。此项为自动功能验证，不替代物理多姿态放球、真实击打计杆或电流测量。球内 XIAO 后续先做人工放球 20–30 次，再做实际推杆；未改电容或升级固件。


## XIAO 球内 50 次放球用户测试

用户报告 50 次实际放球全部识别、几乎无错误。当前服务自动识别统计 50/50 完成，记录身份全部为 XIAO `4d53cd7b5c288607`、固件 0.2.7；有效 NFC 后至 BLE 核对平均 1638.1 ms、最长 2753 ms。快照 `runs/xiao_enclosed_50_review.json`；原始日志 `runs/nfc_web_20260915_130635.recognition.jsonl`。人工按钮统计为 0，因此日志时间不包含首次有效 NFC 前等待，实际 50 次放球全部成功以用户观察为依据。

结合球内电池供电自动休眠唤醒 3/3 通过，此配置按当前原型的放球体验要求通过，保持现有电容/天线配置，不为了连续读取率调整。下一步用 XIAO 实际推杆核对自动计杆；真实光电与实体指示灯仍需接入。50 次成功不代表所有姿态或长期使用永不失败。


## XIAO 冲击候选未计杆诊断（待动作标注）

回放局 `c9466e33d42e44a1b5fee7d24b6c1f82`：1100 帧连续，无无效样本；6 次冲击候选、2 次计杆。候选约在采集开始后 1.98、5.861、9.38、12.68、15.88、18.36 秒。第 1、3、6 个候选因单帧加速度模长 <3 m/s² 被立即取消，第 2 个因角速度短暂降至阈值以下重置连续运动计时，最终 700 ms 超时。第 4、5 个通过。不能单凭这些信号确认物理自由落体或真实推杆。

离线试验：低加速度需持续 60 ms 才取消、运动支持 160 ms 容忍短暂 40 ms 间隙，XIAO 回放得到 6 次；但原版 Tag 两局从 2/3 次变为 3/4 次，新增候选未标注，不能宣布精度改善。候选实现仅存于 `runs/stroke_review/bench_stroke_candidate.py`，未替换应用识别器、未重启服务或改历史成绩。等待用户实际推杆次数及拿放/碰撞说明再决定 XIAO 专用调整。诊断与回放证据 `runs/stroke_review/xiao_replay.json`、`runs/stroke_review/compare.json`。


## 新一局用户确认 6 杆：漏记定位

局号 `305f48879be54e0b8db0960db3e23534`，用户明确实际打了 6 杆。1187 帧连续且有效，六组冲击约在采集开始后 3.08、6.48、10.86、14.22、17.70、19.56 秒；旧规则仅记录第 2、3、5 组。第 1 组单帧低加速度取消；第 4 组冲击前 260 ms 轻微角运动提前解除 armed；第 6 组击打前连续静止样本跨度约 180 ms，不满足 600 ms 重新准备条件。上一轮离线候选修订仍仅计 3 次，因此不能宣称该方案已修复。应用规则和历史成绩未修改。证据 `runs/stroke_review/xiao_labelled_six_diagnosis.json`。下一步需区分轻微晃动与拿放，完善候选/重新准备状态；控制每杆前静止 1 秒可先隔离重复准备问题，不以强行凑满 6 次作为准确性证明。


## XIAO 专用实验计杆 v1 已接入

用户授权处理漏杆后，新增 `bench-stroke-xiao-v1-unvalidated`，按实际样本 `lsm6ds3tr-c-single` 选择；原版 Tag 继续 v0，硬件布局切换清空识别状态。首次要求静止 600 ms，后续在已记杆 1.5 秒后可用 160 ms 新静止重新准备；准备状态容忍有限轻晃（角速度 <1 rad/s、加速度距重力 <3 m/s²，连续非静止最长 300 ms）。冲击阈值仍 >14 m/s²。候选窗口 700 ms，要求有效运动支持累计 160 ms，容忍最多 80 ms 的短暂中断；连续低加速度至少 80 ms 才取消。数据中断/无效值重置，持续普通移动与无运动确认不计杆。这些是依据少量样本调整的实验参数，不是已验证量产模型。

用户明确 6 杆的最新局回放由 3→6，六次输出均位于对应冲击后 700 ms 内；前一局由 2→6（无独立总杆数标注）；原版 Tag 两局仍 2/3 杆。结果 `runs/stroke_review/deployed_xiao_v1_replay.json`。最新 6 杆采样作为回归夹具保留；这是调参样本回放，不能视为独立准确率评估。34 项相关测试通过，包括持续低加速度、普通移动、持续晃动、冲击后无运动、连续碰撞、冷却期与数据中断；真实拿放负例仍需补测。

页面显示当前模型，局日志新增 `imu_phase` 记录以解释后续候选取消原因。服务已更新，无球固件升级，历史成绩未改写。下一局 XIAO 使用新规则；需用户实际再打 6 杆并补充拿放对照，检查计数及误触发。


## XIAO v1 新一局 5 杆现场反馈

局 `891cbe90a789420392d3d93a78904ad3` 使用 XIAO v1，日志 5 个冲击候选均确认，5 次计杆均为 IMU 实验来源，无手动补杆；1733 帧无序号断点或无效样本，模拟入洞完成。用户报告实际约 5 杆，其中一次有点问题，具体表现未标注，不能仅凭总数一致判定无漏记/误记。另有轻晃/普通移动阶段，不能直接认定其中某次对应用户所说问题。证据 `runs/xiao_v1_five_review_status.json` 和 `runs/nfc_web_20260915_132644.hole.jsonl`。优先补真实拿放负例与轻/正常推杆对照；两套 NFC 配置暂保留，电容 A/B 不是修复 IMU 计杆的手段，后续如比较需同一 Tag 同姿态固定条件并单独计放球延迟和调整角度次数。


## 光电已有正式使用项目：状态更正

用户确认 Golf Up 的三个光电项目已正式投入使用，光电硬件本身已验证。已检查 `/Users/pp/Desktop/文档/golf up/README.md` 的“8DI 光电传感器触发”及 `src/waveshare_8di8do/main.cpp`：隔离数字输入、下降沿中断捕获、主循环处理，DI1-DI3 已有音效/奖励与灯光动作。正式现场运行情况来自用户确认，不能把源代码检查表述为本次现场验收。

因此撤销“光电硬件方案尚需从零验证”的待办。当前 PuttTrack 可复用成熟光电方案；此前两颗球的本地单洞结果仍为模拟入洞，尚未记录 Golf Up 实际光电事件接入本项目局号并完成结算。剩余是系统集成确认与实体灯安装，不是光电可行性研发。按当前单球原型范围、暂不以拿放误触发为验收条件，独立核心研发与当前台架能完成的验证基本完成；不要求为此拆 Tag 电容。
