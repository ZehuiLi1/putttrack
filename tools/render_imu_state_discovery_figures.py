#!/usr/bin/env python3
"""Render dependency-free SVG figures from the IMU state-discovery outputs.

The source tables are produced by ``tools/imu_state_discovery.py``.  This tool
is deterministic, uses only the Python standard library, and does not alter any
model or detector threshold.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping


WIDTH = 1120
FONT = "font-family='sans-serif'"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_document(height: int, body: Iterable[str]) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            *body,
            "</svg>",
            "",
        ]
    )


def horizontal_bars(
    title: str,
    values: list[tuple[str, float]],
    *,
    x_label: str,
    value_format: str = ".0f",
    width: int = WIDTH,
) -> str:
    left = 330
    right = 90
    top = 78
    row_height = 34
    plot_width = width - left - right
    height = top + max(1, len(values)) * row_height + 78
    maximum = max((value for _, value in values), default=1.0) or 1.0
    body = [
        f'<text x="40" y="38" {FONT} font-size="24" font-weight="bold">{esc(title)}</text>',
        f'<line x1="{left}" y1="{top-14}" x2="{left}" y2="{height-58}" stroke="black"/>',
    ]
    for index, (label, value) in enumerate(values):
        y = top + index * row_height
        bar_width = plot_width * value / maximum
        body.extend(
            [
                f'<text x="{left-12}" y="{y+17}" text-anchor="end" {FONT} font-size="13">{esc(label)}</text>',
                f'<rect x="{left}" y="{y}" width="{bar_width:.2f}" height="22" fill="#557a95"/>',
                f'<text x="{left+bar_width+8:.2f}" y="{y+17}" {FONT} font-size="13">{format(value, value_format)}</text>',
            ]
        )
    body.append(
        f'<text x="{left+plot_width/2:.1f}" y="{height-20}" text-anchor="middle" {FONT} font-size="14">{esc(x_label)}</text>'
    )
    return svg_document(height, body)


def stacked_v0(rows: list[dict[str, str]]) -> str:
    order = sorted({row["label"] for row in rows})
    decisions = ["PICKUP", "NOT_PICKUP", "UNKNOWN"]
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        counts[row["label"]][row["prediction"]] += 1
    left = 300
    plot_width = 700
    top = 80
    row_height = 42
    height = top + len(order) * row_height + 100
    fills = {"PICKUP": "#3b7d44", "NOT_PICKUP": "#557a95", "UNKNOWN": "#999999"}
    body = [
        f'<text x="40" y="38" {FONT} font-size="24" font-weight="bold">Frozen V0 decisions by post-freeze label</text>'
    ]
    legend_x = 600
    for index, decision in enumerate(decisions):
        x = legend_x + index * 145
        body.append(f'<rect x="{x}" y="48" width="16" height="16" fill="{fills[decision]}"/>')
        body.append(f'<text x="{x+22}" y="61" {FONT} font-size="12">{decision}</text>')
    for index, label in enumerate(order):
        y = top + index * row_height
        total = sum(counts[label].values()) or 1
        body.append(f'<text x="{left-12}" y="{y+21}" text-anchor="end" {FONT} font-size="13">{esc(label)}</text>')
        cursor = left
        for decision in decisions:
            count = counts[label][decision]
            width = plot_width * count / total
            if count:
                body.append(f'<rect x="{cursor:.2f}" y="{y}" width="{width:.2f}" height="28" fill="{fills[decision]}"/>')
                if width > 28:
                    body.append(f'<text x="{cursor+width/2:.2f}" y="{y+20}" text-anchor="middle" {FONT} font-size="12" fill="white">{count}</text>')
            cursor += width
    body.append(f'<text x="{left+plot_width/2}" y="{height-25}" text-anchor="middle" {FONT} font-size="14">Fraction within label (UNKNOWN retained)</text>')
    return svg_document(height, body)


def benchmark(path: Path, title: str, metric: str) -> str:
    rows = read_rows(path)
    values = []
    for row in rows:
        raw = row.get(metric, "")
        if not raw:
            continue
        try:
            values.append((row.get("model", "unknown"), float(raw)))
        except ValueError:
            continue
    values.sort(key=lambda item: item[1])
    return horizontal_bars(title, values, x_label=metric, value_format=".3f")


def confusion(prediction_path: Path, benchmark_path: Path, title: str, metric: str) -> str:
    benchmark_rows = read_rows(benchmark_path)
    valid = []
    for row in benchmark_rows:
        try:
            valid.append((float(row.get(metric, "nan")), row["model"]))
        except (ValueError, KeyError):
            continue
    if not valid:
        return svg_document(180, [f'<text x="40" y="50" {FONT} font-size="22">No confusion data</text>'])
    model = sorted(valid, key=lambda item: (-item[0], item[1]))[0][1]
    rows = [row for row in read_rows(prediction_path) if row.get("model") == model]
    labels = sorted({row["truth"] for row in rows} | {row["prediction"] for row in rows})
    matrix = {(truth, prediction): 0 for truth in labels for prediction in labels}
    for row in rows:
        matrix[(row["truth"], row["prediction"])] += 1
    cell = 72
    left = 280
    top = 105
    height = top + len(labels) * cell + 120
    maximum = max(matrix.values(), default=1) or 1
    body = [
        f'<text x="40" y="38" {FONT} font-size="24" font-weight="bold">{esc(title)}: {esc(model)}</text>',
        f'<text x="{left + len(labels)*cell/2}" y="78" text-anchor="middle" {FONT} font-size="14">Predicted</text>',
        f'<text x="45" y="{top + len(labels)*cell/2}" transform="rotate(-90 45 {top + len(labels)*cell/2})" text-anchor="middle" {FONT} font-size="14">Truth</text>',
    ]
    for index, label in enumerate(labels):
        body.append(f'<text x="{left+index*cell+cell/2}" y="{top-12}" transform="rotate(-35 {left+index*cell+cell/2} {top-12})" text-anchor="start" {FONT} font-size="11">{esc(label)}</text>')
        body.append(f'<text x="{left-12}" y="{top+index*cell+cell/2+4}" text-anchor="end" {FONT} font-size="11">{esc(label)}</text>')
    for row_index, truth in enumerate(labels):
        for column_index, prediction in enumerate(labels):
            value = matrix[(truth, prediction)]
            shade = 245 - int(150 * value / maximum)
            fill = f"rgb({shade},{shade},{shade})"
            x = left + column_index * cell
            y = top + row_index * cell
            body.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" stroke="white"/>')
            body.append(f'<text x="{x+cell/2}" y="{y+cell/2+5}" text-anchor="middle" {FONT} font-size="15">{value}</text>')
    return svg_document(height, body)


def clipping(rows: list[dict[str, str]]) -> str:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        label = row.get("label", "unknown")
        for name, column in (("ADXL367", "adxl_clip_samples"), ("BMI270 accel", "bmi_accel_clip_samples"), ("BMI270 gyro", "bmi_gyro_clip_samples")):
            try:
                if float(row.get(column, "0") or 0) > 0:
                    counts[label][name] += 1
            except ValueError:
                pass
    labels = sorted(counts, key=lambda label: sum(counts[label].values()))
    left = 300
    top = 82
    row_height = 38
    plot_width = 700
    height = top + len(labels) * row_height + 100
    series = ["ADXL367", "BMI270 accel", "BMI270 gyro"]
    fills = {"ADXL367": "#777777", "BMI270 accel": "#3b7d44", "BMI270 gyro": "#557a95"}
    maximum = max((max(counts[label].values(), default=0) for label in labels), default=1) or 1
    body = [f'<text x="40" y="38" {FONT} font-size="24" font-weight="bold">Sensor clipping by label</text>']
    for index, name in enumerate(series):
        x = 610 + index * 145
        body.append(f'<rect x="{x}" y="50" width="16" height="16" fill="{fills[name]}"/>')
        body.append(f'<text x="{x+22}" y="63" {FONT} font-size="11">{name}</text>')
    bar_height = 8
    for row_index, label in enumerate(labels):
        base_y = top + row_index * row_height
        body.append(f'<text x="{left-12}" y="{base_y+18}" text-anchor="end" {FONT} font-size="12">{esc(label)}</text>')
        for series_index, name in enumerate(series):
            value = counts[label][name]
            width = plot_width * value / maximum
            y = base_y + series_index * (bar_height + 2)
            body.append(f'<rect x="{left}" y="{y}" width="{width:.2f}" height="{bar_height}" fill="{fills[name]}"/>')
    body.append(f'<text x="{left+plot_width/2}" y="{height-22}" text-anchor="middle" {FONT} font-size="14">Files containing at least one clipped sample</text>')
    return svg_document(height, body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_dir", type=Path)
    args = parser.parse_args()
    root = args.analysis_dir
    output = root / "figures"
    output.mkdir(parents=True, exist_ok=True)

    labels = read_rows(root / "label_quality_counts.csv")
    label_counts = Counter()
    for row in labels:
        label_counts[row["label"]] += int(row["episodes"])
    (output / "01_label_composition.svg").write_text(
        horizontal_bars("Current semantic episode composition", sorted(label_counts.items(), key=lambda item: item[1]), x_label="Episodes"),
        encoding="utf-8",
    )
    (output / "02_frozen_v0_decisions.svg").write_text(stacked_v0(read_rows(root / "frozen_v0_reconstruction_replay.csv")), encoding="utf-8")
    (output / "03_flat_multiclass_models.svg").write_text(benchmark(root / "flat_multiclass_benchmarks.csv", "Exploratory flat episode classifier", "macro_f1"), encoding="utf-8")
    (output / "04_path_a_models.svg").write_text(benchmark(root / "path_a_benchmarks.csv", "Path A model challenge", "f1"), encoding="utf-8")
    (output / "05_path_b_models.svg").write_text(benchmark(root / "path_b_benchmarks.csv", "Path B exploratory model challenge", "macro_f1"), encoding="utf-8")
    (output / "06_flat_best_confusion.svg").write_text(confusion(root / "flat_multiclass_predictions.csv", root / "flat_multiclass_benchmarks.csv", "Exploratory flat episode confusion", "macro_f1"), encoding="utf-8")
    (output / "07_clipping_by_label.svg").write_text(clipping(read_rows(root / "episode_features.csv")), encoding="utf-8")
    print(f"wrote 7 SVG figures to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
