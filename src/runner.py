"""Commands for the runnable preprocessing and statistical baseline scaffold."""

import argparse
import json
import sys
from pathlib import Path

from src.baselines.statistical import score_flows
from src.data.prepare import prepare_csv, save_json

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_config(path):
    path = Path(path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    config = json.loads(path.read_text(encoding="utf-8"))
    # All paths, including custom config paths, are relative to the repo root.
    for name in ("input_csv", "processed_json", "scores_json"):
        value = Path(config[name])
        config[name] = value if value.is_absolute() else PROJECT_ROOT / value
    minimum = config["baseline"]["min_events"]
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 2:
        raise ValueError("baseline.min_events must be an integer >= 2.")
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "baseline", "demo"))
    parser.add_argument("--config", default="configs/default.json")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command in ("prepare", "demo"):
            payload = prepare_csv(config["input_csv"], config["dataset_id"])
            save_json(payload, config["processed_json"])
            quality = payload["quality"]
            print(f"Prepared {quality['event_count']} events / {quality['flow_count']} groups.")
            print(f"Flows: {config['processed_json']}")
        else:
            payload = json.loads(config["processed_json"].read_text(encoding="utf-8"))
        if args.command in ("baseline", "demo"):
            if payload.get("schema_version") != "1.0":
                raise ValueError("Expected processed data schema_version 1.0.")
            records = score_flows(payload["flows"], config["baseline"]["min_events"])
            save_json({"schema_version": "1.0", "scores": records}, config["scores_json"])
            ok = sum(record["status"] == "ok" for record in records)
            print(f"Baseline: {ok} scored / {len(records) - ok} skipped.")
            print(f"Scores: {config['scores_json']}")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
