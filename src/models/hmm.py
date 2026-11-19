"""Discrete-step Gaussian HMM, feature-wise and separate from CT-HMM."""

import math
import numbers
from collections import Counter

import numpy as np
from hmmlearn.hmm import GaussianHMM


DEFAULT_CONFIG = {
    "min_events": 5,
    "n_states": 2,
    "n_iter": 100,
    "random_seed": 42,
    "n_init": 3,
}


def _hmm_config(config=None):
    if isinstance(config, int) and not isinstance(config, bool):
        return dict(DEFAULT_CONFIG, min_events=config)
    if config is None:
        return dict(DEFAULT_CONFIG)
    if not isinstance(config, dict):
        raise ValueError("HMM config must be a JSON object.")

    nested = config.get("hmm")
    values = nested if isinstance(nested, dict) else config
    merged = dict(DEFAULT_CONFIG)
    merged.update({key: values[key] for key in DEFAULT_CONFIG if key in values})

    for key in ("min_events", "n_states", "n_iter", "n_init", "random_seed"):
        if isinstance(merged[key], bool) or not isinstance(merged[key], int):
            raise ValueError(f"HMM {key} must be an integer.")
    if merged["min_events"] < 2:
        raise ValueError("HMM min_events must be an integer >= 2.")
    if merged["n_states"] < 1:
        raise ValueError("HMM n_states must be an integer >= 1.")
    if merged["n_iter"] < 1:
        raise ValueError("HMM n_iter must be an integer >= 1.")
    if merged["n_init"] < 1:
        raise ValueError("HMM n_init must be an integer >= 1.")
    return merged


def score_decoded_sequence(hidden_states, d=None):
    """Return n_b / d for a state-decoded sequence.

    The result is invariant to renaming or permuting integer state labels.
    """
    states = np.asarray(hidden_states)
    if states.ndim != 1 or states.size == 0:
        raise ValueError("hidden_states must be a nonempty 1-D sequence.")
    observation_count = states.size if d is None else d
    if isinstance(observation_count, bool) or not isinstance(observation_count, (int, np.integer)):
        raise ValueError("d must be an integer.")
    if observation_count <= 0 or states.size > observation_count:
        raise ValueError("d must cover at least the decoded observations.")
    dominant_count = max(Counter(states.tolist()).values())
    return round(dominant_count / observation_count, 6)


def _valid_vector(flow, feature_name):
    value = flow.get(feature_name)
    if not isinstance(value, list):
        return None, f"{feature_name}_missing"
    if any(isinstance(x, bool) or not isinstance(x, numbers.Real)
           or not math.isfinite(float(x)) for x in value):
        return None, f"{feature_name}_invalid_values"
    return np.asarray(value, dtype=float), ""


def _fit_feature(values, config, d, feature_name):
    min_observations = config["min_events"] - (
        1 if feature_name == "time_deltas" else 0
    )
    if d < min_observations:
        return None, f"fewer_than_{min_observations}_observations", None
    if d < config["n_states"]:
        return None, f"not_enough_observations_for_{config['n_states']}_states", None
    if not np.isfinite(values).all():
        return None, "nonfinite_feature_values", None
    if float(np.var(values)) <= np.finfo(float).eps:
        return None, "zero_variance", None

    observations = values.reshape(-1, 1)
    best_model = None
    best_score = -np.inf
    best_seed = config["random_seed"]

    for init_index in range(config["n_init"]):
        seed = config["random_seed"] + init_index
        model = GaussianHMM(
            n_components=config["n_states"],
            covariance_type="diag",
            n_iter=config["n_iter"],
            random_state=seed,
        )
        try:
            model.fit(observations)
            likelihood = float(model.score(observations))
        except (ValueError, np.linalg.LinAlgError):
            continue
        if likelihood > best_score:
            best_model = model
            best_score = likelihood
            best_seed = seed

    if best_model is None:
        return None, "hmm_fit_failed", None
    try:
        hidden_states = best_model.predict(observations)
    except (ValueError, np.linalg.LinAlgError):
        return None, "hmm_decode_failed", None
    score = round(
        int(np.bincount(hidden_states).max()) / d,
        6,
    )
    return score, "", {"model": best_model, "seed": best_seed}


def score_flow(flow, config=None):
    """Score one flow using time_deltas and bytes_sent independently."""
    if not isinstance(flow, dict):
        raise ValueError("Each flow must be a JSON object.")
    if "flow_id" not in flow:
        raise ValueError("Flow is missing flow_id.")
    settings = _hmm_config(config)

    feature_scores = {}
    feature_details = {}
    skipped_reasons = []
    fitted = []

    for feature_name in ("time_deltas", "bytes_sent"):
        values, missing_reason = _valid_vector(flow, feature_name)
        if values is None:
            feature_scores[feature_name] = None
            feature_details[feature_name] = {
                "d": 0,
                "status": "skipped",
                "skip_reason": missing_reason,
            }
            skipped_reasons.append(f"{feature_name}: {missing_reason}")
            continue

        d = len(values)
        score, skip_reason, fit = _fit_feature(
            values,
            settings,
            d,
            feature_name,
        )
        feature_scores[feature_name] = score
        feature_details[feature_name] = {
            "d": d,
            "status": "ok" if score is not None else "skipped",
            "skip_reason": skip_reason,
        }
        if skip_reason:
            skipped_reasons.append(f"{feature_name}: {skip_reason}")
        if fit is not None:
            fitted.append(fit)

    valid_scores = [score for score in feature_scores.values() if score is not None]
    if valid_scores:
        status = "ok"
        top_score = round(float(sum(valid_scores) / len(valid_scores)), 6)
    else:
        status = "skipped"
        top_score = None

    skip_reason = "; ".join(skipped_reasons)
    converged = bool(fitted) and all(
        getattr(getattr(item["model"], "monitor_", None), "converged", False)
        for item in fitted
    )
    seed = fitted[0]["seed"] if fitted else settings["random_seed"]

    return {
        "flow_id": flow["flow_id"],
        "method": "discrete_step_gaussian_hmm",
        "event_count": flow.get("event_count"),
        "score": top_score,
        "status": status,
        "skip_reason": skip_reason,
        "reason": skip_reason,
        "feature_scores": feature_scores,
        "feature_details": feature_details,
        "metadata": {
            "n_states": settings["n_states"],
            "n_iter": settings["n_iter"],
            "n_init": settings["n_init"],
            "configured_seed": settings["random_seed"],
            "seed": seed,
            "converged": converged,
        },
    }


def score_flows(flows, config=None):
    """Score a processed flows list or a processed JSON payload."""
    if isinstance(flows, dict):
        if "flows" not in flows:
            raise ValueError("Processed JSON payload is missing flows.")
        flows = flows["flows"]
    if not isinstance(flows, list):
        raise ValueError("flows must be a list.")
    return [score_flow(flow, config=config) for flow in flows]
