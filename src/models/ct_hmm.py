"""Continuous-time Hidden Markov Model with Gaussian emissions.

This module is intentionally separate from the discrete-step HMM. Hidden-state
transitions are functions of elapsed time through a CTMC and scipy.linalg.expm.
"""

import math
import numbers
from collections import Counter

import numpy as np
from scipy.linalg import expm
from scipy.special import logsumexp


DEFAULT_CONFIG = {
    "min_events": 5,
    "n_states": 2,
    "n_iter": 100,
    "random_seed": 42,
    "n_init": 3,
    "tolerance": 1e-5,
}


def _cthmm_config(config=None):
    if isinstance(config, int) and not isinstance(config, bool):
        return dict(DEFAULT_CONFIG, min_events=config)
    if config is None:
        return dict(DEFAULT_CONFIG)
    if not isinstance(config, dict):
        raise ValueError("CT-HMM config must be a JSON object.")

    values = config.get("ct_hmm", config)
    if not isinstance(values, dict):
        raise ValueError("CT-HMM config must be a JSON object.")
    merged = dict(DEFAULT_CONFIG)
    merged.update({key: values[key] for key in DEFAULT_CONFIG if key in values})

    for key in ("min_events", "n_states", "n_iter", "n_init", "random_seed"):
        if isinstance(merged[key], bool) or not isinstance(merged[key], int):
            raise ValueError(f"CT-HMM {key} must be an integer.")
    if isinstance(merged["tolerance"], bool) or not isinstance(
        merged["tolerance"], numbers.Real
    ):
        raise ValueError("CT-HMM tolerance must be numeric.")
    if merged["min_events"] < 2:
        raise ValueError("CT-HMM min_events must be an integer >= 2.")
    if merged["n_states"] < 1:
        raise ValueError("CT-HMM n_states must be an integer >= 1.")
    if merged["n_iter"] < 1 or merged["n_init"] < 1:
        raise ValueError("CT-HMM n_iter and n_init must be integers >= 1.")
    if merged["tolerance"] <= 0:
        raise ValueError("CT-HMM tolerance must be positive.")
    return merged


def ctmc_transition_matrix(Q, elapsed_time):
    """Compute P(Delta_t) = expm(Q * Delta_t) for one CTMC interval."""
    Q = np.asarray(Q, dtype=float)
    if elapsed_time is None or isinstance(elapsed_time, bool):
        raise ValueError("elapsed_time must be a finite nonnegative number.")
    elapsed_time = float(elapsed_time)
    if not math.isfinite(elapsed_time) or elapsed_time < 0:
        raise ValueError("elapsed_time must be a finite nonnegative number.")
    if Q.ndim != 2 or Q.shape[0] != Q.shape[1]:
        raise ValueError("Q must be a square matrix.")

    if elapsed_time == 0:
        P = np.eye(Q.shape[0], dtype=float)
    else:
        P = expm(Q * elapsed_time)

    P = np.maximum(P, 0.0)
    P = P / np.maximum(P.sum(axis=1, keepdims=True), np.finfo(float).eps)
    return P


expm_transition_matrix = ctmc_transition_matrix


def score_decoded_sequence(hidden_states, d=None):
    states = np.asarray(hidden_states)
    if states.ndim != 1 or states.size == 0:
        raise ValueError("hidden_states must be a nonempty 1-D sequence.")
    d = states.size if d is None else d
    if isinstance(d, bool) or not isinstance(d, (int, np.integer)):
        raise ValueError("d must be an integer.")
    if d <= 0 or states.size > d:
        raise ValueError("d must cover at least the decoded observations.")
    return round(max(Counter(states.tolist()).values()) / d, 6)


def _initial_q(n_states, elapsed_times, random_seed):
    positive_times = elapsed_times[elapsed_times > 0]
    mean_dt = float(np.mean(positive_times)) if positive_times.size else 1.0

    rng = np.random.default_rng(random_seed)
    scale = rng.uniform(0.5, 1.5) / max(mean_dt, 1e-12)

    Q = np.zeros((n_states, n_states), dtype=float)
    if n_states > 1:
        for i in range(n_states):
            for j in range(n_states):
                if i != j:
                    Q[i, j] = scale / (n_states - 1)
        np.fill_diagonal(Q, -Q.sum(axis=1))
    return Q


def _emission_log_probabilities(observations, means, variances):
    differences = observations[:, None] - means[None, :]
    return -0.5 * (
        np.log(2.0 * np.pi * variances)[None, :]
        + differences * differences / variances[None, :]
    )


def _forward_backward(log_emissions, transition_matrices, pi):
    d, n_states = log_emissions.shape
    alpha = np.full((d, n_states), -np.inf)
    beta = np.full((d, n_states), -np.inf)

    alpha[0] = np.log(np.maximum(pi, np.finfo(float).tiny)) + log_emissions[0]
    for k in range(1, d):
        log_P = np.log(
            np.maximum(transition_matrices[k - 1], np.finfo(float).tiny)
        )
        alpha[k] = log_emissions[k] + logsumexp(
            alpha[k - 1][:, None] + log_P,
            axis=0,
        )

    beta[-1] = 0.0
    for k in range(d - 2, -1, -1):
        log_P = np.log(
            np.maximum(transition_matrices[k], np.finfo(float).tiny)
        )
        beta[k] = logsumexp(
            log_P + log_emissions[k + 1][None, :] + beta[k + 1][None, :],
            axis=1,
        )

    log_likelihood = logsumexp(alpha[-1])
    if not np.isfinite(log_likelihood):
        raise FloatingPointError("nonfinite forward-backward likelihood")

    gamma = np.exp(alpha + beta - log_likelihood)
    gamma /= np.maximum(
        gamma.sum(axis=1, keepdims=True),
        np.finfo(float).eps,
    )

    xi_sum = np.zeros((n_states, n_states), dtype=float)
    for k in range(d - 1):
        log_P = np.log(
            np.maximum(transition_matrices[k], np.finfo(float).tiny)
        )
        log_xi = (
            alpha[k][:, None]
            + log_P
            + log_emissions[k + 1][None, :]
            + beta[k + 1][None, :]
        )
        xi_sum += np.exp(log_xi - logsumexp(log_xi))

    return gamma, xi_sum, float(log_likelihood)


def _viterbi(log_emissions, transition_matrices, pi):
    d, n_states = log_emissions.shape
    delta = np.full((d, n_states), -np.inf)
    psi = np.zeros((d, n_states), dtype=np.int64)

    delta[0] = np.log(np.maximum(pi, np.finfo(float).tiny)) + log_emissions[0]
    for k in range(1, d):
        log_P = np.log(
            np.maximum(transition_matrices[k - 1], np.finfo(float).tiny)
        )
        candidates = delta[k - 1][:, None] + log_P
        psi[k] = np.argmax(candidates, axis=0)
        delta[k] = candidates[psi[k], np.arange(n_states)] + log_emissions[k]

    states = np.empty(d, dtype=np.int64)
    states[-1] = np.argmax(delta[-1])
    for k in range(d - 2, -1, -1):
        states[k] = psi[k + 1, states[k + 1]]
    return states


def _valid_vector(flow, feature_name):
    value = flow.get(feature_name)
    if not isinstance(value, list):
        return None, f"{feature_name}_missing"
    if any(
        isinstance(x, bool)
        or not isinstance(x, numbers.Real)
        or not math.isfinite(float(x))
        for x in value
    ):
        return None, f"{feature_name}_invalid_values"

    vector = np.asarray(value, dtype=float)
    if np.any(vector < 0):
        return None, f"{feature_name}_negative_values"
    return vector, ""


def _fit_feature(observations, transition_times, config, seed):
    d = len(observations)
    n_states = config["n_states"]
    rng = np.random.default_rng(seed)

    if n_states == 1:
        initial_means = np.asarray([np.mean(observations)])
    else:
        initial_means = np.quantile(
            observations,
            np.linspace(0.0, 1.0, n_states),
        )

    noise_scale = max(float(np.std(observations)) * 0.01, 1e-6)
    means = initial_means + rng.normal(0.0, noise_scale, n_states)

    global_variance = max(float(np.var(observations)), np.finfo(float).eps)
    variances = np.full(n_states, max(global_variance, 1e-6))
    pi = np.full(n_states, 1.0 / n_states)
    Q = _initial_q(n_states, transition_times, seed)

    log_likelihood = -np.inf
    converged = False

    for _ in range(config["n_iter"]):
        transition_matrices = [
            ctmc_transition_matrix(Q, elapsed)
            for elapsed in transition_times
        ]
        log_emissions = _emission_log_probabilities(
            observations,
            means,
            variances,
        )
        gamma, xi_sum, new_log_likelihood = _forward_backward(
            log_emissions,
            transition_matrices,
            pi,
        )

        if not np.isfinite(new_log_likelihood):
            raise FloatingPointError("CT-HMM likelihood became nonfinite")

        if abs(new_log_likelihood - log_likelihood) <= config["tolerance"]:
            converged = True
        log_likelihood = new_log_likelihood

        pi = np.maximum(gamma[0], np.finfo(float).eps)
        pi /= pi.sum()

        weighted_sum = gamma.T @ observations
        occupancy = np.maximum(
            gamma.sum(axis=0),
            np.finfo(float).eps,
        )
        means = weighted_sum / occupancy

        for i in range(n_states):
            residual = observations - means[i]
            variances[i] = max(
                float(
                    np.dot(gamma[:, i], residual * residual)
                    / occupancy[i]
                ),
                global_variance * 1e-6,
            )

        if d > 1:
            residence = np.zeros(n_states, dtype=float)
            for k, elapsed in enumerate(transition_times[: d - 1]):
                residence += gamma[k] * elapsed

            epsilon = 1e-8
            new_Q = np.zeros_like(Q)
            for i in range(n_states):
                residence_time = float(residence[i])
                for j in range(n_states):
                    if i == j:
                        continue
                    expected_transitions = float(xi_sum[i, j])
                    if residence_time > epsilon:
                        new_Q[i, j] = (
                            expected_transitions + epsilon
                        ) / (residence_time + epsilon)
                new_Q[i, i] = -new_Q[i].sum()
            Q = new_Q

        if converged:
            break

    transition_matrices = [
        ctmc_transition_matrix(Q, elapsed)
        for elapsed in transition_times
    ]
    log_emissions = _emission_log_probabilities(
        observations,
        means,
        variances,
    )
    _, _, log_likelihood = _forward_backward(
        log_emissions,
        transition_matrices,
        pi,
    )
    hidden_states = _viterbi(
        log_emissions,
        transition_matrices,
        pi,
    )
    score = score_decoded_sequence(hidden_states, d=d)
    return score, Q, converged, log_likelihood


def score_flow(flow, config=None):
    settings = _cthmm_config(config)
    if not isinstance(flow, dict):
        raise ValueError("Each flow must be a JSON object.")
    if "flow_id" not in flow:
        raise ValueError("Flow is missing flow_id.")

    feature_scores = {}
    feature_details = {}
    skip_reasons = []
    fitted_q = []
    fitted_convergence = []
    fitted_seeds = []

    for feature_name in ("time_deltas", "bytes_sent"):
        values, vector_reason = _valid_vector(flow, feature_name)
        if values is None:
            score = None
            skip_reason = vector_reason
            d = 0
        else:
            d = len(values)
            min_observations = settings["min_events"] - (
                1 if feature_name == "time_deltas" else 0
            )
            if d < min_observations:
                score = None
                skip_reason = (
                    f"fewer_than_{min_observations}_observations"
                )
            elif d < settings["n_states"]:
                score = None
                skip_reason = (
                    f"not_enough_observations_for_{settings['n_states']}_states"
                )
            elif float(np.var(values)) <= np.finfo(float).eps:
                score = None
                skip_reason = "zero_variance"
            else:
                if feature_name == "time_deltas":
                    transition_times = values[1:] if d > 1 else np.asarray([])
                else:
                    transition_times = np.asarray(
                        flow.get("time_deltas", []),
                        dtype=float,
                    )
                    if len(transition_times) != d - 1:
                        score = None
                        skip_reason = "bytes_sent_time_deltas_length_mismatch"
                        feature_scores[feature_name] = score
                        feature_details[feature_name] = {
                            "d": d,
                            "status": "skipped",
                            "skip_reason": skip_reason,
                        }
                        skip_reasons.append(
                            f"{feature_name}: {skip_reason}"
                        )
                        continue
                    if any(
                        not math.isfinite(float(x)) or float(x) < 0
                        for x in transition_times
                    ):
                        score = None
                        skip_reason = "invalid_transition_times"
                        feature_scores[feature_name] = score
                        feature_details[feature_name] = {
                            "d": d,
                            "status": "skipped",
                            "skip_reason": skip_reason,
                        }
                        skip_reasons.append(
                            f"{feature_name}: {skip_reason}"
                        )
                        continue

                try:
                    best = None
                    best_loglik = -np.inf
                    best_seed = settings["random_seed"]

                    for init_index in range(settings["n_init"]):
                        seed = settings["random_seed"] + init_index
                        candidate = _fit_feature(
                            values,
                            transition_times,
                            settings,
                            seed,
                        )
                        _, _, _, candidate_loglik = candidate
                        if candidate_loglik > best_loglik:
                            best_loglik = candidate_loglik
                            best = candidate
                            best_seed = seed

                    if best is None:
                        raise FloatingPointError("CT-HMM fit failed")

                    score, candidate_Q, candidate_converged, _ = best
                    skip_reason = ""
                    fitted_q.append(candidate_Q)
                    fitted_convergence.append(candidate_converged)
                    fitted_seeds.append(best_seed)
                except (
                    FloatingPointError,
                    ValueError,
                    np.linalg.LinAlgError,
                ):
                    score = None
                    skip_reason = "cthmm_numerical_fit_failed"

        feature_scores[feature_name] = score
        feature_details[feature_name] = {
            "d": d,
            "status": "ok" if score is not None else "skipped",
            "skip_reason": skip_reason,
        }
        if skip_reason:
            skip_reasons.append(f"{feature_name}: {skip_reason}")

    valid_scores = [
        score for score in feature_scores.values()
        if score is not None
    ]
    if valid_scores:
        status = "ok"
        overall_score = round(
            float(sum(valid_scores) / len(valid_scores)),
            6,
        )
    else:
        status = "skipped"
        overall_score = None

    Q = fitted_q[0] if fitted_q else None
    skip_reason = "; ".join(skip_reasons)

    return {
        "flow_id": flow["flow_id"],
        "method": "continuous_time_gaussian_hmm",
        "event_count": flow.get("event_count"),
        "score": overall_score,
        "status": status,
        "skip_reason": skip_reason,
        "reason": skip_reason,
        "feature_scores": feature_scores,
        "feature_details": feature_details,
        "metadata": {
            "n_states": settings["n_states"],
            "n_iter": settings["n_iter"],
            "n_init": settings["n_init"],
            "random_seed": settings["random_seed"],
            "seed": (
                fitted_seeds[0]
                if fitted_seeds
                else settings["random_seed"]
            ),
            "converged": (
                bool(fitted_convergence)
                and all(fitted_convergence)
            ),
            "Q": Q.tolist() if Q is not None else None,
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