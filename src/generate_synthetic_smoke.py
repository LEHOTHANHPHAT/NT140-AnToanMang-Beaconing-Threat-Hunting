import argparse
import csv
import json
import random
import statistics
from datetime import datetime, timedelta
from pathlib import Path


def build_record(pattern, deltas, start, event_count, seed):
    relative_times = [0.0]

    for delta in deltas:
        relative_times.append(relative_times[-1] + delta)

    timestamps = [
        (start + timedelta(seconds=seconds)).isoformat(
            timespec="microseconds"
        )
        for seconds in relative_times
    ]

    return {
        "schema_version": "synthetic-smoke-v1",
        "flow_id": (
            f"synthetic-smoke-v1|{pattern}|seed-{seed}|sample-001"
        ),
        "source": "synthetic",
        "event_count": event_count,
        "timestamps": timestamps,
        "timestamp_basis": "synthetic_UTC",
        "relative_times_seconds": relative_times,
        "time_deltas": deltas,
        "bytes_sent": [500] * event_count,
        "bytes_semantics": "synthetic_source_bytes",
    }


def validate(record):
    n = record["event_count"]
    assert len(record["timestamps"]) == n
    assert len(record["relative_times_seconds"]) == n
    assert len(record["time_deltas"]) == n - 1
    assert len(record["bytes_sent"]) == n
    assert record["relative_times_seconds"][0] == 0.0
    assert all(delta > 0 for delta in record["time_deltas"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir", default="data/synthetic/smoke-v1"
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    event_count = 50
    delta_count = event_count - 1

    regular = [60.0] * delta_count

    patterns = {
        "regular": regular,
        "jitter": [
            round(rng.uniform(54.0, 66.0), 6)
            for _ in range(delta_count)
        ],
        "rate_change": [60.0] * 24 + [120.0] * 25,
        "irregular": [
            round(rng.uniform(1.0, 300.0), 6)
            for _ in range(delta_count)
        ],
        "legitimate_periodic": regular.copy(),
    }

    # Mốc giả lập; "+00:00" thể hiện UTC.
    start = datetime.fromisoformat("2026-01-01T00:00:00+00:00")

    records = []
    metadata = []
    reference_stats = []

    for pattern, deltas in patterns.items():
        record = build_record(
            pattern, deltas, start, event_count, args.seed
        )
        validate(record)
        records.append(record)

        # Metadata được lưu riêng, không đưa vào đặc trưng mô hình.
        metadata.append({
            "flow_id": record["flow_id"],
            "pattern": pattern,
            "seed": args.seed,
            "generator_version": "synthetic-smoke-v1",
            "malicious_label": "unknown",
            "context": (
                "legitimate_periodic_scenario"
                if pattern == "legitimate_periodic"
                else "timing_pattern_only"
            ),
        })

        mean_delta = statistics.mean(deltas)

        # Dùng độ lệch chuẩn tổng thể: ddof = 0.
        std_delta = statistics.pstdev(deltas)
        cv = std_delta / mean_delta

        reference_stats.append({
            "flow_id": record["flow_id"],
            "pattern": pattern,
            "event_count": event_count,
            "duration_seconds": sum(deltas),
            "mean_delta_seconds": mean_delta,
            "std_delta_seconds": std_delta,
            "cv": cv,
            "reference_score": 1.0 / (1.0 + cv),
        })

    # JSON: một mảng chứa năm nhóm.
    (out_dir / "groups.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # JSONL: mỗi dòng là một nhóm, cùng nội dung với JSON.
    with (out_dir / "groups.jsonl").open(
        "w", encoding="utf-8"
    ) as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    with (out_dir / "metadata.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(metadata[0])
        )
        writer.writeheader()
        writer.writerows(metadata)

    with (out_dir / "reference_stats.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(reference_stats[0])
        )
        writer.writeheader()
        writer.writerows(reference_stats)

    print(f"Đã tạo {len(records)} nhóm tại: {out_dir.resolve()}")
    print("Mỗi nhóm: 50 sự kiện, 49 khoảng cách.")
    print("reference_stats.csv dùng để đối chiếu baseline hiện có.")


if __name__ == "__main__":
    main()