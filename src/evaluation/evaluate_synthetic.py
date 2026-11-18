import argparse
import csv
import json
import math
from pathlib import Path


def load_by_id(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError(f"Empty file: {path}")

    result = {}
    for row in rows:
        flow_id = row["flow_id"]
        if flow_id in result:
            raise ValueError(f"Duplicate flow_id: {flow_id}")
        result[flow_id] = row
    return result


def divide(a, b):
    return a / b if b else None


def calculate_metrics(rows, threshold):
    tp = fp = fn = tn = 0

    for row in rows:
        actual = row["actual"]
        predicted = int(row["score"] >= threshold)

        if actual == 1 and predicted == 1:
            tp += 1
        elif actual == 0 and predicted == 1:
            fp += 1
        elif actual == 1 and predicted == 0:
            fn += 1
        else:
            tn += 1

    return {
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": divide(tp, tp + fp),
        "recall": divide(tp, tp + fn),
        "f1": divide(2 * tp, 2 * tp + fp + fn),
        "fpr": divide(fp, fp + tn),
    }


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--select", action="store_true")
    mode.add_argument("--threshold-file", type=Path)

    args = parser.parse_args()

    scores = load_by_id(args.scores)
    labels = load_by_id(args.labels)

    if set(scores) != set(labels):
        raise ValueError("Score IDs and label IDs do not match")

    expected_split = "dev" if args.select else "test"
    splits = {row["split"] for row in labels.values()}
    if splits != {expected_split}:
        raise ValueError(
            f"This mode requires split={expected_split}; got {splits}"
        )

    joined = []
    for flow_id, score_row in scores.items():
        if score_row["status"] != "ok":
            raise ValueError(
                f"Non-ok group: {flow_id}. "
                "Resolve or define an exclusion policy before evaluating."
            )

        score = float(score_row["score"])
        actual = int(labels[flow_id]["periodic_label"])

        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError(f"Invalid score: {flow_id}")
        if actual not in {0, 1}:
            raise ValueError(f"Invalid label: {flow_id}")

        joined.append({
            "flow_id": flow_id,
            "pattern": labels[flow_id]["pattern"],
            "actual": actual,
            "score": score,
        })

    if {row["actual"] for row in joined} != {0, 1}:
        raise ValueError("Evaluation requires both label classes")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.select:
        # Thử toàn bộ ranh giới dự đoán có thể có trên điểm dev.
        # Thêm ngưỡng trên điểm lớn nhất để xét cả trường hợp
        # không dự đoán nhóm nào là dương tính.
        candidates = sorted(
            {row["score"] for row in joined}
            | {
                math.nextafter(
                    max(row["score"] for row in joined),
                    math.inf,
                )
            }
        )
        sweep = [
            calculate_metrics(joined, threshold)
            for threshold in candidates
        ]

        # Quy tắc chốt trước:
        # F1 cao nhất -> FPR thấp nhất -> ngưỡng cao nhất.
        best = max(
            sweep,
            key=lambda row: (
                row["f1"],
                -row["fpr"],
                row["threshold"],
            ),
        )
        threshold = best["threshold"]

        write_csv(args.out_dir / "threshold_sweep.csv", sweep)

        (args.out_dir / "selected_threshold.json").write_text(
            json.dumps(
                {
                    "threshold": threshold,
                    "prediction_rule": "score >= threshold",
                    "selection_split": "dev",
                    "selection_rule": (
                        "max F1, then min FPR, then max threshold"
                    ),
                    "method": "timing_cv_baseline",
                    "target": "synthetic periodic timing behavior",
                    "scores_source": str(args.scores),
                    "labels_source": str(args.labels),
                },
                indent=2,
                allow_nan=False,
            ) + "\n",
            encoding="utf-8",
        )
    else:
        config = json.loads(
            args.threshold_file.read_text(encoding="utf-8")
        )
        if config["selection_split"] != "dev":
            raise ValueError("Threshold must have been selected on dev")
        threshold = float(config["threshold"])
        if not math.isfinite(threshold):
            raise ValueError("Invalid threshold")

    metrics = calculate_metrics(joined, threshold)
    write_csv(args.out_dir / "metrics.csv", [metrics])

    predictions = []
    for row in joined:
        predicted = int(row["score"] >= threshold)
        outcome = (
            "TP" if row["actual"] == 1 and predicted == 1
            else "FN" if row["actual"] == 1
            else "FP" if predicted == 1
            else "TN"
        )
        predictions.append({
            **row,
            "predicted": predicted,
            "outcome": outcome,
        })

    write_csv(args.out_dir / "predictions.csv", predictions)

    # Đọc riêng từng loại mẫu để tránh chỉ nhìn chỉ số tổng.
    by_pattern = []
    for pattern in sorted({row["pattern"] for row in joined}):
        subset = [row for row in joined if row["pattern"] == pattern]
        by_pattern.append({
            "pattern": pattern,
            "groups": len(subset),
            **calculate_metrics(subset, threshold),
        })
    write_csv(args.out_dir / "metrics_by_pattern.csv", by_pattern)

    print(json.dumps(metrics, indent=2, allow_nan=False))
    print(f"Output: {args.out_dir}")


if __name__ == "__main__":
    main()