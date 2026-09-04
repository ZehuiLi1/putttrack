#!/usr/bin/env python3
"""Train compact PuttTrack emission heads with leakage-safe group validation.

Input is a segment/frame feature CSV produced after independent temporal labels
exist. Random window splits are deliberately unsupported: callers must provide
one or more grouping columns such as day, operator, Ball, core revision and
surface. The exported coefficients are compatible with
``SelectiveLinearSoftmax``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


UNKNOWN = "UNKNOWN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument(
        "--features", required=True, help="comma-separated numeric columns"
    )
    parser.add_argument(
        "--groups",
        required=True,
        help="comma-separated leakage boundary columns, e.g. day,operator,ball_id,surface",
    )
    parser.add_argument("--output-model", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--c", type=float, default=1.0)
    parser.add_argument("--minimum-probability", type=float, default=0.98)
    parser.add_argument("--minimum-margin", type=float, default=0.25)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("input CSV has no rows")
    return rows


def safe_divide(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def metrics(
    y_true: Sequence[str], y_pred: Sequence[str], known_labels: Sequence[str]
) -> dict[str, Any]:
    labels = list(known_labels) + [UNKNOWN]
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    per_class: dict[str, Any] = {}
    f1_values: list[float] = []
    for index, label in enumerate(known_labels):
        tp = int(matrix[index, index])
        fp = int(matrix[:, index].sum() - tp)
        fn = int(matrix[index, :].sum() - tp)
        precision = safe_divide(tp, tp + fp)
        recall = safe_divide(tp, tp + fn)
        score = f1(precision, recall)
        if score is not None:
            f1_values.append(score)
        per_class[label] = {
            "support": int(matrix[index, :].sum()),
            "precision": precision,
            "recall": recall,
            "f1": score,
        }
    return {
        "labels": labels,
        "confusion_matrix": matrix.tolist(),
        "per_class": per_class,
        "macro_f1_known_classes": (
            sum(f1_values) / len(f1_values) if f1_values else None
        ),
        "accuracy_including_unknown": safe_divide(
            sum(true == pred for true, pred in zip(y_true, y_pred)), len(y_true)
        ),
        "unknown_rate": safe_divide(
            sum(pred == UNKNOWN for pred in y_pred), len(y_pred)
        ),
    }


def selective_prediction(
    probabilities: np.ndarray,
    labels: Sequence[str],
    min_p: float,
    min_margin: float,
) -> list[str]:
    output: list[str] = []
    for row in probabilities:
        order = np.argsort(row)[::-1]
        best_index = int(order[0])
        best = float(row[best_index])
        second = float(row[int(order[1])]) if len(order) > 1 else 0.0
        output.append(
            str(labels[best_index])
            if best >= min_p and best - second >= min_margin
            else UNKNOWN
        )
    return output


def build_pipeline(c: float) -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=c,
                    l1_ratio=0.0,
                    solver="lbfgs",
                    class_weight="balanced",
                    max_iter=5000,
                ),
            ),
        ]
    )


def export_linear_spec(
    pipeline: Pipeline, feature_names: Sequence[str]
) -> dict[str, Any]:
    scaler: StandardScaler = pipeline.named_steps["scale"]
    model: LogisticRegression = pipeline.named_steps["model"]
    labels = [str(item) for item in model.classes_]
    coefficients = model.coef_
    intercepts = model.intercept_

    if len(labels) == 2 and coefficients.shape[0] == 1:
        weight = coefficients[0]
        intercept = float(intercepts[0])
        coefficient_map = {
            labels[0]: (-0.5 * weight).tolist(),
            labels[1]: (0.5 * weight).tolist(),
        }
        intercept_map = {
            labels[0]: -0.5 * intercept,
            labels[1]: 0.5 * intercept,
        }
    else:
        coefficient_map = {
            label: coefficients[index].tolist()
            for index, label in enumerate(labels)
        }
        intercept_map = {
            label: float(intercepts[index]) for index, label in enumerate(labels)
        }

    return {
        "schema_version": 1,
        "model_type": "standard_scaler_plus_logistic_softmax",
        "labels": labels,
        "feature_order": list(feature_names),
        "means": scaler.mean_.tolist(),
        "scales": scaler.scale_.tolist(),
        "coefficients": coefficient_map,
        "intercepts": intercept_map,
        "unknown_policy": "UNKNOWN is added by probability/margin/quality abstention, not fitted as an ordinary class unless explicitly present in training labels",
    }


def main() -> int:
    args = parse_args()
    features = [item.strip() for item in args.features.split(",") if item.strip()]
    group_columns = [
        item.strip() for item in args.groups.split(",") if item.strip()
    ]
    rows = read_rows(args.input_csv)
    required = [args.target, *features, *group_columns]
    missing = [column for column in required if column not in rows[0]]
    if missing:
        raise ValueError(f"missing CSV columns: {missing}")

    usable: list[dict[str, str]] = []
    excluded: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        try:
            numeric = [float(row[name]) for name in features]
        except (TypeError, ValueError):
            excluded.append({"row": index + 2, "reason": "non_numeric_feature"})
            continue
        if not all(math.isfinite(value) for value in numeric):
            excluded.append({"row": index + 2, "reason": "non_finite_feature"})
            continue
        if not row[args.target].strip():
            excluded.append({"row": index + 2, "reason": "missing_target"})
            continue
        if any(not row[column].strip() for column in group_columns):
            excluded.append({"row": index + 2, "reason": "missing_group_field"})
            continue
        usable.append(row)

    if len(usable) < 2:
        raise ValueError("fewer than two usable rows")
    x = np.asarray(
        [[float(row[name]) for name in features] for row in usable], dtype=float
    )
    y = np.asarray([row[args.target].strip() for row in usable], dtype=object)
    groups = np.asarray(
        [
            "|".join(row[column].strip() for column in group_columns)
            for row in usable
        ],
        dtype=object,
    )
    labels = sorted({str(item) for item in y})
    unique_groups = sorted({str(item) for item in groups})
    if len(unique_groups) < 2:
        raise ValueError("at least two independent groups are required")

    logo = LeaveOneGroupOut()
    held_out_predictions: list[str] = [UNKNOWN] * len(usable)
    fold_records: list[dict[str, Any]] = []
    for fold, (train_indices, test_indices) in enumerate(
        logo.split(x, y, groups), 1
    ):
        train_labels = sorted({str(item) for item in y[train_indices]})
        if len(train_labels) < 2:
            fold_records.append(
                {
                    "fold": fold,
                    "held_out_group": str(groups[test_indices[0]]),
                    "status": "ABSTAINED_TRAINING_SINGLE_CLASS",
                    "test_rows": [int(index) for index in test_indices],
                }
            )
            continue
        pipeline = build_pipeline(args.c)
        pipeline.fit(x[train_indices], y[train_indices])
        probabilities = pipeline.predict_proba(x[test_indices])
        fold_labels = [
            str(item) for item in pipeline.named_steps["model"].classes_
        ]
        predictions = selective_prediction(
            probabilities,
            fold_labels,
            args.minimum_probability,
            args.minimum_margin,
        )
        for index, prediction in zip(test_indices, predictions):
            held_out_predictions[int(index)] = prediction
        fold_records.append(
            {
                "fold": fold,
                "held_out_group": str(groups[test_indices[0]]),
                "status": "PASS",
                "train_labels": train_labels,
                "test_rows": [int(index) for index in test_indices],
                "predictions": predictions,
            }
        )

    report = {
        "schema_version": 1,
        "evaluation": "LeaveOneGroupOut; scaler/model fitted inside each fold",
        "group_columns": group_columns,
        "features": features,
        "target": args.target,
        "usable_rows": len(usable),
        "excluded_rows": excluded,
        "groups": unique_groups,
        "selective_thresholds": {
            "minimum_probability": args.minimum_probability,
            "minimum_margin": args.minimum_margin,
        },
        "metrics": metrics([str(item) for item in y], held_out_predictions, labels),
        "folds": fold_records,
        "predictions": [
            {
                "row_index": index,
                "group": str(groups[index]),
                "target": str(y[index]),
                "prediction": held_out_predictions[index],
            }
            for index in range(len(usable))
        ],
        "warning": "This is valid only to the extent that each group is physically independent. Do not replace group columns with adjacent-window IDs.",
    }

    final_pipeline = build_pipeline(args.c)
    final_pipeline.fit(x, y)
    model_payload = export_linear_spec(final_pipeline, features)
    model_payload.update(
        {
            "training_rows": len(usable),
            "training_groups": unique_groups,
            "group_columns": group_columns,
            "selective_thresholds": report["selective_thresholds"],
            "authority": False,
        }
    )

    args.output_model.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_model.write_text(
        json.dumps(model_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["metrics"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
