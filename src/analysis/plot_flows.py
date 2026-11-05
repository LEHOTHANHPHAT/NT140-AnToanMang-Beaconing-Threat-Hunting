"""Plot three CTU-13 Scenario 1 groups and export their timing statistics.

Run from the repository root: python -m src.analysis.plot_flows
"""

import csv
import json
import math
from pathlib import Path
from statistics import fmean, median, pstdev

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data/processed/ctu13/scenario-01-tcp"
FIGURE_DIR = ROOT / "outputs/figures/ctu13-scenario01"
STATS_PATH = ROOT / "outputs/ctu13-scenario01-flow-statistics.csv"
TARGETS = (
    ("147.32.84.165", "31.192.109.167", 80, "tcp"),
    ("147.32.84.165", "173.192.170.88", 80, "tcp"),
)
FIELDS = (
    "flow_id", "category", "event_count", "duration_seconds", "min_delta",
    "median_delta", "max_delta", "mean_delta", "population_std_delta",
    "timing_cv", "cc_annotated_rows", "timing_cv_reason",
)


def load_data(data_dir=DATA_DIR):
    flows_data = json.loads((data_dir / "flows.json").read_text(encoding="utf-8"))
    labels_data = json.loads((data_dir / "labels.json").read_text(encoding="utf-8"))
    if flows_data.get("schema_version") != "1.1" or labels_data.get("schema_version") != "1.0":
        raise ValueError("Unexpected CTU-13 flows or labels schema version")
    if flows_data.get("run_id") != labels_data.get("run_id"):
        raise ValueError("flows.json and labels.json have different run_id values")
    flows = flows_data["flows"]
    labels = labels_data["labels"]
    by_id = {label["flow_id"]: label for label in labels}
    if len(by_id) != len(labels) or {flow["flow_id"] for flow in flows} != set(by_id):
        raise ValueError("Flow and label IDs must match uniquely")
    return flows, by_id


def select_flows(flows, labels):
    selected = []
    for target in TARGETS:
        matches = [flow for flow in flows if (
            flow["src_ip"], flow["dst_ip"], flow["dst_port"], flow["protocol"]
        ) == target]
        if len(matches) != 1:
            raise ValueError(f"Expected one group for {target}, found {len(matches)}")
        selected.append(matches[0])
    normals = [flow for flow in flows if flow["protocol"] == "tcp"
               and flow["event_count"] >= 20
               and labels[flow["flow_id"]]["category"] == "normal"]
    if not normals:
        raise ValueError("No normal TCP group with at least 20 records; no substitute selected")
    selected.append(min(normals, key=lambda flow: (abs(flow["event_count"] - 53),
                                                  flow["flow_id"])))
    return selected


def statistics(flow, label):
    count = flow["event_count"]
    deltas = flow["time_deltas"]
    times = flow["relative_times_seconds"]
    byte_counts = flow["bytes_sent"]
    if count < 2 or len(deltas) != count - 1 or len(times) != count or len(byte_counts) != count:
        raise ValueError(f"Inconsistent sequence lengths: {flow['flow_id']}")
    if any(not math.isfinite(value) or value < 0 for value in deltas + times):
        raise ValueError(f"Invalid time values: {flow['flow_id']}")
    mean_delta = fmean(deltas)
    std_delta = pstdev(deltas)
    return {
        "flow_id": flow["flow_id"], "category": label["category"],
        "event_count": count, "duration_seconds": times[-1] - times[0],
        "min_delta": min(deltas), "median_delta": median(deltas),
        "max_delta": max(deltas), "mean_delta": mean_delta,
        "population_std_delta": std_delta,
        "timing_cv": std_delta / mean_delta if mean_delta != 0 else "",
        "cc_annotated_rows": label["cc_annotated_rows"],
        "timing_cv_reason": "" if mean_delta != 0 else "mean_delta_is_zero",
    }


def plot_flow(flow, label, path):
    deltas = flow["time_deltas"]
    times = flow["relative_times_seconds"]
    byte_counts = flow["bytes_sent"]
    figure, (top, bottom) = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
    figure.suptitle(f"{flow['src_ip']} → {flow['dst_ip']}:{flow['dst_port']}/{flow['protocol']}\n"
                    f"{label['category']} | {flow['event_count']} flow records")
    top.plot(range(1, len(deltas) + 1), deltas, marker=".", markersize=3, linewidth=0.8)
    top.set(xlabel="Interval index", ylabel="Time delta (seconds)")
    top.grid(alpha=0.3)
    bottom.plot(times, byte_counts, marker=".", markersize=3, linewidth=0.8)
    bottom.set(xlabel="Relative time (seconds)", ylabel="SrcBytes (bytes)")
    bottom.grid(alpha=0.3)
    # Matplotlib defaults to linear axes and includes the full observed range.
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main():
    flows, labels = load_data()
    selected = select_flows(flows, labels)
    rows = [statistics(flow, labels[flow["flow_id"]]) for flow in selected]
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    for role, flow in zip(("target-01", "target-02", "normal"), selected):
        filename = (f"{role}_{flow['src_ip']}_{flow['dst_ip']}_"
                    f"{flow['dst_port']}_{flow['protocol']}.png")
        path = FIGURE_DIR / filename
        plot_flow(flow, labels[flow["flow_id"]], path)
        print(f"{flow['flow_id']} -> {path.relative_to(ROOT)}")
    with STATS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Statistics -> {STATS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
