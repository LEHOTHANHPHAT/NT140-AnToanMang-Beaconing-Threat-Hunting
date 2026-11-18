import argparse
import json
import random
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pattern",
        choices=["regular", "jitter", "legitimate_periodic"],
        required=True,
    )
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--period", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.count < 2 or args.period <= 0:
        parser.error("count must be >= 2 and period must be > 0")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    run_id = (
        f"http-lab-{args.pattern}-"
        f"{uuid.uuid4().hex[:12]}"
    )
    rng = random.Random(args.seed)

    intervals = [
        args.period * (
            rng.uniform(0.8, 1.2)
            if args.pattern == "jitter"
            else 1.0
        )
        for _ in range(args.count - 1)
    ]

    metadata = {
        "run_id": run_id,
        "pattern": args.pattern,
        "count": args.count,
        "period_seconds": args.period,
        "seed": args.seed,
        "planned_intervals_seconds": intervals,
        "purpose": (
            "legitimate service health check"
            if args.pattern == "legitimate_periodic"
            else "controlled timing experiment"
        ),
        "malicious": False,
    }
    (args.out_dir / f"{run_id}-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    # Cùng body và endpoint để tập trung vào thời gian.
    body = b'{"message":"lab-check"}'
    url = "http://127.0.0.1:8088/check"
    log_path = args.out_dir / f"{run_id}-client.jsonl"

    deadline = time.monotonic()
    failures = 0

    with log_path.open("w", encoding="utf-8") as handle:
        for index in range(args.count):
            if index > 0:
                deadline += intervals[index - 1]

            time.sleep(max(0.0, deadline - time.monotonic()))

            started_ns = time.monotonic_ns()
            started_at = datetime.now(timezone.utc).isoformat()

            request = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Lab-Run-ID": run_id,
                    "X-Lab-Sequence": str(index),
                },
                method="POST",
            )

            status = None
            error = ""
            try:
                with urllib.request.urlopen(
                    request, timeout=5
                ) as response:
                    status = response.status
                    response.read()
            except (urllib.error.URLError, TimeoutError) as exc:
                failures += 1
                error = str(exc)

            elapsed = (
                time.monotonic_ns() - started_ns
            ) / 1_000_000_000

            handle.write(json.dumps({
                "run_id": run_id,
                "sequence": index,
                "started_at": started_at,
                "started_monotonic_ns": started_ns,
                "http_status": status,
                "elapsed_seconds": elapsed,
                "error": error,
            }) + "\n")
            handle.flush()

            print(
                f"{index + 1}/{args.count}: "
                f"status={status}, elapsed={elapsed:.4f}s"
            )

    print(f"Run ID: {run_id}")
    print(f"Failures: {failures}")
    print(f"Client log: {log_path}")


if __name__ == "__main__":
    main()