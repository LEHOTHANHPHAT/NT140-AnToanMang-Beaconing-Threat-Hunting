"""NetSpectra-style feature-wise ensemble."""

import numbers


DEFAULT_CONFIG = {
    "state_model": "ct_hmm",
    "features": ["time_deltas", "bytes_sent"],
    "partial_policy": "strict",
}


def _ensemble_config(config=None):
    if config is None:
        return dict(DEFAULT_CONFIG)
    if not isinstance(config, dict):
        raise ValueError("Ensemble config must be a JSON object.")
    values = config.get("ensemble", config)
    if not isinstance(values, dict):
        raise ValueError("Ensemble config must be a JSON object.")
    merged = dict(DEFAULT_CONFIG)
    merged.update({key: values[key] for key in DEFAULT_CONFIG if key in values})

    if merged["state_model"] not in ("ct_hmm", "hmm"):
        raise ValueError("Ensemble state_model must be 'ct_hmm' or 'hmm'.")
    if merged["partial_policy"] not in ("strict", "fallback"):
        raise ValueError("Ensemble partial_policy must be 'strict' or 'fallback'.")
    if not isinstance(merged["features"], list) or not merged["features"]:
        raise ValueError("Ensemble features must be a nonempty list.")
    if any(not isinstance(feature, str) or not feature for feature in merged["features"]):
        raise ValueError("Ensemble feature names must be nonempty strings.")
    return merged


def _feature_score_mapping(record):
    if isinstance(record, dict) and isinstance(record.get("feature_scores"), dict):
        return record["feature_scores"]
    if isinstance(record, dict):
        return record
    raise ValueError("Model score input must be a dict.")


def combine_scores(hidden_state_scores, tsd_scores, config=None):
    """Combine state-model and TSD scores: max per feature, then mean."""
    settings = _ensemble_config(config)
    state_features = _feature_score_mapping(hidden_state_scores)
    tsd_features = _feature_score_mapping(tsd_scores)

    feature_scores = {}
    partial_notes = []
    partial_used = False
    for feature in settings["features"]:
        state_score = state_features.get(feature)
        tsd_score = tsd_features.get(feature)

        valid = [
            score for score in (state_score, tsd_score)
            if isinstance(score, numbers.Real) and score is not None
        ]
        if state_score is None or tsd_score is None:
            if settings["partial_policy"] == "strict":
                feature_scores[feature] = None
                partial_notes.append(
                    f"{feature}: strict_skip because one branch is skipped"
                )
            elif valid:
                feature_scores[feature] = round(float(max(valid)), 6)
                partial_notes.append(
                    f"{feature}: partial_scored using available branch"
                )
                partial_used = True
            else:
                feature_scores[feature] = None
                partial_notes.append(
                    f"{feature}: skipped because both branches are skipped"
                )
            continue

        feature_scores[feature] = round(float(max(state_score, tsd_score)), 6)

    if any(score is None for score in feature_scores.values()):
        score = None
        status = "skipped"
        if settings["partial_policy"] == "fallback":
            scored_features = [
                value for value in feature_scores.values() if value is not None
            ]
            if scored_features:
                score = round(
                    sum(scored_features) / len(scored_features),
                    6,
                )
                status = "partial_scored"
        skip_reason = "; ".join(partial_notes)
    else:
        score = round(
            sum(feature_scores.values()) / len(settings["features"]),
            6,
        )
        if partial_used:
            status = "partial_scored"
            skip_reason = "; ".join(partial_notes)
        else:
            status = "ok"
            skip_reason = ""

    return {
        "score": score,
        "status": status,
        "skip_reason": skip_reason,
        "feature_scores": feature_scores,
    }


def score_flow(flow, hidden_state_scores, tsd_scores, config=None):
    """Return one ensemble flow record."""
    settings = _ensemble_config(config)
    if not isinstance(flow, dict) or "flow_id" not in flow:
        raise ValueError("Flow is missing flow_id.")

    combined = combine_scores(hidden_state_scores, tsd_scores, settings)
    combined.update({
        "flow_id": flow["flow_id"],
        "method": "netspectra_sentinel_ensemble",
        "event_count": flow.get("event_count"),
        "reason": combined["skip_reason"],
        "metadata": {
            "state_model": settings["state_model"],
            "features": list(settings["features"]),
            "partial_policy": settings["partial_policy"],
        },
    })
    return combined


def score_flows(flows, hidden_state_records, tsd_records, config=None):
    if not isinstance(flows, list):
        raise ValueError("flows must be a list.")
    if len(hidden_state_records) != len(flows) or len(tsd_records) != len(flows):
        raise ValueError("State-model, TSD and flow record counts must match.")
    return [
        score_flow(
            flow,
            hidden_state_records[index],
            tsd_records[index],
            config,
        )
        for index, flow in enumerate(flows)
    ]
