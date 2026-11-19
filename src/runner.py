"""Commands for preprocessing, baseline and detection model runs."""

import argparse
import json
import sys
from pathlib import Path

from src.baselines.statistical import score_flows
from src.data.prepare import prepare_csv, save_json
from src.models.ct_hmm import score_flows as score_ct_hmm
from src.models.hmm import score_flows as score_hmm
from src.models.tsd import score_flows as score_tsd
from src.models.ensemble import score_flows as score_ensemble

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
    if "model_scores_dir" in config:
        value = Path(config["model_scores_dir"])
        config["model_scores_dir"] = (
            value if value.is_absolute() else PROJECT_ROOT / value
        )
    minimum = config["baseline"]["min_events"]
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 2:
        raise ValueError("baseline.min_events must be an integer >= 2.")
    return config


def _model_output_path(model_name, config=None):
    output_dir = (
        config.get("model_scores_dir", PROJECT_ROOT / "outputs" / "scores")
        if config is not None
        else PROJECT_ROOT / "outputs" / "scores"
    )
    return Path(output_dir) / f"{model_name}.json"


def _ascii_path(path):
    return str(path).encode("ascii", "backslashreplace").decode("ascii")


def _model_scores(payload, model_name, config):
    flows = payload["flows"]
    if model_name == "hmm":
        return score_hmm(flows, config)
    if model_name == "ct_hmm":
        return score_ct_hmm(flows, config)
    if model_name == "tsd":
        return score_tsd(flows, config)
    if model_name == "ensemble":
        ensemble_config = config.get("ensemble", {})
        state_model = ensemble_config.get("state_model", "ct_hmm")
        if state_model == "hmm":
            hidden_records = score_hmm(flows, config)
        else:
            hidden_records = score_ct_hmm(flows, config)
        tsd_records = score_tsd(flows, config)
        return score_ensemble(
            flows,
            hidden_records,
            tsd_records,
            config,
        )
    raise ValueError("Unknown model name.")


def _print_model_stats(model_name, records, output_path):
    scored = sum(record["status"] in ("ok", "partial_scored") for record in records)
    skipped = sum(record["status"] == "skipped" for record in records)
    errors = sum(record["status"] == "error" for record in records)
    print(
        f"{model_name}: {scored} scored / {skipped} skipped / {errors} error."
    )
    print(f"Scores: {_ascii_path(output_path)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    baseline_parser = subparsers.add_parser("baseline")
    demo_parser = subparsers.add_parser("demo")

    model_parser = subparsers.add_parser("model")
    model_parser.add_argument(
        "--name",
        choices=("hmm", "ct_hmm", "tsd", "ensemble"),
        required=True,
    )

    parser.add_argument("--config", default="configs/default.json")
    for subparser in (prepare_parser, baseline_parser, demo_parser, model_parser):
        subparser.add_argument("--config", default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command in ("prepare", "demo"):
            payload = prepare_csv(config["input_csv"], config["dataset_id"])
            save_json(payload, config["processed_json"])
            quality = payload["quality"]
            print(f"Prepared {quality['event_count']} events / {quality['flow_count']} groups.")
            print(f"Flows: {_ascii_path(config['processed_json'])}")
        else:
            payload = json.loads(config["processed_json"].read_text(encoding="utf-8"))
        if args.command in ("baseline", "demo"):
            if payload.get("schema_version") != "1.0":
                raise ValueError("Expected processed data schema_version 1.0.")
            records = score_flows(payload["flows"], config["baseline"]["min_events"])
            save_json({"schema_version": "1.0", "scores": records}, config["scores_json"])
            ok = sum(record["status"] == "ok" for record in records)
            print(f"Baseline: {ok} scored / {len(records) - ok} skipped.")
            print(f"Scores: {_ascii_path(config['scores_json'])}")
        elif args.command == "model":
            if payload.get("schema_version") != "1.0":
                raise ValueError("Expected processed data schema_version 1.0.")
            records = _model_scores(payload, args.name, config)
            output_path = _model_output_path(args.name, config)
            save_json({"schema_version": "1.0", "scores": records}, output_path)
            _print_model_stats(args.name, records, output_path)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
