import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/synthetic/evaluation-v1"

EVENT_COUNT = 50
PATTERNS = ("regular", "jitter", "random_arrivals", "bursty")
SPLITS = {
    "dev": range(100, 120),
    "test": range(200, 220),
}


def generate_deltas(pattern, rng):
    count = EVENT_COUNT - 1

    if pattern == "regular":
        return [60.0] * count

    if pattern == "jitter":
        return [
            round(rng.uniform(48, 72), 6)
            for _ in range(count)
        ]

    if pattern == "random_arrivals":
        # Phân phối mũ: trung bình lý thuyết 60 giây.
        return [
            max(0.000001, round(rng.expovariate(1 / 60), 6))
            for _ in range(count)
        ]

    if pattern == "bursty":
        # 8 khoảng ngắn rồi một khoảng nghỉ dài.
        deltas = []
        for index in range(count):
            if (index + 1) % 9 == 0:
                delta = rng.uniform(300, 600)
            else:
                delta = rng.uniform(1, 5)
            deltas.append(round(delta, 6))
        return deltas

    raise ValueError(f"Unknown pattern: {pattern}")


def make_flow(split, pattern, seed):
    # Seed dạng chuỗi: tái tạo độc lập từng loại mẫu.
    rng = random.Random(f"evaluation-v1:{pattern}:{seed}")
    deltas = generate_deltas(pattern, rng)

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

    # ID không chứa tên loại mẫu hoặc nhãn.
    pattern_index = PATTERNS.index(pattern)
    flow_id = (
        f"synthetic-eval-v1|{split}|sample-{seed}-{pattern_index}"
    )

    flow = {
        # Giữ cấu trúc của bộ smoke đã chạy được.
        "schema_version": "synthetic-smoke-v1",
        "flow_id": flow_id,
        "source": "synthetic",
        "event_count": EVENT_COUNT,
        "timestamps": timestamps,
        "timestamp_basis": "synthetic_UTC",
        "relative_times_seconds": relative_times,
        "time_deltas": deltas,
        "bytes_sent": [500] * EVENT_COUNT,
        "bytes_semantics": "synthetic_source_bytes",
    }

    label = {
        "flow_id": flow_id,
        "pattern": pattern,
        "periodic_label": int(pattern in {"regular", "jitter"}),
        "seed": seed,
        "split": split,
        "generator_version": "evaluation-v1",
    }

    return flow, label


def main():
    all_ids = set()

    for split, seeds in SPLITS.items():
        directory = OUT_DIR / split
        directory.mkdir(parents=True, exist_ok=True)

        flows = []
        labels = []

        for pattern in PATTERNS:
            for seed in seeds:
                flow, label = make_flow(split, pattern, seed)

                if flow["flow_id"] in all_ids:
                    raise ValueError("Duplicate flow_id")
                all_ids.add(flow["flow_id"])

                if len(flow["time_deltas"]) != EVENT_COUNT - 1:
                    raise ValueError("Wrong delta count")
                if not all(d > 0 for d in flow["time_deltas"]):
                    raise ValueError("Non-positive delta")

                flows.append(flow)
                labels.append(label)

        (directory / "groups.json").write_text(
            json.dumps(flows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with (directory / "labels.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(labels[0])
            )
            writer.writeheader()
            writer.writerows(labels)

        positives = sum(row["periodic_label"] for row in labels)
        print(
            f"{split}: groups={len(flows)}, "
            f"positive={positives}, "
            f"negative={len(flows) - positives}"
        )

    config = {
        "generator_version": "evaluation-v1",
        "event_count": EVENT_COUNT,
        "patterns": {
            "regular": "constant 60 seconds",
            "jitter": "uniform 48 to 72 seconds",
            "random_arrivals": "exponential mean 60 seconds",
            "bursty": "8 short gaps (1-5s), then long gap (300-600s)",
        },
        "dev_seeds": list(SPLITS["dev"]),
        "test_seeds": list(SPLITS["test"]),
        "label_target": "generator-defined periodic timing behavior",
        "bytes_per_event": 500,
    }
    (OUT_DIR / "generation_config.json").write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()