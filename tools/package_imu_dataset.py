#!/usr/bin/env python3
"""Package every unique raw Tag IMU capture with provenance and model notes."""

from __future__ import annotations

import argparse
import collections
import csv
from datetime import date
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]
MOTION_RECORD = "tag_motion"
ACCEL_CLIP_MICRO_MS2 = 153_768_272
GYRO_CLIP_MICRO_RADS = 34_208_453
ADXL_CLIP_MICRO_MS2 = 19_221_034


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "dist"
        / f"putttrack_imu_dataset_{date.today().strftime('%Y%m%d')}.zip",
    )
    return result


def norm_micro(values: list[int]) -> float:
    return math.sqrt(sum(value * value for value in values)) / 1_000_000.0


def load_jsonl(path: Path) -> tuple[list[dict[str, object]], int]:
    records = []
    malformed = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(payload, dict):
            records.append(payload)
        else:
            malformed += 1
    return records, malformed


def category_for(relative: Path, capture_status: str | None) -> str:
    text = relative.as_posix()
    name = relative.name
    if ".failed-" in name or capture_status == "FAIL":
        return "90_diagnostic_or_invalid"
    if "research_ball_r0_stationary/raw" in text:
        return "02_curated_stationary"
    if "research_ball_r1_manual_floor/raw" in text:
        return "03_curated_manual_floor"
    if name.startswith("roller-"):
        if name.startswith(("roller-matrix-", "roller-r2-", "roller-r3-", "roller-r4-", "roller-r5-")):
            return "05_roller_official"
        return "04_roller_preliminary"
    if name.startswith("field-") and "pickup_" in name:
        return "06_field_pickup"
    if name.startswith("field-") and "putt_" in name:
        return "07_field_putt"
    return "01_early_firmware_and_motion_tests"


def annotation_for(relative: Path, category: str) -> tuple[str, str]:
    name = relative.name
    if category == "90_diagnostic_or_invalid":
        if "125536-pickup_carry" in name:
            return "invalid_label", "完整静止窗口被标成 pickup_carry；仅用于失败恢复/负例研究。"
        if "go-handshake-smoke" in name:
            return "invalid_label", "GO 握手冒烟测试，全程静止；不能作为 pickup_drop 真值。"
        if "roller-r1-120rpm-3s-live-r02" in name:
            return "transport_failure", "实时滚轮捕获状态 FAIL；仅用于传输故障诊断。"
        return "diagnostic_only", "文件名或捕获结果标明失败；不要作为监督训练真值。"
    if "field-20260904-130555-pickup_carry" in name:
        run = name.rsplit("-", 1)[-1].removesuffix(".jsonl")
        if run == "r07":
            return "usable_with_timing_warning", "GO 前已有运动污染；拿起段仍可探索，不能当干净基线。"
        if run == "r09":
            return "usable_with_timing_warning", "动作开始约在 GO+6.7 s，明显晚于说明。"
        if run in {"r01", "r03", "r05", "r08"}:
            return "usable_exploratory", "动作接近窗口末端；静止尾段不足，适合拿起起点研究。"
        return "usable_exploratory", "最新人工拿起/携带/放下样本。"
    if "field-20260904-132804-1-putt_normal" in name:
        run = name.rsplit("-", 1)[-1].removesuffix(".jsonl")
        if run in {"r01", "r02", "r03", "r04"}:
            return "mixed_suspected_collision", "疑似推杆后碰到障碍物；可作 pickup 负例，不可当纯净推杆真值。"
        if run == "r05":
            return "invalid_no_motion", "全程静止，没有采到推杆。"
        if run == "r06":
            return "invalid_timing_or_action", "GO 前已有动作，GO 后形态也不像正常推杆。"
        if run == "r08":
            return "usable_with_timing_warning", "GO 前有干扰；GO 后滚动段可单独研究。"
        return "usable_clean_candidate", "当前最干净的正常推杆候选之一；仍缺视频真值。"
    if category == "05_roller_official":
        if "p180" in name or "n180" in name:
            return "fixture_limit_test", "±180 RPM 命令的故意量程边界测试，不能作无削顶幅值真值。"
        return "usable_fixture", "可用于受约束滚动、速度响应和传输研究；不是真实自由滚动语义真值。"
    if category == "04_roller_preliminary":
        return "preliminary_fixture", "早期滚轮调试数据；设备约束、命令和同步成熟度不一致。"
    if category.startswith(("02_", "03_")):
        return "curated_exploratory", "已有仓库内说明和派生分析；仍不是产品分类器验证集。"
    return "legacy_exploratory", "早期固件/动作探索；标签、窗口和同步规则随固件版本变化。"


def summarize(path: Path, relative: Path, records: list[dict[str, object]], malformed: int) -> dict[str, object]:
    motion = [record for record in records if record.get("record_type") == MOTION_RECORD]
    statuses = [
        record
        for record in records
        if record.get("record_type") in {"tag_status", "tag_status_final"}
    ]
    markers = [record for record in records if record.get("record_type") == "tag_episode_marker"]
    results = [record for record in records if record.get("record_type") == "tag_capture_result"]
    status = statuses[0] if statuses else {}
    final_status = statuses[-1] if statuses else status
    capture_status = str(results[-1].get("status")) if results else None
    category = category_for(relative, capture_status)
    quality, note = annotation_for(relative, category)
    times = [int(record["source_monotonic_us"]) for record in motion]
    sequences = [int(record["sequence"]) for record in motion]
    gaps = sum(max(0, current - previous - 1) for previous, current in zip(sequences, sequences[1:]))
    valid = sum(
        bool(record.get("adxl367_valid"))
        and bool(record.get("bmi270_valid"))
        and int(record.get("sensor_error_bits", 0)) == 0
        for record in motion
    )
    accel_norms = [norm_micro(record["bmi270_accel_micro_ms2"]) for record in motion]
    gyro_norms = [norm_micro(record["bmi270_gyro_micro_rads"]) for record in motion]
    active = [
        index
        for index, (accel, gyro) in enumerate(zip(accel_norms, gyro_norms))
        if abs(accel - 9.80665) >= 0.5 or gyro >= 0.25
    ]
    labels = sorted(
        {
            str(record["episode_label"])
            for record in records
            if isinstance(record.get("episode_label"), str) and str(record["episode_label"]).strip()
        }
    )
    duration = (times[-1] - times[0]) / 1_000_000.0 if len(times) > 1 else 0.0
    marker_offset = (
        (int(markers[0]["source_monotonic_us"]) - times[0]) / 1_000_000.0
        if markers and times
        else None
    )
    packaged = Path("data") / category / relative.name
    return {
        "source_path": relative.as_posix(),
        "packaged_path": packaged.as_posix(),
        "category": category,
        "quality": quality,
        "quality_note_zh": note,
        "episode_label": "|".join(labels),
        "capture_status": capture_status or "legacy_no_result_record",
        "motion_samples": len(motion),
        "duration_s": round(duration, 6),
        "observed_rate_hz": round((len(motion) - 1) / duration, 6) if duration > 0 else None,
        "sequence_gaps": gaps,
        "valid_fraction": round(valid / len(motion), 9),
        "first_active_offset_s": round((times[active[0]] - times[0]) / 1_000_000.0, 6) if active else None,
        "last_active_offset_s": round((times[active[-1]] - times[0]) / 1_000_000.0, 6) if active else None,
        "marker_offset_s": round(marker_offset, 6) if marker_offset is not None else None,
        "adxl367_clip_samples": sum(
            max(abs(int(value)) for value in record["adxl367_accel_micro_ms2"]) >= ADXL_CLIP_MICRO_MS2
            for record in motion
            if record.get("adxl367_valid")
        ),
        "bmi270_accel_clip_samples": sum(
            max(abs(int(value)) for value in record["bmi270_accel_micro_ms2"]) >= ACCEL_CLIP_MICRO_MS2
            for record in motion
            if record.get("bmi270_valid")
        ),
        "bmi270_gyro_clip_samples": sum(
            max(abs(int(value)) for value in record["bmi270_gyro_micro_rads"]) >= GYRO_CLIP_MICRO_RADS
            for record in motion
            if record.get("bmi270_valid")
        ),
        "device_id": str(status.get("device_id", final_status.get("device_id", ""))),
        "boot_id": str(status.get("boot_id", final_status.get("boot_id", ""))),
        "firmware_version": str(status.get("firmware_version", final_status.get("firmware_version", ""))),
        "stream_rate_hz_claimed": status.get("stream_rate_hz"),
        "malformed_json_lines": malformed,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "_source": path,
    }


def discover() -> tuple[list[dict[str, object]], dict[str, list[str]], int]:
    summaries = []
    duplicates: dict[str, list[str]] = collections.defaultdict(list)
    zero_motion = 0
    for root_name in ("experiments", "runs"):
        root = REPO_ROOT / root_name
        for path in sorted(root.rglob("*.jsonl")):
            records, malformed = load_jsonl(path)
            if not any(record.get("record_type") == MOTION_RECORD for record in records):
                zero_motion += 1
                continue
            relative = path.relative_to(REPO_ROOT)
            summary = summarize(path, relative, records, malformed)
            duplicates[str(summary["sha256"])].append(relative.as_posix())
            summaries.append(summary)
    unique = []
    seen = set()
    for summary in summaries:
        digest = str(summary["sha256"])
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(summary)
    return unique, {key: value for key, value in duplicates.items() if len(value) > 1}, zero_motion


def csv_text(rows: list[dict[str, object]]) -> str:
    public = [{key: value for key, value in row.items() if key != "_source"} for row in rows]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(public[0]))
    writer.writeheader()
    writer.writerows(public)
    return output.getvalue()


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def readme(rows: list[dict[str, object]], duplicates: dict[str, list[str]], zero_motion: int) -> str:
    counts = collections.Counter(str(row["category"]) for row in rows)
    category_lines = "\n".join(f"- `{name}`：{count} 个文件" for name, count in sorted(counts.items()))
    samples = sum(int(row["motion_samples"]) for row in rows)
    return f"""# PuttTrack IMU 全量研究数据包

生成日期：{date.today().isoformat()}  
仓库提交：`{git_commit()}`

此压缩包包含当前工作区里找到的全部**唯一原始 Tag IMU 捕获**：{len(rows)} 个文件、{samples:,} 条
`tag_motion` 样本。发现并去除了 {sum(len(value) - 1 for value in duplicates.values())} 份字节完全相同的重复副本。
另外有 {zero_motion} 个 JSONL 没有 `tag_motion` 记录（例如观察事件、运行审计或仅连接失败日志），不属于 IMU 原始数据，因此没有打包。

## 目录

{category_lines}

- `MANIFEST.csv` / `MANIFEST.json`：逐文件标签、质量说明、采样统计、设备信息和校验值。
- `DATA_DICTIONARY.md`：JSONL 字段与单位。
- `MODEL_ANALYSIS_BRIEF_CN.md`：交给分析模型的任务、证据边界和当前拿起识别假设。
- `DUPLICATES.json`：被去重的原始路径。
- `SHA256SUMS.txt`：包内每个原始数据文件的 SHA-256。
- `documentation/`：仓库中已有的地面与滚轮研究说明。

## 使用原则

1. 原始 JSONL 未改写；一行是一个 JSON 对象。
2. 必须先看 `quality` 和 `quality_note_zh`，不要只信文件名或 `episode_label`。
3. `90_diagnostic_or_invalid` 不能作为监督训练真值。
4. 滚轮数据是受约束夹具数据，不能冒充真实推杆、自由滚动、撞击或拿起真值。
5. 训练/测试必须按完整会话、日期、机械版本或操作者分组，不能把同一连续动作的相邻窗口随机拆开。
6. 当前数据主要来自同一个球和操作者，适合特征探索，不足以声称产品准确率。

## 已知最新批次问题

- 最新 10 次 `pickup_carry` 全部有动作，但 r07 有 GO 前污染，r09 动作开始过晚，部分样本缺少完整静止尾段。
- 最新 10 次 `putt_normal` 中，r01–r04 疑似碰到障碍物；r05 全程静止；r06 时序/动作无效；r08 有 GO 前污染；r07/r09/r10 是目前最干净候选。
- 多次真实推杆使 BMI270 陀螺仪达到 ±2000 dps 量程边界；不要把削顶后的峰值当真实峰值。
- ADXL367 是低功耗唤醒哨兵，动态动作中常削顶；动态分类应优先使用 BMI270。
"""


DATA_DICTIONARY = """# 数据字典

所有原始文件是 JSON Lines：每行一个对象，按文件内顺序读取。

## `tag_motion`

- `sequence`：设备端运动样本序号；用于检测丢样和乱序。
- `source_monotonic_us`：设备单调时钟，微秒；同一 boot 内有效，不是 UTC。
- `host_received_ns`：主机收到或写出记录的时间戳；冻结历史批量读出时不能代表动作发生时间。
- `adxl367_accel_micro_ms2`：ADXL367 三轴加速度，单位 µm/s²；除以 1,000,000 得 m/s²。
- `bmi270_accel_micro_ms2`：BMI270 三轴加速度，单位 µm/s²。
- `bmi270_gyro_micro_rads`：BMI270 三轴角速度，单位 µrad/s；除以 1,000,000 得 rad/s。
- `adxl367_valid` / `bmi270_valid`：该样本传感器数据是否有效。
- `sensor_error_bits`：非零表示传感器错误。
- `episode_label` / `episode_notes`：采集时标签和操作者说明；仍需结合 MANIFEST 的质量注释。

## 其他记录

- `tag_status` / `tag_status_final`：设备、固件、传感器量程、功耗、电池和错误计数。
- `tag_episode_marker`：设备侧 GO/action-start 时间和序号。
- `tag_episode_window`：请求的 pre-roll 与 post-GO 窗口。
- `tag_frozen_history`：冻结历史快照元数据。
- `tag_capture_result`：连续性、身份和健康检查结果；PASS 只说明捕获完整，不证明动作标签正确。

## 坐标和物理解释

三轴值位于传感器/球体坐标系，不是固定场地坐标。球滚动或被手抓住时轴会旋转。加速度计测量比力：静止时模长约为 9.80665 m/s²；它不会直接输出位置或离地高度。若要估计“向上拿起”，需要用陀螺仪传播姿态，将加速度投影到场地竖直方向，并减去 1g。短时积分可以作为特征，不能当精确高度。
"""


MODEL_BRIEF = """# 给分析模型的任务说明

## 主要目标

优先研究如何高精度识别 `pickup`，避免把正常推杆、自由滚动、边轨碰撞、小台阶跌落或普通触球误判成拿起。误报会错误地使当前洞失效，因此 precision 应优先于 recall。

## 当前探索性发现（不能直接当产品阈值）

当前同批数据上，一个事后选择的研究判据是：

1. 从动作前静止加速度估计场地竖直方向，并用 BMI270 陀螺传播短时姿态；
2. 约 0.6 s 窗口的正向竖直冲量 > 0.5 m/s；
3. 起始后 1 s 平均角速度 < 10 rad/s；
4. 同一窗口的平均角速度向量模 / 平均角速度模（旋转轴一致性）< 0.75。

该组合在目前数据中命中 11/11 个拿起样本，没有命中 8 个可用最新推杆、2 个旧人工滚动或 1 个轻敲样本。它是训练集内观察，存在严重过拟合可能，不是独立验证结果。

## 请完成的分析

1. 严格使用 `MANIFEST` 的质量标签，先分别报告干净数据、混合数据和诊断数据。
2. 使用 `tag_episode_marker.source_monotonic_us` 对齐 GO；不要用冻结历史的 `host_received_ns` 对齐动作。
3. 分析拿起开始前 0.5–1.0 s、开始后 0–0.3 s、0.3–1.2 s 三段，而不是只看整文件统计。
4. 比较姿态补偿后的竖直冲量、加速度持续时间、jerk、陀螺 RMS、旋转轴一致性、滚动轴变点和削顶比例。
5. 分开研究两条路径：静止球被拿起；滚动球被拿起。后者当前尚缺专门真值。
6. 先给出可解释规则/逻辑回归/小型树模型基线，再讨论神经网络；当前数据量不足以支持复杂模型。
7. 使用按会话/日期分组的验证，不要随机拆相邻窗口。报告混淆矩阵、pickup precision、false-positive rate 和置信区间。
8. 明确指出还需要采集哪些负例以及每类建议数量，尤其是始终不离地的触摸、边轨撞击、小台阶跌落、杯口/落杯和不同操作者。

## 产品上下文

只在 Tee/NFC 已激活且杯洞尚未确认的 `HOLE_ACTIVE` 状态检测拿起。中置信度应产生 `PICKUP_SUSPECTED` 供复核；只有经过独立验证的高置信度事件才可使当前洞/尝试失效，不能直接使整场游戏失效。放下可以用于训练分段和恢复状态，但不必成为独立游戏事件。
"""


def main() -> int:
    args = parser().parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing archive: {output}")
    rows, duplicates, zero_motion = discover()
    if not rows:
        raise SystemExit("no Tag IMU captures found")
    public_rows = [{key: value for key, value in row.items() if key != "_source"} for row in rows]
    root = output.stem
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(f"{root}/README_CN.md", readme(rows, duplicates, zero_motion))
        archive.writestr(f"{root}/DATA_DICTIONARY.md", DATA_DICTIONARY)
        archive.writestr(f"{root}/MODEL_ANALYSIS_BRIEF_CN.md", MODEL_BRIEF)
        archive.writestr(
            f"{root}/MANIFEST.json",
            json.dumps(public_rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        archive.writestr(f"{root}/MANIFEST.csv", csv_text(rows))
        archive.writestr(
            f"{root}/DUPLICATES.json",
            json.dumps(duplicates, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        checksums = []
        for row in rows:
            member = f"{root}/{row['packaged_path']}"
            archive.write(Path(row["_source"]), member)
            checksums.append(f"{row['sha256']}  {row['packaged_path']}")
        archive.writestr(f"{root}/SHA256SUMS.txt", "\n".join(checksums) + "\n")
        documentation = {
            REPO_ROOT / "experiments/research_ball_r0_stationary/README.md": "stationary_dataset.md",
            REPO_ROOT / "experiments/research_ball_r1_manual_floor/README.md": "manual_floor_dataset.md",
            REPO_ROOT / "docs/research/ROLLER_DATASET_20260904.md": "roller_dataset.md",
            REPO_ROOT / "docs/hardware/TAG_MOTION_EPISODE_RUNBOOK.md": "capture_runbook.md",
        }
        for source, name in documentation.items():
            if source.is_file():
                archive.write(source, f"{root}/documentation/{name}")
    print(
        json.dumps(
            {
                "archive": str(output),
                "unique_files": len(rows),
                "motion_samples": sum(int(row["motion_samples"]) for row in rows),
                "archive_bytes": output.stat().st_size,
                "archive_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "categories": dict(sorted(collections.Counter(str(row["category"]) for row in rows).items())),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
