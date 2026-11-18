"""Run the existing timing baseline on synthetic smoke-test groups."""

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

from src.baselines.statistical import score_flow


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT = ROOT / "data/synthetic/smoke-v1/groups.json"
DEFAULT_REFERENCE = ROOT / "data/synthetic/smoke-v1/reference_stats.csv"
DEFAULT_OUT_DIR = ROOT / "outputs/synthetic-smoke-v1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--reference", type=Path, default=DEFAULT_REFERENCE
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-events", type=int, default=5)
    args = parser.parse_args()

    if args.min_events < 2:
        parser.error("--min-events must be >= 2")

    flows = json.loads(args.input.read_text(encoding="utf-8"))

    if not isinstance(flows, list) or not flows:
        raise ValueError("Input must be a non-empty JSON array")

    flow_ids = [flow["flow_id"] for flow in flows]
    if len(flow_ids) != len(set(flow_ids)):
        raise ValueError("Duplicate flow_id in input")

    # Chấm điểm chỉ từ dữ liệu đầu vào.
    scores = []
    for flow in flows:
        try:
            record = score_flow(flow, args.min_events)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            record = {
                "flow_id": flow["flow_id"],
                "method": "timing_cv_baseline",
                "event_count": flow["event_count"],
                "score": None,
                "status": "error",
                "reason": f"{type(error).__name__}: {error}",
            }

        if record["flow_id"] != flow["flow_id"]:
            raise ValueError("score_flow returned a different flow_id")

        if record["status"] not in {"ok", "skipped", "error"}:
            raise ValueError("Unexpected score status")

        if record["status"] == "ok":
            value = record["score"]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError("Invalid score for an ok record")
        elif record["score"] is not None or not record.get("reason"):
            raise ValueError("Invalid skipped/error record")

        scores.append(record)

    # Đọc bảng tham chiếu sau khi đã chấm xong.
    with args.reference.open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        reference_rows = list(csv.DictReader(handle))

    reference = {row["flow_id"]: row for row in reference_rows}

    if len(reference) != len(reference_rows):
        raise ValueError("Duplicate flow_id in reference CSV")

    if set(reference) != set(flow_ids):
        raise ValueError("Reference IDs do not match input IDs")

    comparison = []
    for record in scores:
        ref = reference[record["flow_id"]]
        expected = float(ref["reference_score"])

        if record["status"] == "ok":
            difference = abs(record["score"] - expected)
            matches = math.isclose(
                record["score"],
                expected,
                rel_tol=0.0,
                abs_tol=5e-7,
            )
        else:
            difference = ""
            matches = ""

        comparison.append({
            "flow_id": record["flow_id"],
            "pattern": ref["pattern"],
            "event_count": record["event_count"],
            "mean_delta_seconds": ref["mean_delta_seconds"],
            "std_delta_seconds": ref["std_delta_seconds"],
            "cv": ref["cv"],
            "reference_score": expected,
            "baseline_score": record["score"],
            "absolute_difference": difference,
            "matches_reference": matches,
            "status": record["status"],
            "reason": record.get("reason", ""),
        })

    args.out_dir.mkdir(parents=True, exist_ok=True)

    scores_path = args.out_dir / "scores.json"
    scores_path.write_text(
        json.dumps(
            {
                "method": "timing_cv_baseline",
                "min_events": args.min_events,
                "scores": scores,
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )

    comparison_path = args.out_dir / "comparison.csv"
    with comparison_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(comparison[0])
        )
        writer.writeheader()
        writer.writerows(comparison)

    counts = Counter(record["status"] for record in scores)
    print(
        f"Groups: {len(scores)}; "
        f"ok: {counts['ok']}; "
        f"skipped: {counts['skipped']}; "
        f"error: {counts['error']}"
    )

    for row in comparison:
        score = row["baseline_score"]
        score_text = "" if score is None else f"{score:.6f}"
        print(
            f"{row['pattern']}: "
            f"score={score_text}, "
            f"matches={row['matches_reference']}, "
            f"status={row['status']}"
        )

    print(f"Comparison: {comparison_path}")
    print(f"Scores: {scores_path}")


if __name__ == "__main__":
    main()