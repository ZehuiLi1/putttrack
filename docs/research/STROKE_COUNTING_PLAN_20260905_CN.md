# PuttTrack 计杆优先工程计划

日期：2026-09-05。状态：软件准备完成，真实计杆检测器尚未建立。

## 产品目标

首个玩家价值是屏幕持续、清楚地显示当前玩家本洞已确认杆数。目标事件定义：

- 球杆与当前研究球发生一次真实接触，计一杆；
- 球撞边轨、台阶、障碍或另一颗球，不新增杆数；
- 另一颗球撞到静止研究球，研究球计零杆；
- 手推、摆球和拿起不属于计杆事件；
- 同一杆后的多个振动峰、弹跳和碰撞不能重复计数。

防作弊、拿起处罚和运动来源细分不在本阶段计杆闭环内。未知证据保持 UNKNOWN，
不能静默当作零杆或确认一杆。

## 已有与缺失

Gameplay Engine 已实现幂等 STROKE_CONFIRMED、杆数累计、审计和 SSE 通知。
Hole 页面现在持续显示当前玩家本洞杆数和各玩家本洞杆数。

现有 11 条轻推和 10 条撞栏只用于过去的 pickup/quality 研究，不能给出
“球杆击球 vs 碰撞”的准确率。当前没有通过独立真值验证的 stroke detector，
MotionObservation 的 IMPACT_CANDIDATE 仍保持 pending，不会改变杆数。

## 数据矩阵

现场采集界面新增以下成对场景：

| 场景 | 计划杆数 | 主要检验 |
|---|---:|---|
| 轻推一杆 / 正常一杆 | 1 | 基本召回和延迟 |
| 停球后第二杆 | 2 | 重新武装、连续计杆 |
| 滚球中第二杆 | 2 | 接触事件与普通滚动扰动 |
| 一杆后多次撞栏 | 1 | 碰撞不得重复计杆 |
| 被另一颗球撞到 | 0 | 外部碰撞不得计杆 |
| 手推对照 | 0 | 运动开始不等于球杆击球 |

`planned_strokes` 只描述实验计划。每条 capture 必须用
`tools/review_stroke_capture.py` 写独立的实际杆数和接触时刻；没有人工/视频
复核的记录不进入指标。原始 capture SHA-256 被写入 review，防止错配。

示例：

```bash
python tools/review_stroke_capture.py runs/example.jsonl \
  --session-id 20260906-a --scenario stroke_two_after_stop \
  --actual-strokes 2 --contact-times 1.20,5.45 \
  --truth-source video_review
```

候选检测器产生逐 episode 杆数后，用 `tools/evaluate_stroke_counts.py` 报告：
覆盖率、整段杆数完全一致率、多计杆数、少计杆数、UNKNOWN，以及 scenario 和
session 分组。杆数总量相等可能掩盖“一次漏检 + 一次误报”，所以事件时刻误差
必须另外审计。

## 实现顺序

1. 按上表采集带 GO 的原始 IMU，并记录实际球杆接触时刻；优先视频真值。
2. 先画出首次球杆接触、后续滚动和碰撞的时序特征，检查 50 Hz 和当前量程是否
   保存了足够证据。
3. 建立 research-only stroke candidate：需要接触瞬态、接触前状态、接触后运动
   变化、refractory/hysteresis 和质量门；保持 authority=false。
4. 按 session/scenario 留出评估，特别报告一杆多碰撞中的多计和两杆中的少计。
5. 通过独立日期/操作者/表面验证后，由 Edge 把候选转为 STROKE_CONFIRMED，
   Gameplay Engine 继续作为唯一杆数权威；早期现场保留人工纠错。

当前停止线：没有新原始计杆真值前，不为碰撞分类宣称准确率，不把已有 pickup
阈值改名为计杆规则，也不把 motion candidate 直接接入玩家分数。
