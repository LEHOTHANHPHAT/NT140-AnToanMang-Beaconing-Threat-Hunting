"""Score every prepared CTU-13 group, then join labels for analysis only.

Run from the repository root: python -m src.analysis.run_ctu13_baseline
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from src.baselines.statistical import score_flow


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data/processed/ctu13/scenario-01-tcp"
SCORES_PATH = ROOT / "outputs/scores/ctu13-scenario01-timing-baseline.json"
RANKING_PATH = ROOT / "outputs/ctu13-scenario01-timing-baseline-ranking.csv"
RANKING_FIELDS = (
    "rank", "flow_id", "method", "event_count", "score", "status", "reason",
    "category", "cc_annotated_rows",
)


def unique_by_id(records, name):
    result = {record["flow_id"]: record for record in records}
    if len(result) != len(records):
        raise ValueError(f"Duplicate flow_id in {name}")
    return result


def score_flows(flows, min_events):
    """Use the existing score formula; retain an explicit error record per bad flow."""
    scores = []
    for flow in flows:
        try:
            record = score_flow(flow, min_events)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            record = {
                "flow_id": flow["flow_id"], "method": "timing_cv_baseline",
                "event_count": flow["event_count"], "score": None,
                "status": "error", "reason": f"{type(error).__name__}: {error}",
            }
        scores.append(record)
    return scores


def rank_scores(scores, labels):
    """Rank all scored groups; retain skipped/error rows with an empty rank."""
    scored = sorted((record for record in scores if record["status"] == "ok"),
                    key=lambda record: (-record["score"], record["flow_id"]))
    unscored = sorted((record for record in scores if record["status"] != "ok"),
                      key=lambda record: record["flow_id"])
    rows = []
    for rank, record in enumerate(scored, start=1):
        rows.append({"rank": rank, **record,
                     "category": labels[record["flow_id"]]["category"],
                     "cc_annotated_rows": labels[record["flow_id"]]["cc_annotated_rows"]})
    for record in unscored:
        rows.append({"rank": "", **record,
                     "category": labels[record["flow_id"]]["category"],
                     "cc_annotated_rows": labels[record["flow_id"]]["cc_annotated_rows"]})
    return rows


def run(data_dir=DATA_DIR, scores_path=SCORES_PATH, ranking_path=RANKING_PATH,
        min_events=5):
    if isinstance(min_events, bool) or not isinstance(min_events, int) or min_events < 2:
        raise ValueError("min_events must be an integer >= 2")
    flows_data = json.loads((data_dir / "flows.json").read_text(encoding="utf-8"))
    if flows_data.get("schema_version") != "1.1":
        raise ValueError("Expected CTU-13 flows schema_version 1.1")
    flows = flows_data["flows"]
    flow_ids = unique_by_id(flows, "flows.json")
    scores = score_flows(flows, min_events)
    score_ids = unique_by_id(scores, "scores")
    if len(scores) != len(flows) or set(score_ids) != set(flow_ids):
        raise ValueError("Score count or flow_id set does not match the input")
    counts = Counter(record["status"] for record in scores)
    if set(counts) - {"ok", "skipped", "error"}:
        raise ValueError("Unexpected score status")
    if any((record["score"] is None) != (record["status"] != "ok") or
           (record["status"] != "ok" and not record["reason"]) for record in scores):
        raise ValueError("Score/status/reason mismatch")

    # Labels are loaded only after every score has been computed and validated.
    labels_data = json.loads((data_dir / "labels.json").read_text(encoding="utf-8"))
    if labels_data.get("schema_version") != "1.0":
        raise ValueError("Expected CTU-13 labels schema_version 1.0")
    if labels_data.get("run_id") != flows_data.get("run_id"):
        raise ValueError("Input run_id values do not match")
    labels = unique_by_id(labels_data["labels"], "labels.json")
    if set(labels) != set(score_ids):
        raise ValueError("Label flow_id set does not match scores")
    ranking = rank_scores(scores, labels)
    if len(ranking) != len(scores):
        raise ValueError("Ranking count does not match scores")

    result = {
        "schema_version": "1.1", "source_schema_version": "1.1",
        "source_run_id": flows_data["run_id"],
        "dataset_id": flows_data["source"]["dataset_id"],
        "method": "timing_cv_baseline", "min_events": min_events,
        "counts": {status: counts[status] for status in ("ok", "skipped", "error")},
        "scores": scores,
    }
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    ranking_path.parent.mkdir(parents=True, exist_ok=True)
    scores_path.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                      allow_nan=False) + "\n", encoding="utf-8")
    with ranking_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RANKING_FIELDS)
        writer.writeheader()
        writer.writerows(ranking)
    return result, ranking


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--scores-out", type=Path, default=SCORES_PATH)
    parser.add_argument("--ranking-out", type=Path, default=RANKING_PATH)
    parser.add_argument("--min-events", type=int, default=5)
    args = parser.parse_args()
    try:
        result, ranking = run(args.data_dir, args.scores_out, args.ranking_out,
                              args.min_events)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Error: {error}\n")
    print(f"Groups: {len(result['scores'])}; "
          f"ok: {result['counts']['ok']}; skipped: {result['counts']['skipped']}; "
          f"error: {result['counts']['error']}")
    print(f"Scores: {args.scores_out}")
    print(f"Ranking: {args.ranking_out} ({len(ranking)} rows)")


if __name__ == "__main__":
    main()
