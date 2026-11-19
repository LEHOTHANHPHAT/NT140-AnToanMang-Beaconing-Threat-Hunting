"""Time-series decomposition detector using additive seasonal decomposition."""

import math
import numbers
from datetime import datetime, timezone

import numpy as np
from statsmodels.tsa.seasonal import seasonal_decompose


DEFAULT_CONFIG = {
    "min_events": 5,
    "mode": "event",
    "period": 6,
    "bin_size_seconds": 10,
    "clock_period_seconds": 60,
    "clock_aggregation": "sum",
    "z_threshold": 3.0,
}


def _tsd_config(config=None):
    if isinstance(config, int) and not isinstance(config, bool):
        return dict(DEFAULT_CONFIG, min_events=config)
    if config is None:
        return dict(DEFAULT_CONFIG)
    if not isinstance(config, dict):
        raise ValueError("TSD config must be a JSON object.")

    values = config.get("tsd", config)
    if not isinstance(values, dict):
        raise ValueError("TSD config must be a JSON object.")
    merged = dict(DEFAULT_CONFIG)
    merged.update({key: values[key] for key in DEFAULT_CONFIG if key in values})

    mode = values.get("axis_mode", values.get("mode", merged["mode"]))
    if mode not in ("event", "clock"):
        raise ValueError("TSD mode must be 'event' or 'clock'.")
    merged["mode"] = mode

    for key in ("min_events", "period", "bin_size_seconds", "clock_period_seconds"):
        if key in values and (isinstance(values[key], bool) or not isinstance(values[key], int)):
            raise ValueError(f"TSD {key} must be an integer.")
    if isinstance(merged["z_threshold"], bool) or not isinstance(merged["z_threshold"], numbers.Real):
        raise ValueError("TSD z_threshold must be numeric.")
    if merged["z_threshold"] <= 0:
        raise ValueError("TSD z_threshold must be positive.")
    if merged["min_events"] < 2:
        raise ValueError("TSD min_events must be an integer >= 2.")
    if merged["bin_size_seconds"] <= 0:
        raise ValueError("TSD bin_size_seconds must be positive.")
    if merged["clock_period_seconds"] <= 0:
        raise ValueError("TSD clock_period_seconds must be positive.")
    if merged["clock_aggregation"] not in ("count", "sum"):
        raise ValueError("TSD clock_aggregation must be 'count' or 'sum'.")
    return merged


def _parse_timestamp(value):
    if not isinstance(value, str):
        return None
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clock_series(flow, feature_name, settings):
    timestamps = flow.get("timestamps")
    if not isinstance(timestamps, list) or not timestamps:
        return None, "timestamps_missing"
    try:
        stamps = [_parse_timestamp(value) for value in timestamps]
    except (TypeError, ValueError):
        return None, "timestamps_invalid"
    if any(stamp is None for stamp in stamps):
        return None, "timestamps_invalid"

    start = min(stamps)
    bin_seconds = settings["bin_size_seconds"]
    duration = max((stamp - start).total_seconds() for stamp in stamps)
    bin_count = int(math.floor(duration / bin_seconds)) + 1
    series = np.zeros(bin_count, dtype=float)

    if feature_name == "bytes_sent":
        values = flow.get("bytes_sent")
        if not isinstance(values, list) or len(values) != len(stamps):
            return None, "bytes_sent_clock_length_mismatch"
        if any(isinstance(x, bool) or not isinstance(x, numbers.Real)
               or not math.isfinite(float(x)) or float(x) < 0 for x in values):
            return None, "bytes_sent_invalid_values"
        for stamp, value in zip(stamps, values):
            index = int(math.floor((stamp - start).total_seconds() / bin_seconds))
            if settings["clock_aggregation"] == "sum":
                series[index] += float(value)
            else:
                series[index] += 1.0
    else:
        deltas = flow.get("time_deltas")
        if not isinstance(deltas, list):
            return None, "time_deltas_missing"
        if len(deltas) != len(stamps) - 1:
            return None, "time_deltas_clock_length_mismatch"
        if any(isinstance(x, bool) or not isinstance(x, numbers.Real)
               or not math.isfinite(float(x)) or float(x) < 0 for x in deltas):
            return None, "time_deltas_invalid_values"
        for stamp, value in zip(stamps[1:], deltas):
            index = int(math.floor((stamp - start).total_seconds() / bin_seconds))
            series[index] += float(value)

    return series, ""


def _decompose(values, period):
    result = seasonal_decompose(
        np.asarray(values, dtype=float),
        model="additive",
        period=period,
        extrapolate_trend=0,
    )
    residual = np.asarray(result.resid, dtype=float)
    valid = residual[~np.isnan(residual)]
    return valid


def score_residual(residual, z_threshold=3.0):
    residual = np.asarray(residual, dtype=float)
    residual = residual[np.isfinite(residual)]
    d = residual.size
    if d == 0:
        return None, 0, "insufficient_valid_residual"

    mu_r = float(np.mean(residual))
    sigma_r = float(np.std(residual))
    if sigma_r < 1e-12:
        return 1.0, d, ""

    z_scores = (residual - mu_r) / sigma_r
    n_a = int(np.count_nonzero(np.abs(z_scores) > z_threshold))
    score = round((d - n_a) / d, 6)
    return score, d, ""


def score_flow(flow, config=None):
    if not isinstance(flow, dict):
        raise ValueError("Each flow must be a JSON object.")
    if "flow_id" not in flow:
        raise ValueError("Flow is missing flow_id.")

    settings = _tsd_config(config)
    period = settings["period"]
    if settings["mode"] == "clock":
        period = max(
            1,
            int(round(settings["clock_period_seconds"] / settings["bin_size_seconds"])),
        )

    feature_scores = {}
    feature_details = {}
    skip_reasons = []

    for feature_name in ("time_deltas", "bytes_sent"):
        if settings["mode"] == "clock":
            values, reason = _clock_series(flow, feature_name, settings)
        else:
            values = flow.get(feature_name)
            reason = ""
            if not isinstance(values, list):
                reason = f"{feature_name}_missing"
            elif any(isinstance(x, bool) or not isinstance(x, numbers.Real)
                     or not math.isfinite(float(x)) or float(x) < 0 for x in values):
                reason = f"{feature_name}_invalid_values"
            else:
                values = np.asarray(values, dtype=float)

        d = 0
        if reason:
            score = None
            skip_reason = reason
        elif values is None:
            score = None
            skip_reason = f"{feature_name}_missing"
        else:
            values = np.asarray(values, dtype=float)
            d = len(values)
            if d < 2 * period:
                score = None
                skip_reason = "insufficient_cycles"
            else:
                try:
                    residual = _decompose(values, period)
                    decompose_reason = ""
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    residual = np.asarray([], dtype=float)
                    decompose_reason = "seasonal_decompose_failed"
                if residual.size == 0:
                    score = None
                    skip_reason = decompose_reason or "insufficient_valid_residual"
                else:
                    score, d, skip_reason = score_residual(
                        residual, settings["z_threshold"]
                    )

        feature_scores[feature_name] = score
        feature_details[feature_name] = {
            "d": d,
            "status": "ok" if score is not None else "skipped",
            "skip_reason": skip_reason,
        }
        if skip_reason:
            skip_reasons.append(f"{feature_name}: {skip_reason}")

    valid_scores = [score for score in feature_scores.values() if score is not None]
    if valid_scores:
        overall_score = round(float(sum(valid_scores) / len(valid_scores)), 6)
        status = "ok"
    else:
        overall_score = None
        status = "skipped"

    skip_reason = "; ".join(skip_reasons)
    return {
        "flow_id": flow["flow_id"],
        "method": "time_series_decomposition",
        "event_count": flow.get("event_count"),
        "score": overall_score,
        "status": status,
        "skip_reason": skip_reason,
        "reason": skip_reason,
        "feature_scores": feature_scores,
        "feature_details": feature_details,
        "metadata": {
            "mode": settings["mode"],
            "period": period,
            "bin_size_seconds": settings["bin_size_seconds"],
            "clock_aggregation": settings["clock_aggregation"],
            "z_threshold": settings["z_threshold"],
        },
    }


def score_flows(flows, config=None):
    if isinstance(flows, dict):
        if "flows" not in flows:
            raise ValueError("Processed JSON payload is missing flows.")
        flows = flows["flows"]
    if not isinstance(flows, list):
        raise ValueError("flows must be a list.")
    return [score_flow(flow, config=config) for flow in flows]
