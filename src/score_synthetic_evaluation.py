import argparse
import csv
import json
import math
from pathlib import Path

from src.baselines.statistical import score_flow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    flows = json.loads(args.input.read_text(encoding="utf-8"))
    rows = []
    seen = set()

    for flow in flows:
        flow_id = flow["flow_id"]
        if flow_id in seen:
            raise ValueError(f"Duplicate flow_id: {flow_id}")
        seen.add(flow_id)

        try:
            result = score_flow(flow, 5)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            result = {
                "flow_id": flow_id,
                "score": None,
                "status": "error",
                "reason": f"{type(error).__name__}: {error}",
            }

        if result["flow_id"] != flow_id:
            raise ValueError("Output flow_id mismatch")

        status = result["status"]
        score = result["score"]

        if status not in {"ok", "skipped", "error"}:
            raise ValueError("Unexpected status")

        if status == "ok":
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
            ):
                raise ValueError("Invalid score")
        elif score is not None or not result.get("reason"):
            raise ValueError("Invalid skipped/error output")

        rows.append({
            "flow_id": flow_id,
            "score": score,
            "status": status,
            "reason": result.get("reason", ""),
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["flow_id", "score", "status", "reason"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Groups: {len(rows)}")
    print(f"ok: {sum(r['status'] == 'ok' for r in rows)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()