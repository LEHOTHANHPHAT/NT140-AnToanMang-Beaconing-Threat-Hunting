"""Timing regularity reference score. This is not RITA or NetSpectra Sentinel."""

import math
from statistics import fmean, pstdev


def score_flow(flow, min_events=5):
    """Score timing regularity as 1 / (1 + population_std / mean).

    No decision threshold or malicious/benign prediction is produced.
    """
    if isinstance(min_events, bool) or not isinstance(min_events, int) or min_events < 2:
        raise ValueError("min_events must be an integer >= 2.")
    count = flow["event_count"]
    deltas = flow["time_deltas"]
    if count < 1 or len(deltas) != count - 1:
        raise ValueError("Expected event_count - 1 time deltas.")
    if any(isinstance(x, bool) or not isinstance(x, (int, float))
           or not math.isfinite(x) or x < 0 for x in deltas):
        raise ValueError("Time deltas must be finite nonnegative numbers.")
    result = {
        "flow_id": flow["flow_id"], "method": "timing_cv_baseline",
        "event_count": count, "score": None, "status": "skipped", "reason": "",
    }
    if count < min_events:
        result["reason"] = f"fewer_than_{min_events}_events"
        return result
    mean = fmean(deltas)
    if mean <= 0:
        result["reason"] = "zero_mean_interval"
        return result
    result.update(score=round(1 / (1 + pstdev(deltas) / mean), 6), status="ok")
    return result


def score_flows(flows, min_events=5):
    return [score_flow(flow, min_events) for flow in flows]
