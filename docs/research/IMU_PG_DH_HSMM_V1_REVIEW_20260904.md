# PG-DH-HSMM V1 分支审查 — 2026-09-04

审查对象：`research/imu-pg-dh-hsmm-v1-20260904`，远端 HEAD `7252876`。

## 当前判断

这个分支方向正确，值得作为下一阶段基础，但**暂不直接合并或接入 Gameplay**。
它新增了：

- 无第三方依赖的冻结 pickup V0 原始 JSONL evaluator；
- UNKNOWN-aware CLI 和 Wilson 95% 区间；
- physics-guided dual-head recognizer 与 explicit-duration HSMM 原语；
- 分组留出 logistic emission trainer；
- 10 个 pickup/recognizer 单元测试。

本地复跑 10/10 测试通过。用七个 precision manifest 实测 V0 CLI：

- metric eligible：60；
- definitive：41；
- UNKNOWN：19；
- TP=20、TN=21、FP=0、FN=0；
- definitive coverage：0.683，Wilson 95% 区间约 0.558–0.787；
- false-pickup rate 为 0，但 95% 上界仍约 0.088。

结果与独立 discovery 回放一致，说明 evaluator 主体计算方向可信；它仍只是同日、
同操作者、同一 Ball 的研究结果。

## 合并前必须补齐

1. **manifest/capture 标签一致性**：当前 `evaluate_pickup_v0()` 优先采用
   `manifest_label`，但没有检查它与 capture 内唯一 `episode_label` 是否一致；
   标签错配必须返回 `UNKNOWN`。
2. **fail-closed 测试矩阵**：补缺失 GO、多个 GO、marker/window 不一致、时间回退、
   传感器 invalid/error bits、capture result 缺失/失败、异常采样率、静止基线不足/
   不静止、特征窗口不足和 manifest/capture 标签错配。
3. **真实数据回归 fixture**：现有 pickup 测试主要是合成数据；需要固定少量脱敏原始
   JSONL fixture 和期望特征/判定，防止公式重构漂移。
4. **配置单一来源**：说明 `pickup_detector_v0.json` 与 eval profile 的职责边界，
   保证阈值不会在两个文件中无版本约束地漂移。
5. **Recognizer 端到端验证**：当前 HSMM 测试证明原语可运行，但尚未证明训练器输出、
   recognizer 输入 schema、模型 artifact 和 CLI 回放形成一个可复现闭环。
6. **权限边界**：持续断言 `authority=false`，不导出 Gameplay 事件，不把 UNKNOWN
   变成 NOT_PICKUP。

## 建议处理顺序

先补 1–3 并跑全仓库回归，再生成一次真实数据 V0 报告；随后验证 trainer 到
recognizer 的 artifact 闭环。只有这些通过后才考虑把该分支合入 `main`。独立日期、
第二操作者、第二颗 Ball 和不同表面的盲测仍是产品声明前的必要门槛。
