"""Generate 200 synthetic groups and summarize timing baseline scores.

Run from the repository root:
    python -m src.analysis.run_synthetic_grid
"""

import csv
import json
import math
import random
import statistics
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from src.baselines.statistical import score_flow


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data/synthetic/grid-v1"
OUT_DIR = ROOT / "outputs/synthetic-grid-v1"

EVENT_COUNTS = (10, 20, 50, 100)
JITTER_LEVELS = (0, 5, 10, 20, 40)
SEEDS = range(10)
PERIOD_SECONDS = 60.0
MIN_EVENTS = 5


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_group(event_count, jitter_percent, seed):
    # Khởi tạo riêng cho từng nhóm để có thể tái tạo độc lập.
    rng = random.Random(seed)
    fraction = jitter_percent / 100.0

    deltas = [
        round(
            rng.uniform(
                PERIOD_SECONDS * (1 - fraction),
                PERIOD_SECONDS * (1 + fraction),
            ),
            6,
        )
        for _ in range(event_count - 1)
    ]

    relative_times = [0.0]
    for delta in deltas:
        relative_times.append(relative_times[-1] + delta)

    start = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    timestamps = [
        (start + timedelta(seconds=value)).isoformat(
            timespec="microseconds"
        )
        for value in relative_times
    ]

    flow_id = (
        f"synthetic-grid-v1|n-{event_count}"
        f"|jitter-{jitter_percent}|seed-{seed}"
    )

    # Cấu trúc tương tự bộ smoke-v1 đã chạy thành công.
    flow = {
        "schema_version": "synthetic-smoke-v1",
        "flow_id": flow_id,
        "source": "synthetic",
        "event_count": event_count,
        "timestamps": timestamps,
        "timestamp_basis": "synthetic_UTC",
        "relative_times_seconds": relative_times,
        "time_deltas": deltas,
        "bytes_sent": [500] * event_count,
        "bytes_semantics": "synthetic_source_bytes",
    }

    if not (
        len(timestamps) == event_count
        and len(relative_times) == event_count
        and len(deltas) == event_count - 1
        and len(flow["bytes_sent"]) == event_count
        and all(math.isfinite(d) and d > 0 for d in deltas)
    ):
        raise ValueError(f"Invalid generated group: {flow_id}")

    metadata = {
        "flow_id": flow_id,
        "event_count": event_count,
        "period_seconds": PERIOD_SECONDS,
        "jitter_percent": jitter_percent,
        "seed": seed,
    }
    return flow, metadata


def main():
    flows = []
    metadata = []

    for event_count in EVENT_COUNTS:
        for jitter_percent in JITTER_LEVELS:
            for seed in SEEDS:
                flow, meta = make_group(
                    event_count, jitter_percent, seed
                )
                flows.append(flow)
                metadata.append(meta)

    flow_ids = [flow["flow_id"] for flow in flows]
    if len(flow_ids) != len(set(flow_ids)):
        raise ValueError("Duplicate flow_id")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (DATA_DIR / "groups.json").write_text(
        json.dumps(flows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(DATA_DIR / "metadata.csv", metadata)

    # Các cấu hình này thuộc bộ sinh dữ liệu, không phải nhãn mã độc.
    (DATA_DIR / "generation_config.json").write_text(
        json.dumps(
            {
                "generator_version": "synthetic-grid-v1",
                "event_counts": EVENT_COUNTS,
                "jitter_percent_levels": JITTER_LEVELS,
                "seeds": list(SEEDS),
                "period_seconds": PERIOD_SECONDS,
                "distribution": "uniform",
                "round_delta_decimals": 6,
                "bytes_per_event": 500,
                "seed_policy": (
                    "reset Random(seed) for each configuration; "
                    "paired comparisons across configurations"
                ),
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    # Chỉ đưa flow vào hàm baseline, không truyền metadata.
    scores = []
    for flow in flows:
        try:
            result = score_flow(flow, MIN_EVENTS)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            result = {
                "flow_id": flow["flow_id"],
                "method": "timing_cv_baseline",
                "event_count": flow["event_count"],
                "score": None,
                "status": "error",
                "reason": f"{type(error).__name__}: {error}",
            }

        if result["flow_id"] != flow["flow_id"]:
            raise ValueError("Output flow_id does not match input")

        status = result["status"]
        if status not in {"ok", "skipped", "error"}:
            raise ValueError(f"Unexpected status: {status}")

        if status == "ok":
            value = result["score"]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError("Invalid score")
        elif result["score"] is not None or not result.get("reason"):
            raise ValueError("Invalid skipped/error output")

        scores.append(result)

    (OUT_DIR / "scores.json").write_text(
        json.dumps(
            {
                "method": "timing_cv_baseline",
                "min_events": MIN_EVENTS,
                "scores": scores,
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )

    # Ghép cấu hình với điểm sau khi chấm xong.
    score_by_id = {row["flow_id"]: row for row in scores}
    detail = []

    for meta in metadata:
        result = score_by_id[meta["flow_id"]]
        detail.append({
            **meta,
            "score": result["score"],
            "status": result["status"],
            "reason": result.get("reason", ""),
        })

    write_csv(OUT_DIR / "detail.csv", detail)

    summary = []
    for event_count in EVENT_COUNTS:
        for jitter_percent in JITTER_LEVELS:
            selected = [
                row for row in detail
                if row["event_count"] == event_count
                and row["jitter_percent"] == jitter_percent
            ]
            values = [
                row["score"]
                for row in selected
                if row["status"] == "ok"
            ]
            counts = Counter(row["status"] for row in selected)

            summary.append({
                "event_count": event_count,
                "jitter_percent": jitter_percent,
                "groups_total": len(selected),
                "groups_ok": counts["ok"],
                "groups_skipped": counts["skipped"],
                "groups_error": counts["error"],
                "score_mean": (
                    statistics.mean(values) if values else ""
                ),
                # Độ lệch chuẩn mẫu giữa các lần sinh: ddof=1.
                "score_std_across_seeds": (
                    statistics.stdev(values)
                    if len(values) >= 2 else ""
                ),
                "score_min": min(values) if values else "",
                "score_max": max(values) if values else "",
            })

    write_csv(OUT_DIR / "summary.csv", summary)

    overall = Counter(row["status"] for row in scores)
    print(
        f"Groups: {len(flows)}; "
        f"ok: {overall['ok']}; "
        f"skipped: {overall['skipped']}; "
        f"error: {overall['error']}"
    )
    print(f"Summary rows: {len(summary)}")
    print(f"Summary: {OUT_DIR / 'summary.csv'}")
    print(f"Details: {OUT_DIR / 'detail.csv'}")


if __name__ == "__main__":
    main()