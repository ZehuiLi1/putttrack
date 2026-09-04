#!/usr/bin/env python3
"""PuttTrack Research Ball IMU full-state discovery pass.

This is a research-only evaluator. It audits the immutable 2026-09-04 archive
plus newer manifest-backed Research Ball captures, preserves the frozen pickup
V0 boundary, and compares interpretable episode-level baselines without giving
IMU any gameplay/scoring authority.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from collections import Counter, defaultdict
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics
import sys
import warnings
import zipfile
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from scipy import signal, stats

from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
)
from sklearn.model_selection import LeaveOneOut, LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

G = 9.80665
ADXL_CLIP = 19_221_034 / 1_000_000.0
BMI_ACCEL_CLIP = 153_768_272 / 1_000_000.0
BMI_GYRO_CLIP = 34_208_453 / 1_000_000.0
RANDOM_SEED = 20260904

STATE_LABEL_MAP = {
    "stationary": "STATIONARY",
    "handling": "HANDLING_NO_LIFT",
    "pickup_carry": "PICKED_UP_CARRIED",
    "pickup_drop": "PICKED_UP_CARRIED",
    "rolling_pickup": "ROLLING_PICKUP",
    "rolling": "ROLLING",
    "putt_gentle": "ROLLING",
    "putt_normal": "ROLLING",
    "putt_firm": "ROLLING",
    "putt_rail_collision": "COLLISION_RAIL",
    "track_step_drop": "TRACK_STEP_DROP",
    "impact_tap": "IMPACT_TAP",
}

UNSUPPORTED_V0_LABELS = {"rolling_pickup"}
STATIONARY_PICKUP_POS = {"pickup_carry", "pickup_drop"}
PATH_A_NEG = {"handling", "putt_gentle", "putt_normal", "putt_firm", "impact_tap", "stationary"}
PATH_B_LABELS = {"rolling_pickup", "putt_rail_collision", "track_step_drop", "rolling", "putt_gentle", "putt_normal"}

@dataclass
class Episode:
    key: str
    source: str
    dataset_id: str
    capture_path: str
    label: str
    session: str
    operator: str
    device_id: str
    boot_id: str
    firmware_version: str
    core_revision: str
    shell_revision: str
    surface: str
    orientation: str
    strength: str
    notes: str
    quality_declared: str
    raw_text: str
    sha256: str

@dataclass
class Capture:
    t: np.ndarray
    seq: np.ndarray
    acc: np.ndarray
    gyro: np.ndarray
    adxl: np.ndarray
    valid: np.ndarray
    error_bits: np.ndarray
    go_us: int | None
    status: dict[str, Any]
    final_status: dict[str, Any]
    malformed_lines: int
    capture_pass: bool
    embedded_labels: tuple[str, ...]


def text(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def canonical_label(value: str) -> str:
    return text(value).lower().replace("-", "_")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse_notes_metadata(notes: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ("operator", "surface", "ball", "core", "shell", "orientation", "session"):
        m = re.search(rf"(?:^|[;\s]){key}\s*=\s*([^;]+)", notes, re.I)
        if m:
            out[key] = m.group(1).strip()
    return out


def parse_capture(raw_text: str) -> Capture:
    motions: list[dict[str, Any]] = []
    status: dict[str, Any] = {}
    final_status: dict[str, Any] = {}
    go_candidates: list[int] = []
    malformed = 0
    capture_pass = True
    labels: set[str] = set()
    for line in raw_text.splitlines():
        if not line.strip():
            continue
        try:
            p = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(p, dict):
            malformed += 1
            continue
        rt = p.get("record_type")
        lab = p.get("episode_label")
        if isinstance(lab, str) and lab.strip():
            labels.add(canonical_label(lab))
        if rt == "tag_motion":
            motions.append(p)
        elif rt == "tag_status" and not status:
            status = p
        elif rt == "tag_status_final":
            final_status = p
        elif rt == "tag_episode_marker" and p.get("marker_kind") == "action_start":
            if p.get("source_monotonic_us") is not None:
                go_candidates.append(int(p["source_monotonic_us"]))
        elif rt == "tag_episode_window":
            if p.get("action_start_source_monotonic_us") is not None:
                go_candidates.append(int(p["action_start_source_monotonic_us"]))
        elif rt == "tag_capture_result" and text(p.get("status"), "PASS").upper() != "PASS":
            capture_pass = False
    if len(motions) < 2:
        raise ValueError("fewer than two tag_motion records")
    motions.sort(key=lambda p: (int(p["source_monotonic_us"]), int(p["sequence"])))
    t_us = np.asarray([int(p["source_monotonic_us"]) for p in motions], dtype=np.int64)
    seq = np.asarray([int(p["sequence"]) for p in motions], dtype=np.int64)
    acc = np.asarray([p["bmi270_accel_micro_ms2"] for p in motions], dtype=float) / 1e6
    gyro = np.asarray([p["bmi270_gyro_micro_rads"] for p in motions], dtype=float) / 1e6
    adxl = np.asarray([p["adxl367_accel_micro_ms2"] for p in motions], dtype=float) / 1e6
    valid = np.asarray([
        bool(p.get("bmi270_valid")) and bool(p.get("adxl367_valid")) and int(p.get("sensor_error_bits", 0)) == 0
        for p in motions
    ], dtype=bool)
    error_bits = np.asarray([int(p.get("sensor_error_bits", 0)) for p in motions], dtype=np.int64)
    return Capture(
        t=t_us.astype(float) / 1e6,
        seq=seq,
        acc=acc,
        gyro=gyro,
        adxl=adxl,
        valid=valid,
        error_bits=error_bits,
        go_us=min(go_candidates) if go_candidates else None,
        status=status,
        final_status=final_status,
        malformed_lines=malformed,
        capture_pass=capture_pass,
        embedded_labels=tuple(sorted(labels)),
    )


def archive_episodes(root: Path) -> list[Episode]:
    zip_path = root / "datasets" / "putttrack_imu_dataset_20260904.zip"
    manifest_path = root / "docs" / "research" / "imu_analysis_20260904" / "MANIFEST.csv"
    if not zip_path.exists() or not manifest_path.exists():
        return []
    manifest = pd.read_csv(manifest_path).fillna("")
    episodes: list[Episode] = []
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        for _, r in manifest.iterrows():
            packaged = text(r.get("packaged_path"))
            candidates = [packaged, f"putttrack_imu_dataset_20260904/{packaged}"]
            member = next((c for c in candidates if c in names), None)
            if member is None:
                # tolerate a top-level directory name chosen by the packager
                suffix = "/" + packaged.lstrip("/")
                matches = [n for n in names if n.endswith(suffix)]
                member = matches[0] if len(matches) == 1 else None
            if member is None:
                continue
            raw = zf.read(member).decode("utf-8")
            notes = text(r.get("quality_note_zh"))
            episodes.append(Episode(
                key=f"archive::{packaged}",
                source="archive_20260904",
                dataset_id="putttrack_imu_dataset_20260904",
                capture_path=packaged,
                label=canonical_label(r.get("episode_label", "")),
                session=text(r.get("boot_id"), text(r.get("category"), "archive")),
                operator="unknown",
                device_id=text(r.get("device_id"), "unknown"),
                boot_id=text(r.get("boot_id"), "unknown"),
                firmware_version=text(r.get("firmware_version"), "unknown"),
                core_revision="unknown",
                shell_revision="unknown",
                surface="unknown",
                orientation="unknown",
                strength="unknown",
                notes=notes,
                quality_declared=text(r.get("quality"), "unknown"),
                raw_text=raw,
                sha256=text(r.get("sha256"), sha256_text(raw)),
            ))
    return episodes


def manifest_episodes(root: Path) -> list[Episode]:
    out: list[Episode] = []
    for mf in sorted((root / "experiments").glob("**/manifest.json")):
        try:
            p = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(p, dict) or not isinstance(p.get("episodes"), list):
            continue
        defaults = p.get("defaults") if isinstance(p.get("defaults"), dict) else {}
        dataset_id = text(p.get("dataset_id"), mf.parent.name)
        for ep0 in p["episodes"]:
            if not isinstance(ep0, dict):
                continue
            ep = {**defaults, **ep0}
            rel = text(ep.get("capture"))
            path = mf.parent / rel
            if not path.exists() or path.suffix.lower() != ".jsonl":
                continue
            raw = path.read_text(encoding="utf-8")
            notes = text(ep.get("notes"), text(defaults.get("notes")))
            nm = parse_notes_metadata(notes)
            out.append(Episode(
                key=f"manifest::{mf.parent.name}::{text(ep.get('episode_id'), path.stem)}",
                source=f"manifest::{mf.parent.name}",
                dataset_id=dataset_id,
                capture_path=str(path.relative_to(root)),
                label=canonical_label(ep.get("label", "")),
                session=text(ep.get("session"), text(defaults.get("session"), mf.parent.name)),
                operator=text(ep.get("operator"), text(defaults.get("operator"), nm.get("operator", "unknown"))),
                device_id="unknown",
                boot_id="unknown",
                firmware_version="unknown",
                core_revision=text(ep.get("core_revision"), text(defaults.get("core_revision"), nm.get("core", "unknown"))),
                shell_revision=text(ep.get("shell_revision"), text(defaults.get("shell_revision"), nm.get("shell", "unknown"))),
                surface=text(ep.get("surface"), text(defaults.get("surface"), nm.get("surface", "unknown"))),
                orientation=text(ep.get("orientation"), text(defaults.get("orientation"), nm.get("orientation", "unknown"))),
                strength=text(ep.get("strength"), "unknown"),
                notes=notes,
                quality_declared="manifest_operator_label",
                raw_text=raw,
                sha256=sha256_text(raw),
            ))
    return out


def deduplicate(episodes: list[Episode]) -> tuple[list[Episode], pd.DataFrame]:
    by_sha: dict[str, Episode] = {}
    duplicates: list[dict[str, str]] = []
    # Prefer current experiment manifests over the archive for richer physical metadata.
    for ep in sorted(episodes, key=lambda x: (x.sha256, 0 if x.source.startswith("manifest") else 1)):
        if ep.sha256 in by_sha:
            duplicates.append({"sha256": ep.sha256, "kept": by_sha[ep.sha256].key, "duplicate": ep.key})
            continue
        by_sha[ep.sha256] = ep
    return list(by_sha.values()), pd.DataFrame(duplicates)


def robust_mad(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return float("nan")
    med = np.nanmedian(x)
    return float(np.nanmedian(np.abs(x - med)) * 1.4826)


def integrate_trapezoid(y: np.ndarray, x: np.ndarray) -> float:
    """Integrate on both NumPy 1.x and 2.x without relying on removed APIs."""
    implementation = getattr(np, "trapezoid", None)
    if implementation is None:  # pragma: no cover - compatibility for NumPy < 2
        implementation = np.trapz
    return float(implementation(y, x))


def load_v0_config(root: Path) -> dict[str, Any]:
    detector_path = root / "configs" / "research" / "pickup_detector_v0.json"
    profile_path = (
        root
        / "configs"
        / "research"
        / "pickup_detector_v0_eval_profile.json"
    )
    detector = json.loads(detector_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(detector, dict) or not isinstance(profile, dict):
        raise ValueError("expected detector and evaluation-profile objects")
    if detector.get("authority") is not False:
        raise ValueError(
            f"research detector must remain authority=false: {detector_path}"
        )
    detector_sha256 = sha256_text(
        json.dumps(detector, sort_keys=True, separators=(",", ":"))
    )
    expected = str(profile["detector_config_sha256_expected"])
    if detector_sha256 != expected:
        raise ValueError(
            f"frozen detector hash mismatch: {detector_sha256} != {expected}"
        )
    baseline = profile["pre_go_stationary"]
    execution = dict(detector)
    execution["stationary_baseline"] = {
        "maximum_accel_norm_stdev_mps2": baseline[
            "maximum_accel_norm_stdev_mps2"
        ],
        "maximum_gyro_norm_rms_rads": baseline[
            "maximum_gyro_norm_rms_rads"
        ],
    }
    execution["_frozen_config_sha256"] = detector_sha256
    return execution


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    """Write stable research tables across repeat runs on the same platform."""
    frame.to_csv(path, index=False, float_format="%.12g", lineterminator="\n")


def run_length_true(x: np.ndarray, n: int) -> int | None:
    if n <= 1:
        idx = np.flatnonzero(x)
        return int(idx[0]) if idx.size else None
    if len(x) < n:
        return None
    c = np.convolve(x.astype(int), np.ones(n, dtype=int), mode="valid")
    idx = np.flatnonzero(c >= n)
    return int(idx[0]) if idx.size else None


def axis_consistency(g: np.ndarray) -> float:
    if len(g) == 0:
        return float("nan")
    norms = np.linalg.norm(g, axis=1)
    den = float(np.mean(norms))
    return float(np.linalg.norm(np.mean(g, axis=0)) / den) if den > 1e-12 else 0.0


def axis_coherence(g: np.ndarray) -> tuple[float, float, float]:
    if len(g) < 3:
        return (float("nan"), float("nan"), float("nan"))
    c = np.cov(g.T, bias=True)
    vals = np.sort(np.maximum(np.linalg.eigvalsh(c), 0.0))[::-1]
    s = float(vals.sum())
    if s <= 1e-12:
        return (0.0, 0.0, 0.0)
    return (float(vals[0] / s), float(vals[1] / s), float(vals[2] / s))


def linear_slope(t: np.ndarray, x: np.ndarray) -> float:
    if len(x) < 2 or np.ptp(t) <= 0:
        return float("nan")
    return float(np.polyfit(t, x, 1)[0])


def spectral_entropy(x: np.ndarray, fs: float) -> float:
    if len(x) < 8 or not np.isfinite(fs) or fs <= 0:
        return float("nan")
    f, p = signal.periodogram(x - np.mean(x), fs=fs)
    p = p[1:]
    if p.size == 0 or np.sum(p) <= 0:
        return 0.0
    p = p / np.sum(p)
    return float(-np.sum(p * np.log(p + 1e-15)) / np.log(len(p))) if len(p) > 1 else 0.0


def peak_count(x: np.ndarray, threshold: float, distance: int) -> int:
    if len(x) < 3:
        return 0
    peaks, _ = signal.find_peaks(x, height=threshold, distance=max(1, distance))
    return int(len(peaks))


def window_metrics(prefix: str, t: np.ndarray, acc: np.ndarray, gyro: np.ndarray, adxl: np.ndarray, fs: float) -> dict[str, float]:
    out: dict[str, float] = {}
    if len(t) < 2:
        for name in (
            "n", "acc_dev_mean", "acc_dev_rms", "acc_dev_max", "acc_norm_std", "acc_norm_min", "acc_norm_max",
            "jerk_rms", "jerk_peak", "gyro_mean", "gyro_rms", "gyro_max", "gyro_std", "gyro_integral",
            "axis_consistency", "axis_eig1", "axis_eig2", "axis_eig3", "gyro_slope", "freefall_fraction",
            "near_g_fraction", "gyro_entropy", "acc_entropy", "adxl_dev_rms", "acc_gyro_corr"
        ):
            out[f"{prefix}_{name}"] = float("nan")
        return out
    an = np.linalg.norm(acc, axis=1)
    gn = np.linalg.norm(gyro, axis=1)
    adn = np.linalg.norm(adxl, axis=1)
    dev = an - G
    dt = np.diff(t)
    jerk = np.linalg.norm(np.diff(acc, axis=0), axis=1) / np.maximum(dt, 1e-6)
    eig1, eig2, eig3 = axis_coherence(gyro)
    out.update({
        f"{prefix}_n": float(len(t)),
        f"{prefix}_acc_dev_mean": float(np.mean(dev)),
        f"{prefix}_acc_dev_rms": float(np.sqrt(np.mean(dev**2))),
        f"{prefix}_acc_dev_max": float(np.max(np.abs(dev))),
        f"{prefix}_acc_norm_std": float(np.std(an)),
        f"{prefix}_acc_norm_min": float(np.min(an)),
        f"{prefix}_acc_norm_max": float(np.max(an)),
        f"{prefix}_jerk_rms": float(np.sqrt(np.mean(jerk**2))) if len(jerk) else 0.0,
        f"{prefix}_jerk_peak": float(np.max(jerk)) if len(jerk) else 0.0,
        f"{prefix}_gyro_mean": float(np.mean(gn)),
        f"{prefix}_gyro_rms": float(np.sqrt(np.mean(gn**2))),
        f"{prefix}_gyro_max": float(np.max(gn)),
        f"{prefix}_gyro_std": float(np.std(gn)),
        f"{prefix}_gyro_integral": integrate_trapezoid(gn, t),
        f"{prefix}_axis_consistency": axis_consistency(gyro),
        f"{prefix}_axis_eig1": eig1,
        f"{prefix}_axis_eig2": eig2,
        f"{prefix}_axis_eig3": eig3,
        f"{prefix}_gyro_slope": linear_slope(t, gn),
        f"{prefix}_freefall_fraction": float(np.mean(an < 0.35 * G)),
        f"{prefix}_near_g_fraction": float(np.mean(np.abs(an - G) < 0.5)),
        f"{prefix}_gyro_entropy": spectral_entropy(gn, fs),
        f"{prefix}_acc_entropy": spectral_entropy(dev, fs),
        f"{prefix}_adxl_dev_rms": float(np.sqrt(np.mean((adn - G)**2))),
        f"{prefix}_acc_gyro_corr": float(np.corrcoef(np.abs(dev), gn)[0, 1]) if np.std(dev) > 1e-12 and np.std(gn) > 1e-12 else 0.0,
    })
    return out


def estimate_vertical_impulse(
    t: np.ndarray,
    acc: np.ndarray,
    gyro: np.ndarray,
    baseline_mask: np.ndarray,
    onset_time: float,
    *,
    gravity: float,
    start: float,
    end: float,
) -> float:
    if np.sum(baseline_mask) < 3:
        return float("nan")
    u = np.mean(acc[baseline_mask], axis=0)
    n = np.linalg.norm(u)
    if n <= 1e-6:
        return float("nan")
    u = u / n
    total = 0.0
    # The initial direction is defined by the pre-GO stationary window. Start
    # propagation at that window's final sample; propagating through samples
    # before the baseline would be physically inconsistent.
    base_indices = np.flatnonzero(baseline_mask)
    start_index = int(base_indices[-1])
    for i in range(start_index + 1, len(t)):
        dt = t[i] - t[i - 1]
        if dt <= 0:
            continue
        u = u - np.cross(gyro[i], u) * dt
        un = np.linalg.norm(u)
        if un > 1e-9:
            u = u / un
        rel = t[i] - onset_time
        if start <= rel <= end:
            total += max(0.0, float(np.dot(acc[i], u) - gravity)) * dt
    return float(total)


def detect_onset(
    t_rel: np.ndarray,
    acc: np.ndarray,
    gyro: np.ndarray,
    baseline_mask: np.ndarray,
    config: dict[str, Any],
) -> tuple[int | None, dict[str, float]]:
    onset = config["onset"]
    gravity = float(config["gravity_mps2"])
    an = np.linalg.norm(acc, axis=1)
    gn = np.linalg.norm(gyro, axis=1)
    base_dev = np.abs(an[baseline_mask] - gravity)
    base_g = gn[baseline_mask]
    a_floor = float(onset["accel_norm_deviation_mps2"])
    g_floor = float(onset["gyro_norm_rads"])
    a_thr = max(a_floor, float(np.median(base_dev) + 6 * robust_mad(base_dev))) if base_dev.size else a_floor
    g_thr = max(g_floor, float(np.median(base_g) + 6 * robust_mad(base_g))) if base_g.size else g_floor
    search = t_rel >= float(onset["search_start_after_go_s"])
    active = (np.abs(an - G) >= a_thr) | (gn >= g_thr)
    idxs = np.flatnonzero(search)
    if idxs.size == 0:
        return None, {"onset_accel_threshold": a_thr, "onset_gyro_threshold": g_thr}
    start = int(idxs[0])
    lookahead = int(onset["lookahead_samples"])
    minimum_active = int(onset["minimum_active_samples"])
    # Frozen V0 counts active samples in a lookahead; they need not be consecutive.
    idx = None
    for i in range(start, max(start, len(active) - lookahead + 1)):
        if int(np.sum(active[i:i + lookahead])) >= minimum_active:
            idx = i
            break
    return idx, {"onset_accel_threshold": a_thr, "onset_gyro_threshold": g_thr}


def classify_semantic_quality(ep: Episode, cap: Capture, has_onset: bool) -> tuple[str, list[str]]:
    reasons: list[str] = []
    evidence_identity = (ep.capture_path + " " + ep.quality_declared).lower()
    p = ep.notes.lower()
    if (
        ".failed" in evidence_identity
        or "invalid_label" in evidence_identity
        or "diagnostic" in evidence_identity
        or not cap.capture_pass
        or cap.malformed_lines
    ):
        reasons.append("invalid_or_failed_capture")
        return "INVALID", reasons
    if len(cap.embedded_labels) > 1 or (cap.embedded_labels and ep.label not in cap.embedded_labels):
        reasons.append("label_mismatch")
        return "INVALID", reasons
    # Dataset-level notes may document that one named episode hit an obstacle;
    # they are inherited by every episode and cannot mark the whole dataset MIXED.
    # Episode-level capture/strength/quality fields carry the actual exclusion.
    mixed_evidence = (ep.capture_path + " " + ep.strength + " " + ep.quality_declared).lower()
    if "mixed" in mixed_evidence or "suspected_collision" in mixed_evidence:
        reasons.append("mixed_or_obstacle_content")
        return "MIXED", reasons
    if "timing_warning" in p or "pre-go" in p or "pre_go" in p:
        reasons.append("timing_warning")
    if ep.surface in {"", "unknown", "unspecified"}:
        reasons.append("surface_not_recorded")
    if ep.orientation in {"", "unknown", "uncontrolled"}:
        reasons.append("orientation_uncontrolled")
    if ep.operator in {"", "unknown"}:
        reasons.append("operator_unknown")
    if cap.go_us is None:
        reasons.append("go_marker_missing")
    if ep.label not in {"stationary"} and not has_onset:
        reasons.append("no_detected_motion_onset")
    return ("WARNING" if reasons else "CLEAN_OPERATOR_LABEL"), reasons


def extract_features(ep: Episode, v0_config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    cap = parse_capture(ep.raw_text)
    # Fill embedded status metadata when archive/manifest did not provide it.
    st = cap.final_status or cap.status
    ep.device_id = ep.device_id if ep.device_id != "unknown" else text(st.get("device_id"), "unknown")
    ep.boot_id = ep.boot_id if ep.boot_id != "unknown" else text(st.get("boot_id"), "unknown")
    ep.firmware_version = ep.firmware_version if ep.firmware_version != "unknown" else text(st.get("firmware_version"), "unknown")

    t = cap.t.copy()
    dt = np.diff(t)
    fs = float(1.0 / np.median(dt)) if len(dt) and np.median(dt) > 0 else float("nan")
    go_t = cap.go_us / 1e6 if cap.go_us is not None else t[0] + min(3.0, max(0.0, (t[-1]-t[0])*0.2))
    tr = t - go_t
    baseline_s = float(v0_config["required_pre_go_stationary_s"])
    baseline_mask = (tr >= -baseline_s) & (tr < 0.0) & cap.valid
    if np.sum(baseline_mask) < max(3, int(fs * 0.5) if np.isfinite(fs) else 3):
        baseline_mask = (t <= t[0] + min(1.0, (t[-1]-t[0])*0.2)) & cap.valid
    onset_idx, onset_meta = detect_onset(tr, cap.acc, cap.gyro, baseline_mask, v0_config)
    onset_time = t[onset_idx] if onset_idx is not None else float("nan")

    an = np.linalg.norm(cap.acc, axis=1)
    gn = np.linalg.norm(cap.gyro, axis=1)
    adn = np.linalg.norm(cap.adxl, axis=1)
    gaps = int(np.sum(np.maximum(0, np.diff(cap.seq) - 1)))
    regressions = int(np.sum(np.diff(cap.t) <= 0) + np.sum(np.diff(cap.seq) <= 0))
    quality, qreasons = classify_semantic_quality(ep, cap, onset_idx is not None)

    row: dict[str, Any] = {
        "episode_key": ep.key,
        "source": ep.source,
        "dataset_id": ep.dataset_id,
        "capture_path": ep.capture_path,
        "sha256": ep.sha256,
        "label": ep.label,
        "state_label": STATE_LABEL_MAP.get(ep.label, "OTHER"),
        "session": ep.session,
        "operator": ep.operator,
        "device_id": ep.device_id,
        "boot_id": ep.boot_id,
        "firmware_version": ep.firmware_version,
        "core_revision": ep.core_revision,
        "shell_revision": ep.shell_revision,
        "surface": ep.surface,
        "orientation": ep.orientation,
        "strength": ep.strength,
        "quality_declared": ep.quality_declared,
        "semantic_quality": quality,
        "quality_reasons": ";".join(qreasons),
        "sample_count": len(t),
        "duration_s": float(t[-1] - t[0]),
        "observed_rate_hz": fs,
        "go_marker_present": int(cap.go_us is not None),
        "onset_present": int(onset_idx is not None),
        "onset_after_go_s": float(tr[onset_idx]) if onset_idx is not None else float("nan"),
        "sequence_gaps": gaps,
        "time_or_sequence_regressions": regressions,
        "valid_fraction": float(np.mean(cap.valid)),
        "malformed_lines": cap.malformed_lines,
        "capture_pass": int(cap.capture_pass),
        "adxl_clip_samples": int(np.sum(np.max(np.abs(cap.adxl), axis=1) >= ADXL_CLIP * 0.999)),
        "bmi_accel_clip_samples": int(np.sum(np.max(np.abs(cap.acc), axis=1) >= BMI_ACCEL_CLIP * 0.999)),
        "bmi_gyro_clip_samples": int(np.sum(np.max(np.abs(cap.gyro), axis=1) >= BMI_GYRO_CLIP * 0.999)),
        "acc_norm_mean": float(np.mean(an)),
        "acc_norm_std": float(np.std(an)),
        "acc_norm_min": float(np.min(an)),
        "acc_norm_max": float(np.max(an)),
        "gyro_norm_mean": float(np.mean(gn)),
        "gyro_norm_rms": float(np.sqrt(np.mean(gn**2))),
        "gyro_norm_max": float(np.max(gn)),
        "adxl_norm_std": float(np.std(adn)),
        "active_fraction": float(np.mean((np.abs(an-G) >= 0.5) | (gn >= 0.25))),
        **onset_meta,
    }
    if np.sum(baseline_mask) >= 2:
        row.update(window_metrics("baseline", t[baseline_mask], cap.acc[baseline_mask], cap.gyro[baseline_mask], cap.adxl[baseline_mask], fs))
    else:
        row.update(window_metrics("baseline", np.array([]), np.empty((0,3)), np.empty((0,3)), np.empty((0,3)), fs))

    if onset_idx is not None:
        rel_on = t - onset_time
        for seconds, tag in [(0.1,"100ms"),(0.2,"200ms"),(0.5,"500ms"),(1.0,"1s"),(2.0,"2s")]:
            m = (rel_on >= 0) & (rel_on < seconds) & cap.valid
            row.update(window_metrics(f"onset_{tag}", t[m], cap.acc[m], cap.gyro[m], cap.adxl[m], fs))
        for start, end, tag in [(0,.25,"post_0_250"),(.25,.5,"post_250_500"),(.5,1,"post_500_1000"),(1,2,"post_1_2s"),(2,4,"post_2_4s")]:
            m = (rel_on >= start) & (rel_on < end) & cap.valid
            row.update(window_metrics(tag, t[m], cap.acc[m], cap.gyro[m], cap.adxl[m], fs))
        impulse = v0_config["vertical_impulse"]
        row["vertical_impulse_pos_0p6"] = estimate_vertical_impulse(
            t,
            cap.acc,
            cap.gyro,
            baseline_mask,
            onset_time,
            gravity=float(v0_config["gravity_mps2"]),
            start=float(impulse["window_start_relative_to_onset_s"]),
            end=float(impulse["window_end_relative_to_onset_s"]),
        )
        feature_window = (rel_on >= 0) & (rel_on < 1.0)
        row["gyro_clip_in_first_1s"] = int(np.any(np.max(np.abs(cap.gyro[feature_window]), axis=1) >= BMI_GYRO_CLIP * 0.999)) if np.any(feature_window) else 0
        # Motion/tail summaries.
        active = ((np.abs(an-G) >= max(0.5, row["onset_accel_threshold"])) | (gn >= max(0.25, row["onset_gyro_threshold"]))) & (rel_on >= 0)
        ai = np.flatnonzero(active)
        row["active_duration_after_onset_s"] = float(t[ai[-1]] - t[ai[0]]) if len(ai) > 1 else 0.0
        tail = (t >= t[-1] - 1.0)
        row["tail_stationary_fraction"] = float(np.mean((np.abs(an[tail]-G) < 0.5) & (gn[tail] < 0.25))) if np.any(tail) else float("nan")
        row["gyro_peak_count"] = peak_count(gn[rel_on >= 0], threshold=max(0.5, np.median(gn[baseline_mask]) + 8*robust_mad(gn[baseline_mask])), distance=max(1, int(fs*0.12)))
        row["acc_peak_count"] = peak_count(np.abs(an[rel_on >= 0]-G), threshold=max(1.0, np.median(np.abs(an[baseline_mask]-G)) + 8*robust_mad(np.abs(an[baseline_mask]-G))), distance=max(1, int(fs*0.12)))
    else:
        # populate feature schema consistently
        for seconds, tag in [(0.1,"100ms"),(0.2,"200ms"),(0.5,"500ms"),(1.0,"1s"),(2.0,"2s")]:
            row.update(window_metrics(f"onset_{tag}", np.array([]), np.empty((0,3)), np.empty((0,3)), np.empty((0,3)), fs))
        for tag in ("post_0_250","post_250_500","post_500_1000","post_1_2s","post_2_4s"):
            row.update(window_metrics(tag, np.array([]), np.empty((0,3)), np.empty((0,3)), np.empty((0,3)), fs))
        row.update({"vertical_impulse_pos_0p6": float("nan"), "gyro_clip_in_first_1s": 0,
                    "active_duration_after_onset_s": 0.0, "tail_stationary_fraction": 1.0,
                    "gyro_peak_count": 0, "acc_peak_count": 0})

    raw = {
        "t_rel_go": tr,
        "acc": cap.acc,
        "gyro": cap.gyro,
        "adxl": cap.adxl,
        "valid": cap.valid,
        "onset_time_rel_go": np.asarray([tr[onset_idx] if onset_idx is not None else np.nan]),
    }
    return row, raw


def v0_predict(row: pd.Series, config: dict[str, Any]) -> tuple[str, str]:
    label = row["label"]
    if label in UNSUPPORTED_V0_LABELS:
        return "UNKNOWN", "unsupported_rolling_start_pickup"
    hard_unknown = []
    if not int(row["go_marker_present"]): hard_unknown.append("missing_go")
    if row["valid_fraction"] < 1.0: hard_unknown.append("sensor_invalid")
    if row["sequence_gaps"] > 0 or row["time_or_sequence_regressions"] > 0: hard_unknown.append("continuity")
    baseline = config["stationary_baseline"]
    baseline_acc_std = row.get("baseline_acc_norm_std", np.nan)
    baseline_gyro_rms = row.get("baseline_gyro_rms", np.nan)
    if (
        not np.isfinite(baseline_acc_std)
        or not np.isfinite(baseline_gyro_rms)
        or baseline_acc_std > float(baseline["maximum_accel_norm_stdev_mps2"])
        or baseline_gyro_rms > float(baseline["maximum_gyro_norm_rms_rads"])
    ):
        hard_unknown.append("pre_go_not_stationary")
    if not int(row["onset_present"]):
        if hard_unknown:
            return "UNKNOWN", ";".join(hard_unknown + ["no_motion_onset"])
        # True stationary/no-motion negative controls are supported.
        return ("NOT_PICKUP", "no_motion_onset") if label in {"stationary", "handling"} else ("UNKNOWN", "no_motion_onset")
    if row.get("gyro_clip_in_first_1s", 0) > 0: hard_unknown.append("gyro_clipping")
    if not np.isfinite(row.get("vertical_impulse_pos_0p6", np.nan)) or not np.isfinite(row.get("onset_1s_gyro_mean", np.nan)):
        hard_unknown.append("insufficient_window")
    if hard_unknown:
        return "UNKNOWN", ";".join(hard_unknown)
    impulse = config["vertical_impulse"]
    gyro_shape = config["gyro_shape"]
    pred = (
        row["vertical_impulse_pos_0p6"] > float(impulse["minimum_mps"])
        and row["onset_1s_gyro_mean"] < float(gyro_shape["maximum_mean_norm_rads"])
        and row["onset_1s_axis_consistency"] < float(gyro_shape["maximum_axis_consistency"])
    )
    return ("PICKUP", "frozen_v0_rule") if pred else ("NOT_PICKUP", "frozen_v0_rule")


def numeric_feature_columns(df: pd.DataFrame) -> list[str]:
    exclude = {
        "sample_count", "duration_s", "observed_rate_hz", "go_marker_present", "onset_present",
        "sequence_gaps", "time_or_sequence_regressions", "valid_fraction", "malformed_lines",
        "capture_pass", "adxl_clip_samples", "bmi_accel_clip_samples", "bmi_gyro_clip_samples",
        "gyro_clip_in_first_1s",
    }
    cols = []
    for c in df.columns:
        if c in exclude:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            values = pd.to_numeric(df[c], errors="coerce")
            if values.notna().sum() >= 2 and values.dropna().nunique() >= 2:
                cols.append(c)
    return cols


def model_catalog(n_features: int, binary: bool = False) -> dict[str, Any]:
    k = max(1, min(24, n_features))
    models: dict[str, Any] = {
        "logistic": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("select", SelectKBest(f_classif, k=k)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced", random_state=RANDOM_SEED)),
        ]),
        "linear_lda_shrinkage": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("select", SelectKBest(f_classif, k=k)),
            ("scale", StandardScaler()),
            ("model", LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")),
        ]),
        "rbf_svm": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("select", SelectKBest(f_classif, k=k)),
            ("scale", StandardScaler()),
            ("model", SVC(C=1.0, kernel="rbf", gamma="scale", class_weight="balanced", probability=True, random_state=RANDOM_SEED)),
        ]),
        "random_forest": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", RandomForestClassifier(n_estimators=400, max_depth=6, min_samples_leaf=2,
                                              class_weight="balanced_subsample", random_state=RANDOM_SEED, n_jobs=1)),
        ]),
        "extra_trees": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", ExtraTreesClassifier(n_estimators=400, max_depth=8, min_samples_leaf=2,
                                             class_weight="balanced", random_state=RANDOM_SEED, n_jobs=1)),
        ]),
    }
    return models


def loo_predictions(x: pd.DataFrame, y: pd.Series, models: dict[str, Any], ids: Sequence[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    loo = LeaveOneOut()
    X = x.to_numpy(float)
    Y = y.to_numpy()
    for name, proto in models.items():
        # Preserve the target dtype.  An object array containing integer labels
        # is classified as "unknown" by scikit-learn 1.8 metrics.
        pred = np.empty_like(Y)
        conf = np.full(len(Y), np.nan)
        for train, test in loo.split(X):
            if len(np.unique(Y[train])) < 2:
                pred[test[0]] = Y[train][0]
                conf[test[0]] = 1.0
                continue
            m = clone(proto)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m.fit(X[train], Y[train])
            pred[test[0]] = m.predict(X[test])[0]
            if hasattr(m, "predict_proba"):
                try: conf[test[0]] = float(np.max(m.predict_proba(X[test])[0]))
                except Exception: pass
        acc = accuracy_score(Y, pred)
        bal = balanced_accuracy_score(Y, pred)
        macro = f1_score(Y, pred, average="macro", zero_division=0)
        weighted = f1_score(Y, pred, average="weighted", zero_division=0)
        summaries.append({
            "model": name, "evaluation": "leave_one_episode_out", "n": len(Y), "classes": len(np.unique(Y)),
            "accuracy": acc, "balanced_accuracy": bal, "macro_f1": macro, "weighted_f1": weighted,
            "median_confidence": float(np.nanmedian(conf)), "note": "episode-isolated but not session/operator/ball independent",
        })
        for i, (truth, pr) in enumerate(zip(Y, pred)):
            rows.append({"model": name, "episode_key": ids[i], "truth": truth, "prediction": pr,
                         "correct": int(truth == pr), "confidence": conf[i]})
    return pd.DataFrame(rows), pd.DataFrame(summaries)


def logo_predictions(x: pd.DataFrame, y: pd.Series, groups: pd.Series, model: Any, ids: Sequence[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    X = x.to_numpy(float); Y = y.to_numpy(); Gp = groups.to_numpy()
    rows = []
    seen_test = 0; correct_seen = 0
    logo = LeaveOneGroupOut()
    for train, test in logo.split(X, Y, Gp):
        train_classes = set(Y[train])
        test_seen = np.asarray([v in train_classes for v in Y[test]])
        m = clone(model)
        if len(train_classes) < 2:
            preds = np.asarray([next(iter(train_classes))] * len(test), dtype=object)
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m.fit(X[train], Y[train])
            preds = m.predict(X[test])
        for j, idx in enumerate(test):
            seen = bool(test_seen[j])
            rows.append({"episode_key": ids[idx], "group": Gp[idx], "truth": Y[idx], "prediction": preds[j],
                         "class_seen_in_training": int(seen), "correct": int(preds[j] == Y[idx])})
            if seen:
                seen_test += 1; correct_seen += int(preds[j] == Y[idx])
    summary = {
        "evaluation": "leave_one_session_or_manifest_group_out",
        "n": len(Y), "groups": len(np.unique(Gp)), "seen_class_test_n": seen_test,
        "seen_class_accuracy": correct_seen / seen_test if seen_test else float("nan"),
        "unseen_class_test_n": len(Y) - seen_test,
        "note": "Unseen-class rows expose class/session confounding and are not scored as ordinary errors.",
    }
    return pd.DataFrame(rows), summary


def binary_summary(truth: Sequence[int], pred: Sequence[int]) -> dict[str, Any]:
    tn, fp, fn, tp = confusion_matrix(truth, pred, labels=[0,1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(truth, pred, average="binary", zero_division=0)
    return {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
            "precision": float(precision), "recall": float(recall), "f1": float(f1),
            "specificity": float(tn/(tn+fp)) if tn+fp else float("nan"),
            "mcc": float(matthews_corrcoef(truth, pred)) if len(set(truth)) > 1 else float("nan")}


def rocket_features(raw_map: dict[str, dict[str, np.ndarray]], ids: list[str], length: int = 400, kernels: int = 192) -> np.ndarray:
    rng = np.random.default_rng(RANDOM_SEED)
    seqs = []
    grid = np.linspace(0, 8.0, length)
    for key in ids:
        r = raw_map[key]
        t = r["t_rel_go"]
        ch = np.column_stack([r["acc"], r["gyro"]])
        arr = np.empty((6, length), dtype=float)
        for c in range(6):
            valid = np.isfinite(t) & np.isfinite(ch[:,c])
            if np.sum(valid) < 2:
                arr[c] = 0
            else:
                arr[c] = np.interp(grid, t[valid], ch[valid,c], left=ch[valid,c][0], right=ch[valid,c][-1])
        # Per-episode baseline centering only; no label information.
        base = grid < 0.5
        arr = arr - np.mean(arr[:,base], axis=1, keepdims=True)
        seqs.append(arr)
    seqs = np.asarray(seqs)
    feats = np.empty((len(ids), kernels*2), dtype=np.float32)
    for k in range(kernels):
        length_k = int(rng.choice([7,9,11,15,21]))
        dilation = int(rng.choice([1,1,1,2,4,8]))
        channels = rng.choice(6, size=int(rng.integers(1,4)), replace=False)
        w = rng.normal(size=(len(channels), length_k))
        w -= w.mean(axis=1, keepdims=True)
        bias = float(rng.uniform(-1,1))
        for i, x in enumerate(seqs):
            conv_sum = None
            for ci, c in enumerate(channels):
                kernel = np.zeros((length_k-1)*dilation+1)
                kernel[::dilation] = w[ci]
                cv = signal.fftconvolve(x[c], kernel[::-1], mode="valid")
                conv_sum = cv if conv_sum is None else conv_sum[:len(cv)] + cv[:len(conv_sum)]
            z = conv_sum + bias
            feats[i, 2*k] = float(np.max(z)) if len(z) else 0.0
            feats[i, 2*k+1] = float(np.mean(z > 0)) if len(z) else 0.0
    return feats


def evaluate_rocket(raw_map: dict[str, dict[str, np.ndarray]], ids: list[str], y: pd.Series) -> tuple[pd.DataFrame, dict[str, Any]]:
    X = rocket_features(raw_map, ids)
    Y = y.to_numpy()
    pred = np.empty(len(Y), dtype=object)
    for train, test in LeaveOneOut().split(X):
        m = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                      ("model", RidgeClassifier(alpha=1.0, class_weight="balanced"))])
        m.fit(X[train], Y[train])
        pred[test[0]] = m.predict(X[test])[0]
    rows = pd.DataFrame({"model":"rocket_lite_ridge", "episode_key":ids, "truth":Y, "prediction":pred,
                         "correct":(Y==pred).astype(int)})
    summary = {"model":"rocket_lite_ridge", "evaluation":"leave_one_episode_out", "n":len(Y),
               "classes":len(np.unique(Y)), "accuracy":accuracy_score(Y,pred),
               "balanced_accuracy":balanced_accuracy_score(Y,pred),
               "macro_f1":f1_score(Y,pred,average="macro",zero_division=0),
               "weighted_f1":f1_score(Y,pred,average="weighted",zero_division=0),
               "median_confidence":float("nan"),
               "note":"data-driven random convolution baseline; episode-isolated but not session/operator/ball independent"}
    return rows, summary


def write_confusion(pred_df: pd.DataFrame, out: Path, prefix: str) -> None:
    for model, g in pred_df.groupby("model"):
        labels = sorted(set(g["truth"]) | set(g["prediction"]))
        cm = confusion_matrix(g["truth"], g["prediction"], labels=labels)
        pd.DataFrame(cm, index=[f"true:{x}" for x in labels], columns=[f"pred:{x}" for x in labels]).to_csv(out/f"{prefix}_{model}_confusion.csv")


def audit_raw_files(root: Path, represented_paths: set[str]) -> pd.DataFrame:
    rows = []
    for p in sorted((root/"experiments").glob("**/raw/*.jsonl")):
        rel = str(p.relative_to(root))
        raw = p.read_text(encoding="utf-8")
        rows.append({"path":rel, "bytes":p.stat().st_size, "sha256":sha256_text(raw),
                     "represented_by_manifest":int(rel in represented_paths),
                     "diagnostic_name":int("failed" in p.name.lower() or "diagnostic" in p.name.lower())})
    return pd.DataFrame(rows)


def top_feature_effects(df: pd.DataFrame, feature_cols: list[str], target_col: str, max_per_class: int = 8) -> pd.DataFrame:
    rows = []
    y = df[target_col]
    for cls in sorted(y.unique()):
        mask = y == cls
        for f in feature_cols:
            a = pd.to_numeric(df.loc[mask,f], errors="coerce").dropna().to_numpy()
            b = pd.to_numeric(df.loc[~mask,f], errors="coerce").dropna().to_numpy()
            if len(a)<2 or len(b)<2: continue
            pooled = math.sqrt(((len(a)-1)*np.var(a,ddof=1)+(len(b)-1)*np.var(b,ddof=1))/max(1,len(a)+len(b)-2))
            d = (np.mean(a)-np.mean(b))/pooled if pooled>1e-12 else 0.0
            rows.append({"class":cls,"feature":f,"effect_d":float(d),"class_median":float(np.median(a)),"other_median":float(np.median(b)),"n_class":len(a),"n_other":len(b)})
    out = pd.DataFrame(rows)
    if out.empty: return out
    out["abs_effect"] = out["effect_d"].abs()
    return out.sort_values(["class","abs_effect"], ascending=[True,False]).groupby("class").head(max_per_class).drop(columns="abs_effect")


def architecture_markdown(audit: dict[str, Any], benchmark: pd.DataFrame, v0: dict[str, Any], pathb: pd.DataFrame,
                          session_confounded: list[str]) -> str:
    best = benchmark.sort_values(["macro_f1","balanced_accuracy"], ascending=False).iloc[0].to_dict() if not benchmark.empty else {}
    pathb_best = pathb.sort_values(["macro_f1","balanced_accuracy"], ascending=False).iloc[0].to_dict() if not pathb.empty else {}
    return f"""# PuttTrack Research Ball IMU — Full State Discovery Result\n\nGenerated from repository data; research-only; `authority=false`.\n\n## Data audit\n\n- unique raw episodes analysed: **{audit.get('unique_episodes')}**\n- semantic manifest episodes used for model discovery: **{audit.get('model_episodes')}**\n- devices / boots / sessions / operators: **{audit.get('devices')} / {audit.get('boots')} / {audit.get('sessions')} / {audit.get('operators')}**\n- median sample rate: **{audit.get('median_rate_hz'):.2f} Hz**\n- sequence-gap episodes: **{audit.get('sequence_gap_episodes')}**\n- BMI270 gyro-clipped episodes: **{audit.get('gyro_clipped_episodes')}**\n\nClasses confined to one session/manifest group: `{', '.join(session_confounded) or 'none'}`. This prevents a commercial generalisation claim even when leave-one-episode-out scores are high.\n\n## Empirical model comparison\n\nBest exploratory flat multiclass baseline: **{best.get('model','n/a')}**, LOEO macro-F1 **{best.get('macro_f1',float('nan')):.3f}**. This is not a production accuracy estimate because episodes from the same day/operator/Ball remain correlated.\n\nBest exploratory rolling-disruption baseline: **{pathb_best.get('model','n/a')}**, LOEO macro-F1 **{pathb_best.get('macro_f1',float('nan')):.3f}**.\n\nFrozen V0 reconstruction replay (no threshold changes): `{json.dumps(v0, ensure_ascii=False)}`. UNKNOWN is retained and is not counted as a true negative.\n\n## Final architecture decision\n\nThe recommended system is **not** one flat neural network and **not** one global threshold table. Use a hierarchical hybrid recogniser:\n\n```text\nADXL367 motion wake / low-power guard\n    -> BMI270 FIFO event burst\n    -> signal health + clipping + continuity gate\n    -> multi-scale physics feature bank (0.1 / 0.2 / 0.5 / 1 / 2 s)\n    -> hierarchical finite-state / semi-Markov controller\n       STATIONARY -> ACTIVE -> ROLLING -> DISRUPTION -> POST_TRANSITION\n    -> state-specific small probabilistic classifier\n       Path A: stationary pickup vs no-lift / putt\n       Path B: rolling pickup vs rail collision / step / natural settling\n    -> calibrated confidence + explicit UNKNOWN\n    -> generic MotionEvidence only\n    -> venue context + Tee/Cup/feature sensors -> Gameplay authority\n```\n\n### Model choice now\n\nUse **regularised Logistic Regression first** for each state-specific branch, with an **Extra-Trees challenger** on Edge during research. Logistic is the production candidate now because the independent episode count is small, its evidence can be calibrated and audited, and its implementation can be reduced to a fixed feature vector plus dot products. Keep Extra-Trees only if a future untouched multi-operator/multi-Ball holdout demonstrates a statistically meaningful gain at the same false-event ceiling.\n\n### Temporal controller\n\nUse a hierarchical **explicit-duration FSM / HSMM-like policy**, not an unconstrained framewise classifier. State dwell, hysteresis, refractory intervals, legal transitions, and post-disruption persistence are part of the signal definition. A classifier emits likelihoods; the temporal controller decides whether a candidate state is sufficiently persistent, and low confidence becomes UNKNOWN.\n\n### What 50 Hz can and cannot support\n\nAt 50 Hz the current data can support stationary/activity, sustained rolling shape, pickup/carry, rolling-model departure, and coarse settling. It cannot validate exact putter-impact timing or reliably distinguish putter contact from wall/ball contact from the transient alone. Capture normal motion at 200–400 Hz and retain an 800 Hz–1.6 kHz accelerometer/FIFO burst around impact candidates before trying to give IMPACT/COLLISION subtypes product authority.\n\n### Neural-network gate\n\nDo not deploy a TCN/CNN now. Re-open that comparison only after at least two Balls, multiple operators/days/surfaces, independent event timestamps, and hundreds of genuinely independent episodes per difficult branch. The data-driven ROCKET-lite result in this report is a small-data temporal challenger, not evidence that an end-to-end neural model will generalise.\n\n## Commercial validation gates\n\n1. Freeze feature/schema/model version before collection.\n2. Blind holdout by day + operator + Ball + surface, never random adjacent windows.\n3. Report event precision/recall, false events per player-hour, P50/P95 latency, UNKNOWN rate, clipping, and exact confidence intervals.\n4. Auto-penalty requires a much higher precision gate than non-authoritative telemetry.\n5. Cup/feature completion remains physical-sensor/venue-confirmed.\n\nNo result in this report establishes Puttshack-equivalent commercial accuracy; it establishes the most defensible architecture and the next validation path.\n"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    root = args.root.resolve()
    out = (args.out or root/"artifacts"/"imu_state_discovery_20260904").resolve()
    out.mkdir(parents=True, exist_ok=True)
    v0_config = load_v0_config(root)

    all_eps = archive_episodes(root) + manifest_episodes(root)
    episodes, dup = deduplicate(all_eps)
    write_csv(dup, out/"duplicate_episode_map.csv")

    feature_rows = []
    raw_map: dict[str, dict[str, np.ndarray]] = {}
    parse_errors = []
    for ep in episodes:
        try:
            row, raw = extract_features(ep, v0_config)
            feature_rows.append(row)
            raw_map[ep.key] = raw
        except Exception as exc:
            parse_errors.append({"episode_key":ep.key,"capture_path":ep.capture_path,"error":repr(exc)})
    write_csv(pd.DataFrame(parse_errors), out/"parse_errors.csv")
    df = pd.DataFrame(feature_rows)
    write_csv(df, out/"episode_features.csv")
    if df.empty:
        failure = {
            "status": "FAILED",
            "reason": "no episodes produced features",
            "episode_count": len(episodes),
            "parse_error_count": len(parse_errors),
        }
        (out/"analysis_failure.json").write_text(
            json.dumps(failure, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 2

    represented = set(df.loc[df["source"].str.startswith("manifest"),"capture_path"])
    raw_audit = audit_raw_files(root, represented)
    write_csv(raw_audit, out/"current_experiment_raw_audit.csv")

    # Dataset audit tables.
    label_counts = df.groupby(["label","semantic_quality"]).size().rename("episodes").reset_index()
    write_csv(label_counts, out/"label_quality_counts.csv")
    meta_counts = []
    for col in ("source","dataset_id","device_id","boot_id","session","operator","firmware_version","core_revision","shell_revision","surface","orientation"):
        for value,count in df[col].fillna("unknown").value_counts(dropna=False).items():
            meta_counts.append({"dimension":col,"value":value,"episodes":int(count)})
    write_csv(pd.DataFrame(meta_counts), out/"metadata_distribution.csv")

    # Conservative semantic discovery set: manifest/archive operator-labelled, valid continuity, not declared invalid/mixed.
    model_df = df[
        df["state_label"].isin(set(STATE_LABEL_MAP.values())) &
        ~df["semantic_quality"].isin(["INVALID","MIXED"]) &
        (df["sequence_gaps"] == 0) & (df["valid_fraction"] == 1.0)
    ].copy()
    # Exclude formal roller captures from semantic truth even when they use a rolling-like label.
    model_df = model_df[~model_df["source"].str.contains("roller", case=False, na=False)]
    feature_cols = numeric_feature_columns(model_df)
    X = model_df[feature_cols]
    y = model_df["state_label"]
    ids = model_df["episode_key"].tolist()

    pred, bench = loo_predictions(X, y, model_catalog(len(feature_cols)), ids)
    try:
        rocket_pred, rocket_summary = evaluate_rocket(raw_map, ids, y)
        pred = pd.concat([pred, rocket_pred], ignore_index=True)
        bench = pd.concat([bench, pd.DataFrame([rocket_summary])], ignore_index=True)
    except Exception as exc:
        write_csv(pd.DataFrame([{"error":repr(exc)}]), out/"rocket_error.csv")
    write_csv(pred, out/"flat_multiclass_predictions.csv")
    write_csv(bench, out/"flat_multiclass_benchmarks.csv")
    write_confusion(pred, out, "flat")

    # Strict group challenge using session where available, otherwise source manifest/archive category.
    groups = model_df["session"].where(~model_df["session"].isin(["","unknown"]), model_df["source"])
    logo_pred, logo_summary = logo_predictions(X, y, groups, model_catalog(len(feature_cols))["logistic"], ids)
    write_csv(logo_pred, out/"leave_group_out_predictions.csv")
    (out/"leave_group_out_summary.json").write_text(json.dumps(logo_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Frozen V0, explicitly separating unsupported/UNKNOWN.
    prospective = df[df["source"].str.contains("pickup_precision", case=False, na=False)].copy()
    v0_rows = []
    for _, r in prospective.iterrows():
        p, reason = v0_predict(r, v0_config)
        target = "PICKUP" if r["label"] in STATIONARY_PICKUP_POS else "NOT_PICKUP"
        v0_rows.append({"episode_key":r["episode_key"],"source":r["source"],"label":r["label"],
                        "semantic_quality":r["semantic_quality"],"target":target,
                        "prediction":p,"reason":reason,"scorable":int(p in {"PICKUP","NOT_PICKUP"}),
                        "correct":int(p==target) if p in {"PICKUP","NOT_PICKUP"} else ""})
    v0_df = pd.DataFrame(v0_rows)
    write_csv(v0_df, out/"frozen_v0_reconstruction_replay.csv")
    metric_eligible = v0_df[
        ~v0_df["semantic_quality"].isin(["INVALID", "MIXED"])
        & ~v0_df["label"].isin(UNSUPPORTED_V0_LABELS)
    ]
    v0_summary: dict[str,Any] = {
        "episodes":len(v0_df),
        "unknown":int((~v0_df["prediction"].isin(["PICKUP","NOT_PICKUP"])).sum()) if len(v0_df) else 0,
        "quality_excluded":int(v0_df["semantic_quality"].isin(["INVALID","MIXED"]).sum()) if len(v0_df) else 0,
        "unsupported_path_episodes":int(v0_df["label"].isin(UNSUPPORTED_V0_LABELS).sum()) if len(v0_df) else 0,
        "metric_eligible_episodes":int(len(metric_eligible)),
        "metric_eligible_unknown":int((metric_eligible["prediction"] == "UNKNOWN").sum()),
        "config_path": "configs/research/pickup_detector_v0.json",
        "config_sha256": v0_config["_frozen_config_sha256"],
        "note": "Exact frozen-config replay; UNKNOWN is retained and never counted as NOT_PICKUP.",
    }
    scored = v0_df[
        v0_df["prediction"].isin(["PICKUP","NOT_PICKUP"])
        & ~v0_df["semantic_quality"].isin(["INVALID","MIXED"])
    ]
    v0_summary["metric_eligible_definitive"] = int(len(scored))
    if len(scored) and scored["target"].nunique()>1:
        v0_summary.update(binary_summary((scored["target"]=="PICKUP").astype(int), (scored["prediction"]=="PICKUP").astype(int)))
    (out/"frozen_v0_summary.json").write_text(json.dumps(v0_summary,indent=2,ensure_ascii=False),encoding="utf-8")

    # Path A post-hoc V1 model discovery.
    patha = model_df[model_df["label"].isin(STATIONARY_PICKUP_POS | PATH_A_NEG)].copy()
    patha["target"] = (patha["label"].isin(STATIONARY_PICKUP_POS)).astype(int)
    pa_cols = numeric_feature_columns(patha)
    pa_pred, pa_bench = loo_predictions(patha[pa_cols], patha["target"], model_catalog(len(pa_cols),binary=True), patha["episode_key"].tolist())
    write_csv(pa_pred, out/"path_a_predictions.csv")
    write_csv(pa_bench, out/"path_a_benchmarks.csv")

    # Path B episode-family discovery. This is not transition-timestamp validation.
    pathb = model_df[model_df["label"].isin(PATH_B_LABELS)].copy()
    pathb["path_b_state"] = pathb["label"].map({
        "rolling_pickup":"ROLLING_PICKUP", "putt_rail_collision":"COLLISION_RAIL",
        "track_step_drop":"TRACK_STEP_DROP", "rolling":"ROLL_OR_SETTLE",
        "putt_gentle":"ROLL_OR_SETTLE", "putt_normal":"ROLL_OR_SETTLE",
    })
    pb_cols = [c for c in numeric_feature_columns(pathb) if c.startswith(("onset_","post_","active_","tail_","gyro_peak","acc_peak","vertical_"))]
    if len(pathb) >= 4 and pathb["path_b_state"].nunique() >= 2:
        pb_pred, pb_bench = loo_predictions(pathb[pb_cols], pathb["path_b_state"], model_catalog(len(pb_cols)), pathb["episode_key"].tolist())
    else:
        pb_pred, pb_bench = pd.DataFrame(), pd.DataFrame()
    write_csv(pb_pred, out/"path_b_predictions.csv")
    write_csv(pb_bench, out/"path_b_benchmarks.csv")
    if not pb_pred.empty: write_confusion(pb_pred,out,"path_b")

    effects = top_feature_effects(model_df, feature_cols, "state_label")
    write_csv(effects, out/"top_feature_effects.csv")

    class_sessions = model_df.groupby("state_label")["session"].nunique()
    session_confounded = class_sessions[class_sessions < 2].index.tolist()
    audit = {
        "unique_episodes": int(len(df)), "model_episodes": int(len(model_df)),
        "archive_plus_manifest_before_dedup": int(len(all_eps)), "duplicates": int(len(dup)),
        "parse_errors": int(len(parse_errors)), "raw_experiment_files": int(len(raw_audit)),
        "unmanifested_experiment_raw_files": int((raw_audit["represented_by_manifest"]==0).sum()) if len(raw_audit) else 0,
        "labels": {str(k):int(v) for k,v in df["label"].value_counts().items()},
        "semantic_quality": {str(k):int(v) for k,v in df["semantic_quality"].value_counts().items()},
        "devices": int(df["device_id"].nunique()), "boots": int(df["boot_id"].nunique()),
        "sessions": int(df["session"].nunique()), "operators": int(df["operator"].nunique()),
        "median_rate_hz": float(df["observed_rate_hz"].median()),
        "sequence_gap_episodes": int((df["sequence_gaps"]>0).sum()),
        "invalid_sensor_episodes": int((df["valid_fraction"]<1).sum()),
        "adxl_clipped_episodes": int((df["adxl_clip_samples"]>0).sum()),
        "accel_clipped_episodes": int((df["bmi_accel_clip_samples"]>0).sum()),
        "gyro_clipped_episodes": int((df["bmi_gyro_clip_samples"]>0).sum()),
        "class_session_counts": {str(k):int(v) for k,v in class_sessions.items()},
    }
    (out/"dataset_audit.json").write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding="utf-8")
    recommendation = architecture_markdown(audit, bench, v0_summary, pb_bench, session_confounded)
    (out/"ARCHITECTURE_RECOMMENDATION.md").write_text(recommendation,encoding="utf-8")

    index = {
        "audit":"dataset_audit.json", "features":"episode_features.csv",
        "flat_benchmarks":"flat_multiclass_benchmarks.csv", "flat_predictions":"flat_multiclass_predictions.csv",
        "v0":"frozen_v0_reconstruction_replay.csv", "path_a":"path_a_benchmarks.csv", "path_b":"path_b_benchmarks.csv",
        "recommendation":"ARCHITECTURE_RECOMMENDATION.md",
    }
    (out/"INDEX.json").write_text(json.dumps(index,indent=2),encoding="utf-8")
    print(json.dumps({"audit":audit,"best_flat":bench.sort_values("macro_f1",ascending=False).head(3).to_dict("records"),
                      "v0":v0_summary,"path_b":pb_bench.sort_values("macro_f1",ascending=False).head(3).to_dict("records") if not pb_bench.empty else []},
                     indent=2,ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
