# 从这里开始：计杆 + 拿起 Shadow V1 当前交付状态

2026-09-05。本文件与 `validation.json` 优先于初始 README 中任何“可上球”的笼统措辞。

## 已完成

- 保留 BMI270 + ADXL367，编写独立 C 候选引擎并接入 Tag 实际采样路径。
- 重放 236 份去重原始 capture、168,142 条 tag_motion；冻结 V0 和 main 未修改。
- 保存初始/最终逐回合结果、完整事件日志、原始 SHA-256、反例和开发过程。
- 200 ms 保存初始击球 proposal，约 1 s 经拿起路径否决后才增加击球候选计数。
- 完成独立协议、16 条事件日志、原始数据与候选结果联采、真值复核和事件时刻评估工具。
- Host 272 项测试、11 项 verifier 检查通过；38 项为新增引擎/协议测试。
- 同一完整原始数据重放两次，CSV/JSON/JSONL 一致。

## 尚未完成——现在不要刷本候选

**还没有通过最终目标固件构建验收，没有设备签名密钥对应的发布包，没有实球 test-boot/action PASS。**

初次 CI 的 NCS 绿色状态无效：容器 ENTRYPOINT 导致编译脚本未执行。已修正，并增加真实 ELF/BIN/map/配置/函数符号检查。实际编译随后暴露可选函数/变量条件编译问题；修正后，最新检查仍在 MCUboot 分区对齐断言处失败。

不能为消除该报错而任意移动已确认设备的分区、修改 bootloader 信任或禁用断言。应先保存并对照生成的 MCUboot/application `zephyr.dts`、`.config`、partition-manager 输出与现有已确认镜像的分区。目标构建问题解决、真实产物验证通过之后，才允许使用原设备签名密钥构建 signed application BIN，并沿用原有 MCUboot test/rollback。

**不使用 CI 一次性密钥镜像，不刷 first-install HEX，不自动 image-confirm。**

当前研究电脑没有连接该球的 HCI/串口，因此本次没有向球写入任何镜像或命令。

## 回放究竟支持什么

10 条干净轻推和 10 条推球后撞栏回合各产生一次击球候选；20 条静止拿起/拿起后放落回合产生拿起嫌疑；10 条严格不离地对照没有误发击球/拿起候选；86 条正式滚筒没有击球候选。

以上是同一批已看过数据上的开发回放，缺少独立接触时刻，不能写成商业准确率。

必须保留的限制：两条人工手推滚动都误发击球候选；10 条滚动拿起不被当前静止起始路径支持；滚动中二次接触不能直接决定是碰撞还是第二杆。归档正常推杆的 8/10 输出不代表两次已证实漏检——另两条原本已标为无动作/时序无效，详见 `AUDIT_ADDENDUM.md`。

`PICKUP_SUSPECTED` 不是作弊定论。取球、放球或球洞结束后的拿起是否违规，需要玩法上下文；球端不自行处罚。`STROKE_LIKE_CANDIDATE` 不是正式杆数。

## 唯一下一条执行链

1. 关闭目标构建/分区配置问题，验证精确源代码下真实 ELF、签名应用 BIN、配置和链接映射。
2. 用原设备密钥构建 `0.1.19` 测试包，核对设备身份、包哈希和槽位；test 启动，保留 `0.1.17` 回退路径。
3. 用 `tools/test_ball_stroke_pickup_v1.py` 同时保存 raw IMU 和 MCU 事件，先每种 3 次：单杆、停球后二杆、一杆多次碰轨、另一球撞击、手推、拿起、不离地对照。
4. 用独立视频/人工记录填写真实 putter/pickup/collision 时刻，运行 `review_shadow_trial.py` 和 `evaluate_shadow_trials.py`。
5. 分别报告多计、漏计、待判、日志缺失、时间误差；不因候选总数凑巧相等就算通过。新 holdout 不用于现场反复调阈值。

全部构建、采集和评估命令见 [README_CN.md](README_CN.md)。测试工具已经提交，但它们不能替代本文件中的“目标构建通过”前置条件。

## 文件导航

- [算法、结果与测试命令](README_CN.md)
- [最终回放摘要](replay_v1/summary.json)
- [完整逐回合结果](replay_v1/capture_results.csv)
- [完整事件日志](replay_v1/events.jsonl)
- [初始实现对照](replay_initial/summary.json)
- [开发过程](PROCESS.md)
- [分母与构建审计补充](AUDIT_ADDENDUM.md)
- [验收状态](validation.json)
