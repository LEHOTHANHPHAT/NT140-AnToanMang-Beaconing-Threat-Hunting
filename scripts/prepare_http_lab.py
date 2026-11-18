import argparse
import json
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    server_path = args.session_dir / "server.jsonl"
    grouped = defaultdict(list)

    with server_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if not row["run_id"]:
                    raise ValueError("Server record has no run_id")
                grouped[row["run_id"]].append(row)

    metadata = {}
    for path in args.session_dir.glob("*-metadata.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        if row["run_id"] in metadata:
            raise ValueError("Duplicate metadata run_id")
        metadata[row["run_id"]] = row

    if not grouped:
        raise ValueError("No server requests found")

    if set(grouped) != set(metadata):
        raise ValueError(
            "Server run IDs and metadata run IDs do not match"
        )

    flows = []
    contexts = []

    for run_id, rows in sorted(grouped.items()):
        meta = metadata[run_id]
        expected_count = int(meta["count"])

        # Đối chiếu log client: không âm thầm bỏ request thất bại.
        client_path = args.session_dir / f"{run_id}-client.jsonl"
        with client_path.open(encoding="utf-8") as handle:
            client_rows = [
                json.loads(line)
                for line in handle
                if line.strip()
            ]

        if len(client_rows) != expected_count:
            raise ValueError(f"{run_id}: wrong client count")

        if any(
            row["run_id"] != run_id
            or row["http_status"] != 200
            or row["error"]
            for row in client_rows
        ):
            raise ValueError(f"{run_id}: invalid/failed client request")

        client_sequences = [int(row["sequence"]) for row in client_rows]
        if sorted(client_sequences) != list(range(expected_count)):
            raise ValueError(f"{run_id}: invalid client sequences")

        if len(rows) != expected_count:
            raise ValueError(f"{run_id}: wrong server count")

        sequences = [int(row["sequence"]) for row in rows]
        if sorted(sequences) != list(range(expected_count)):
            raise ValueError(f"{run_id}: missing/duplicate server sequence")

        # Sắp theo thời điểm nhận thực tế.
        rows.sort(key=lambda row: int(row["received_monotonic_ns"]))

        if [int(row["sequence"]) for row in rows] != list(
            range(expected_count)
        ):
            raise ValueError(f"{run_id}: unexpected receive order")

        ticks = [int(row["received_monotonic_ns"]) for row in rows]
        deltas = [
            (right - left) / 1_000_000_000
            for left, right in zip(ticks, ticks[1:])
        ]

        if not deltas or any(delta <= 0 for delta in deltas):
            raise ValueError(f"{run_id}: invalid time deltas")

        relative = [
            (tick - ticks[0]) / 1_000_000_000
            for tick in ticks
        ]

        flow_id = f"http-lab-v1|{args.session_dir.name}|{run_id}"

        flows.append({
            # Tương thích cấu trúc nhóm đã dùng trong smoke test.
            # Cần chuẩn hóa cùng data-contract khi tích hợp mô hình.
            "schema_version": "synthetic-smoke-v1",
            "flow_id": flow_id,
            "source": "controlled_http_lab",
            "event_count": len(rows),
            "timestamps": [row["received_at"] for row in rows],
            "timestamp_basis": (
                "server_UTC_timestamps;"
                "deltas_from_server_monotonic_clock"
            ),
            "relative_times_seconds": relative,
            "time_deltas": deltas,
            "bytes_sent": [
                int(row["request_body_bytes"]) for row in rows
            ],
            "bytes_semantics": "http_request_body_bytes",
        })

        # Ngữ cảnh và cấu hình nằm riêng, không dùng để chấm điểm.
        contexts.append({
            "flow_id": flow_id,
            "run_id": run_id,
            "pattern": meta["pattern"],
            "purpose": meta["purpose"],
            "malicious": meta["malicious"],
            "expected_count": expected_count,
            "period_seconds": meta["period_seconds"],
            "planned_intervals_seconds": (
                meta["planned_intervals_seconds"]
            ),
        })

    args.out_dir.mkdir(parents=True, exist_ok=True)

    (args.out_dir / "groups.json").write_text(
        json.dumps(flows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "contexts.json").write_text(
        json.dumps(contexts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    for flow in flows:
        print(
            f"{flow['flow_id']}: "
            f"events={flow['event_count']}, "
            f"deltas={len(flow['time_deltas'])}"
        )

    print(f"Output: {args.out_dir}")


if __name__ == "__main__":
    main()