"""Dependency-free SVG reporting for research-ball motion captures."""

from __future__ import annotations

from html import escape
import math
from pathlib import Path
from typing import Sequence

from putttrack.tag import MotionRecord


def _norm(values: tuple[int, int, int]) -> float:
    return math.sqrt(sum(value * value for value in values)) / 1_000_000.0


def _series(records: Sequence[MotionRecord]) -> dict[str, list[float]]:
    start_us = records[0].source_monotonic_us
    times = [(item.source_monotonic_us - start_us) / 1_000_000.0 for item in records]
    bmi_accel = [_norm(item.bmi270_accel_micro_ms2) for item in records]
    adxl_accel = [_norm(item.adxl367_accel_micro_ms2) for item in records]
    gyro = [_norm(item.bmi270_gyro_micro_rads) for item in records]
    jerk = [0.0]
    for previous, current, previous_accel, current_accel in zip(
        records, records[1:], bmi_accel, bmi_accel[1:]
    ):
        dt = (current.source_monotonic_us - previous.source_monotonic_us) / 1_000_000.0
        jerk.append(abs(current_accel - previous_accel) / dt)
    return {
        "time_s": times,
        "BMI270 accel |a| (m/s²)": bmi_accel,
        "BMI270 gyro |ω| (rad/s)": gyro,
        "Jerk magnitude (m/s³)": jerk,
        "ADXL367 accel |a| (m/s²)": adxl_accel,
    }


def _polyline(
    times: Sequence[float],
    values: Sequence[float],
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> str:
    t_min, t_max = min(times), max(times)
    v_min, v_max = min(values), max(values)
    if t_max <= t_min:
        t_max = t_min + 1.0
    if v_max <= v_min:
        padding = max(abs(v_min) * 0.05, 1.0)
        v_min -= padding
        v_max += padding
    points = []
    for time_s, value in zip(times, values):
        px = x + (time_s - t_min) / (t_max - t_min) * width
        py = y + height - (value - v_min) / (v_max - v_min) * height
        points.append(f"{px:.2f},{py:.2f}")
    return " ".join(points)


def render_episode_svg(
    records: Sequence[MotionRecord],
    *,
    title: str,
    subtitle: str | None = None,
) -> str:
    """Render a standalone SVG so CI and field laptops need no plotting package."""

    if len(records) < 2:
        raise ValueError("SVG reporting requires at least two motion records")
    data = _series(records)
    times = data.pop("time_s")
    width = 1100
    left = 95
    right = 30
    top = 95
    panel_height = 145
    panel_gap = 45
    plot_width = width - left - right
    height = top + len(data) * (panel_height + panel_gap) + 55

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="35" font-family="sans-serif" font-size="22" font-weight="bold">{escape(title)}</text>',
    ]
    if subtitle:
        parts.append(
            f'<text x="{left}" y="62" font-family="sans-serif" font-size="13">{escape(subtitle)}</text>'
        )

    duration = times[-1] - times[0]
    for index, (label, values) in enumerate(data.items()):
        panel_y = top + index * (panel_height + panel_gap)
        v_min, v_max = min(values), max(values)
        parts.extend(
            [
                f'<text x="{left}" y="{panel_y - 10}" font-family="sans-serif" font-size="14">{escape(label)}</text>',
                f'<rect x="{left}" y="{panel_y}" width="{plot_width}" height="{panel_height}" fill="none" stroke="black" stroke-width="1"/>',
                f'<polyline points="{_polyline(times, values, x=left, y=panel_y, width=plot_width, height=panel_height)}" fill="none" stroke="black" stroke-width="1.5"/>',
                f'<text x="{left - 8}" y="{panel_y + 12}" text-anchor="end" font-family="monospace" font-size="11">{v_max:.3g}</text>',
                f'<text x="{left - 8}" y="{panel_y + panel_height}" text-anchor="end" font-family="monospace" font-size="11">{v_min:.3g}</text>',
            ]
        )
        if index == len(data) - 1:
            parts.extend(
                [
                    f'<text x="{left}" y="{panel_y + panel_height + 20}" font-family="monospace" font-size="11">0 s</text>',
                    f'<text x="{left + plot_width}" y="{panel_y + panel_height + 20}" text-anchor="end" font-family="monospace" font-size="11">{duration:.2f} s</text>',
                ]
            )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def write_episode_svg(
    output: Path,
    records: Sequence[MotionRecord],
    *,
    title: str,
    subtitle: str | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_episode_svg(records, title=title, subtitle=subtitle), encoding="utf-8")
