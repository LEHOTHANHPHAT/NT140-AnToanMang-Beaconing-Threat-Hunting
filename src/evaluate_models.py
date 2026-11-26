"""Score HMM, CT-HMM, TSD and the ensemble on a labelled synthetic dataset.

Protocol (same as src/evaluation/evaluate_synthetic.py): labels are only
joined after scoring; the decision threshold is chosen on dev (max F1, then
min FPR, then max threshold) and applied unchanged to test. AUC is computed
on test over scored groups.

Usage:
    python -m src.evaluate_models \
        --dataset data/synthetic/evaluation-v1 \
        --config configs/default.json \
        --out-dir outputs/model-evaluation-v1
"""

import argparse
import csv
import json
import math
import time
from pathlib import Path

from src.evaluation.evaluate_synthetic import calculate_metrics
from src.models import ct_hmm, ensemble, hmm, tsd

MODELS = ("hmm", "ct_hmm", "tsd", "ensemble")


def load_labels(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {row["flow_id"]: row for row in csv.DictReader(handle)}


def score_split(flows, config):
    """Return ({model: records}, {model: seconds})."""
    records, seconds = {}, {}
    for name, module in (("hmm", hmm), ("ct_hmm", ct_hmm), ("tsd", tsd)):
        start = time.perf_counter()
        records[name] = module.score_flows(flows, config)
        seconds[name] = time.perf_counter() - start

    state_model = config.get("ensemble", {}).get("state_model", "ct_hmm")
    start = time.perf_counter()
    records["ensemble"] = ensemble.score_flows(
        flows, records[state_model], records["tsd"], config,
    )
    # Ensemble cost includes its components.
    seconds["ensemble"] = (
        time.perf_counter() - start + seconds[state_model] + seconds["tsd"]
    )
    return records, seconds


def roc_auc(rows):
    """Mann-Whitney AUC; ties count one half."""
    positives = [r["score"] for r in rows if r["actual"] == 1]
    negatives = [r["score"] for r in rows if r["actual"] == 0]
    if not positives or not negatives:
        return None
    wins = sum(
        1.0 if p > n else 0.5 if p == n else 0.0
        for p in positives for n in negatives
    )
    return wins / (len(positives) * len(negatives))


def select_threshold(rows):
    if not rows:
        return None
    candidates = sorted(
        {r["score"] for r in rows}
        | {math.nextafter(max(r["score"] for r in rows), math.inf)}
    )
    sweep = [calculate_metrics(rows, t) for t in candidates]
    best = max(sweep, key=lambda m: (m["f1"] or 0.0, -(m["fpr"] or 0.0), m["threshold"]))
    return best["threshold"]


def joined_rows(records, labels):
    rows = []
    for record in records:
        label = labels[record["flow_id"]]
        rows.append({
            "flow_id": record["flow_id"],
            "pattern": label["pattern"],
            "actual": int(label["periodic_label"]),
            "score": record["score"],
            "status": record["status"],
            "skip_reason": record.get("skip_reason", ""),
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/synthetic/evaluation-v1"))
    parser.add_argument("--config", type=Path, default=Path("configs/default.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/model-evaluation-v1"))
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    split_rows, split_seconds = {}, {}
    for split in ("dev", "test"):
        flows = json.loads((args.dataset / split / "groups.json").read_text(encoding="utf-8"))
        labels = load_labels(args.dataset / split / "labels.csv")
        records, seconds = score_split(flows, config)
        split_rows[split] = {m: joined_rows(records[m], labels) for m in MODELS}
        split_seconds[split] = seconds

    summary, by_pattern, score_rows = [], [], []
    for model in MODELS:
        test_rows = split_rows["test"][model]
        dev_scored = [r for r in split_rows["dev"][model] if r["score"] is not None]
        scored = [r for r in test_rows if r["score"] is not None]
        threshold = select_threshold(dev_scored)
        metrics = calculate_metrics(scored, threshold) if threshold is not None and scored else {}
        auc = roc_auc(scored)
        summary.append({
            "model": model,
            "test_groups": len(test_rows),
            "scored": len(scored),
            "skipped": len(test_rows) - len(scored),
            "partial_scored": sum(r["status"] == "partial_scored" for r in test_rows),
            "auc": round(auc, 4) if auc is not None else None,
            "dev_threshold": threshold,
            "f1": round(metrics["f1"], 4) if metrics.get("f1") is not None else None,
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "fpr": metrics.get("fpr"),
            "test_seconds": round(split_seconds["test"][model], 2),
        })
        for pattern in sorted({r["pattern"] for r in test_rows}):
            group = [r for r in test_rows if r["pattern"] == pattern]
            values = [r["score"] for r in group if r["score"] is not None]
            by_pattern.append({
                "model": model,
                "pattern": pattern,
                "periodic_label": group[0]["actual"],
                "groups": len(group),
                "scored": len(values),
                "mean_score": round(sum(values) / len(values), 4) if values else None,
                "min_score": round(min(values), 4) if values else None,
                "max_score": round(max(values), 4) if values else None,
            })
        score_rows.extend({"model": model, **r} for r in test_rows)

    for name, rows in (("summary.csv", summary), ("by_pattern.csv", by_pattern),
                       ("test_scores.csv", score_rows)):
        with (args.out_dir / name).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    for row in summary:
        print(row)
    for row in by_pattern:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
