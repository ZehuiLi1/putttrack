# IMU 全量状态发现结果 — 2026-09-04

## 结论

失败的 GitHub Actions 分析链已经修复并完整重跑。当前结果支持继续开发一个
**非权威、fail-closed 的拿起候选检测器**，但不支持把 IMU 直接接入处罚或计分。

本次从原始 JSONL 审计了 233 个去重 episode，其中 121 个进入探索性多分类
比较；全部原始实验文件都有 manifest，特征提取错误为 0。

## 冻结 V0 回放

`pickup_detector_v0_stationary_start` 严格从
`configs/research/pickup_detector_v0.json` 读取阈值，输出只有：

- `PICKUP`
- `NOT_PICKUP`
- `UNKNOWN`

72 个 precision 批次 episode 中有 3 个因 `INVALID/MIXED` 质量排除；剩余
69 个中只有 40 个可以评分，29 个 fail closed 为 `UNKNOWN`。40 个可评分样本
得到 TP=20、TN=20、FP=0、FN=0。

这个 100% **不能解释为产品准确率**：

- 10/10 边轨碰撞都因 BMI270 gyro clipping 成为 `UNKNOWN`；
- 轻推杆中 9 个干净 episode 因 gyro clipping 成为 `UNKNOWN`；
- 10/10 滚动中拿起按 V0 定义为不支持，成为 `UNKNOWN`；
- 数据仍主要来自同一颗 Ball、同一操作者和同一天；
- 没有独立视频/物理事件真值。

V0 因此只能产生研究证据。它证明当前静止起步拿起和部分负例有明显可分性，
也同时暴露出最重要的工程缺口：高动态事件在当前 50 Hz/gyro 量程下大量进入
UNKNOWN。

## 探索性状态模型

- 8 类 episode 留一验证中，Extra Trees 的 macro-F1 为 0.725；
- 按 session/manifest 留组时，只对训练中出现过的类别计分，准确率降到 0.68；
- 21 个测试 episode 的类别在对应训练组中从未出现，不能作为普通错误统计；
- rolling disruption 四类探索中，最佳 macro-F1 为 0.813。

这些结果说明层级状态机加小型分支分类器值得继续研究，但也明确否定了现在部署
一个平坦八分类模型或神经网络的做法。

## 修复内容

- 将五段压缩 Base64 payload 恢复为可审查的
  `tools/imu_state_discovery.py`；
- 兼容 NumPy 2.x 移除 `np.trapz`；
- 修复 scikit-learn 1.8 二分类标签 dtype 崩溃；
- 无特征结果时输出明确失败文件，不再二次触发 `KeyError`；
- 边轨碰撞和台阶跌落作为 V0 硬负例，不再误判成“不支持路径”；
- 只让 `rolling_pickup` 按冻结范围返回 `UNKNOWN`；
- 修复静止基线“代码计算 RMS、报告声称标准差”的不一致；
- 修复批次说明提到一次 obstacle、却把整批样本标成 MIXED 的污染；
- 固定完整依赖版本并新增研究回归测试；
- workflow 直接运行正常源码，不再在 CI 中临时解压隐藏程序。

## 可重复运行

```bash
python -m pip install '.[research-imu]'
python -m unittest discover -s tests_research -p 'test_*.py' -v
python tools/imu_state_discovery.py \
  --root . \
  --out artifacts/imu_state_discovery_20260904
```

## 版本化输出

- `dataset_audit.json`：数据完整性和来源审计；
- `frozen_v0_summary.json`：冻结 V0 主指标；
- `frozen_v0_reconstruction_replay.csv`：逐 episode 判定和 UNKNOWN 原因；
- `flat_multiclass_benchmarks.csv`：八类探索性模型比较；
- `path_a_benchmarks.csv`：静止起步 pickup 分支探索；
- `path_b_benchmarks.csv`：滚动扰动分支探索；
- `leave_group_out_summary.json`：留 session/manifest 组挑战；
- `ARCHITECTURE_RECOMMENDATION.md`：架构结论和产品验证门槛。

完整 2 MB 特征矩阵和逐模型预测由 GitHub Actions artifact 保存，不在文档目录
重复提交；这里保留可审查的主结论与逐 episode V0 回放。

## 下一步

1. 保持 V0 阈值冻结，不因本批结果回调。
2. 将拿起 evaluator 拆成 `src/putttrack/motion/pickup.py` 和独立 CLI，补原始记录
   fixture、延迟和置信区间；本次 discovery 工具不直接接 Gameplay。
3. 冻结下一版后，用第二颗 Ball、不同日期/操作者/表面做盲测。
4. 对边轨碰撞、轻推杆等 gyro clipping 事件，提高采样率并审查量程/FIFO，不能把
   `UNKNOWN` 当成负例。
5. 产品闭环优先继续 Tee PN532 + Cup 光学候选/PN532 身份确认。

