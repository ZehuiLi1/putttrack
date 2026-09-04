#!/usr/bin/env python3
"""Reproduce the 2026-09-04 three-feature pickup LOEO baselines.

This script intentionally does NOT evaluate the post-hoc physics rule as LOEO
and does NOT reproduce the legacy "full-feature" rows whose original feature
definition was not preserved.
"""

from __future__ import annotations

import csv
from pathlib import Path

try:
    import numpy as np
    import sklearn
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        confusion_matrix,
        matthews_corrcoef,
        precision_recall_fscore_support,
    )
    from sklearn.model_selection import LeaveOneOut
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    from sklearn.tree import DecisionTreeClassifier
except ImportError as exc:
    raise SystemExit(
        "This snapshot reproduction requires scikit-learn==1.8.0. "
        "Install the repository's optional 'research-ml' extra."
    ) from exc


EXPECTED_SKLEARN = "1.8.0"
FEATURES = (
    "vertical_impulse_pos_0p6",
    "gyro_mean_1s",
    "gyro_axis_consistency_1s",
)
EXPECTED = {
    "logistic_3f": (10, 1, 0, 11),
    "linear_svm_3f": (10, 1, 0, 11),
    "rbf_svm_3f": (10, 1, 0, 11),
    "tree_depth2_3f": (10, 1, 1, 10),
    "rf_3f": (10, 1, 0, 11),
}


def _models():
    return {
        "logistic_3f": Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000),
                ),
            ]
        ),
        "linear_svm_3f": Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", SVC(kernel="linear", C=1.0, gamma="scale")),
            ]
        ),
        "rbf_svm_3f": Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", SVC(kernel="rbf", C=1.0, gamma="scale")),
            ]
        ),
        "tree_depth2_3f": DecisionTreeClassifier(max_depth=2, random_state=42),
        "rf_3f": RandomForestClassifier(n_estimators=200, random_state=42),
    }


def _load_ledger(path: Path):
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    if len(rows) != 22:
        raise SystemExit(f"expected 22 snapshot episodes, found {len(rows)}")
    x = np.asarray([[float(row[name]) for name in FEATURES] for row in rows])
    y = np.asarray([int(row["target"]) for row in rows], dtype=int)
    return rows, x, y


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    snapshot_dir = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "research"
        / "imu_analysis_20260904"
    )
    episode_rows, x, y = _load_ledger(snapshot_dir / "pickup_binary_research_set.csv")

    if sklearn.__version__ != EXPECTED_SKLEARN:
        raise SystemExit(
            f"snapshot requires scikit-learn {EXPECTED_SKLEARN}; found {sklearn.__version__}"
        )

    fold_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for model_name, prototype in _models().items():
        predictions = np.empty_like(y)
        for fold, (train_index, test_index) in enumerate(LeaveOneOut().split(x), 1):
            model = prototype
            model.fit(x[train_index], y[train_index])
            prediction = int(model.predict(x[test_index])[0])
            held_out = int(test_index[0])
            predictions[held_out] = prediction
            fold_rows.append(
                {
                    "model": model_name,
                    "fold": fold,
                    "held_out_index": held_out,
                    "path": episode_rows[held_out]["path"],
                    "label": episode_rows[held_out]["label"],
                    "target": int(y[held_out]),
                    "prediction": prediction,
                    "correct": int(prediction == y[held_out]),
                }
            )

        tn, fp, fn, tp = (
            int(value)
            for value in confusion_matrix(y, predictions, labels=[0, 1]).ravel()
        )
        expected = EXPECTED[model_name]
        if (tn, fp, fn, tp) != expected:
            raise SystemExit(
                f"{model_name}: expected confusion {expected}, observed {(tn, fp, fn, tp)}"
            )

        precision, recall, f1, _ = precision_recall_fscore_support(
            y, predictions, average="binary", zero_division=0
        )
        summary_rows.append(
            {
                "model": model_name,
                "evaluation_scope": "reproduced_leave_one_episode_out",
                "reproducible_from_repo": "yes",
                "accuracy": f"{accuracy_score(y, predictions):.10f}",
                "balanced_accuracy": f"{balanced_accuracy_score(y, predictions):.10f}",
                "pickup_precision": f"{precision:.10f}",
                "pickup_recall": f"{recall:.10f}",
                "pickup_f1": f"{f1:.10f}",
                "mcc": f"{matthews_corrcoef(y, predictions):.10f}",
                "tn": tn,
                "fp": fp,
                "fn": fn,
                "tp": tp,
            }
        )

    _write_csv(
        snapshot_dir / "model_benchmark_fold_predictions_3f.csv",
        [
            "model",
            "fold",
            "held_out_index",
            "path",
            "label",
            "target",
            "prediction",
            "correct",
        ],
        fold_rows,
    )
    _write_csv(
        snapshot_dir / "model_benchmark_reproduced_3f.csv",
        [
            "model",
            "evaluation_scope",
            "reproducible_from_repo",
            "accuracy",
            "balanced_accuracy",
            "pickup_precision",
            "pickup_recall",
            "pickup_f1",
            "mcc",
            "tn",
            "fp",
            "fn",
            "tp",
        ],
        summary_rows,
    )
    print(
        "PASS: reproduced five three-feature LOEO baselines "
        f"from {len(episode_rows)} preserved episodes using scikit-learn {sklearn.__version__}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
