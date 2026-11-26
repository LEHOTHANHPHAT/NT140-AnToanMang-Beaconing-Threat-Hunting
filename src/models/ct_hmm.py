"""Continuous-time Hidden Markov Model with Gaussian emissions.

This module is intentionally separate from the discrete-step HMM. Hidden-state
transitions are functions of elapsed time through a CTMC generator ``Q`` and
``P(Δt) = expm(Q Δt)`` (scipy.linalg.expm).

Implementation notes (see docs/methodology.md for the full discussion):

* Score: dominant-state share weighted by emission regularity, shared with the
  discrete HMM (src/models/state_scoring.py). Higher = more beaconing-like.
* Emission variances are floored (scale-aware), so zero-variance sequences are
  scored instead of skipped.
* Number of states is chosen by BIC over 1..n_states (``state_selection``).
* ``Q`` is re-estimated with a first-order approximation of the exact CT-HMM
  EM step; see :func:`update_generator`.
* Speed: ``expm`` is evaluated once per distinct Δt per EM iteration
  (batched), forward-backward uses scaled probabilities with vectorised
  ``xi`` accumulation, and EM stops at ``n_iter`` or at relative tolerance.
"""

import math
import numbers
from collections import Counter

import numpy as np
from scipy.linalg import expm
from scipy.special import logsumexp

from src.models.state_scoring import (
    DEFAULT_VARIANCE_FLOOR_RATIO,
    bic,
    dominant_state_score,
    is_degenerate,
    single_state_fit,
    variance_floor,
)


DEFAULT_CONFIG = {
    "min_events": 5,
    "n_states": 2,
    # Upper bound on EM iterations per initialisation.
    "n_iter": 50,
    "random_seed": 42,
    "n_init": 3,
    # Relative log-likelihood tolerance: |ΔLL| <= tolerance * max(1, |LL|).
    "tolerance": 1e-5,
    "state_selection": "bic",
    "variance_floor_ratio": DEFAULT_VARIANCE_FLOOR_RATIO,
}

_TINY = np.finfo(float).tiny
_EPS = np.finfo(float).eps


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
    for key in ("tolerance", "variance_floor_ratio"):
        if isinstance(merged[key], bool) or not isinstance(merged[key], numbers.Real):
            raise ValueError(f"CT-HMM {key} must be numeric.")
    if merged["min_events"] < 2:
        raise ValueError("CT-HMM min_events must be an integer >= 2.")
    if merged["n_states"] < 1:
        raise ValueError("CT-HMM n_states must be an integer >= 1.")
    if merged["n_iter"] < 1 or merged["n_init"] < 1:
        raise ValueError("CT-HMM n_iter and n_init must be integers >= 1.")
    if merged["tolerance"] <= 0:
        raise ValueError("CT-HMM tolerance must be positive.")
    if merged["variance_floor_ratio"] <= 0:
        raise ValueError("CT-HMM variance_floor_ratio must be positive.")
    if merged["state_selection"] not in ("bic", "fixed"):
        raise ValueError("CT-HMM state_selection must be 'bic' or 'fixed'.")
    return merged


def _normalise_rows(P):
    P = np.maximum(P, 0.0)
    return P / np.maximum(P.sum(axis=-1, keepdims=True), _EPS)


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
        return np.eye(Q.shape[0], dtype=float)
    return _normalise_rows(expm(Q * elapsed_time))


expm_transition_matrix = ctmc_transition_matrix


def transition_matrices(Q, elapsed_times):
    """Return P(Δt_k) for every interval, shape (len(elapsed_times), n, n).

    ``expm`` is evaluated once (batched) over the *distinct* positive Δt
    values; repeated intervals - typical of beacons - reuse the result.
    Δt = 0 maps to the identity.
    """
    Q = np.asarray(Q, dtype=float)
    elapsed_times = np.asarray(elapsed_times, dtype=float)
    n = Q.shape[0]
    if elapsed_times.size == 0:
        return np.zeros((0, n, n), dtype=float)
    unique_times, inverse = np.unique(elapsed_times, return_inverse=True)
    unique_P = np.empty((unique_times.size, n, n), dtype=float)
    positive = unique_times > 0
    unique_P[~positive] = np.eye(n)
    if positive.any():
        stacked = Q[None, :, :] * unique_times[positive][:, None, None]
        unique_P[positive] = _normalise_rows(expm(stacked))
    return unique_P[inverse.reshape(-1)]


def score_decoded_sequence(hidden_states, d=None):
    """Dominant-state share n_b / d (kept for API compatibility)."""
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
        Q[:] = scale / (n_states - 1)
        np.fill_diagonal(Q, 0.0)
        np.fill_diagonal(Q, -Q.sum(axis=1))
    return Q


def _emission_log_probabilities(observations, means, variances):
    differences = observations[:, None] - means[None, :]
    return -0.5 * (
        np.log(2.0 * np.pi * variances)[None, :]
        + differences * differences / variances[None, :]
    )


def _forward_backward_log(log_emissions, transition_matrices, pi):
    """Log-space forward-backward; slow but robust fallback."""
    d, n_states = log_emissions.shape
    log_P = np.log(np.maximum(transition_matrices, _TINY))
    alpha = np.full((d, n_states), -np.inf)
    beta = np.full((d, n_states), -np.inf)
    alpha[0] = np.log(np.maximum(pi, _TINY)) + log_emissions[0]
    for k in range(1, d):
        alpha[k] = log_emissions[k] + logsumexp(
            alpha[k - 1][:, None] + log_P[k - 1], axis=0)
    beta[-1] = 0.0
    for k in range(d - 2, -1, -1):
        beta[k] = logsumexp(
            log_P[k] + log_emissions[k + 1][None, :] + beta[k + 1][None, :],
            axis=1)
    log_likelihood = logsumexp(alpha[-1])
    if not np.isfinite(log_likelihood):
        raise FloatingPointError("nonfinite forward-backward likelihood")
    gamma = np.exp(alpha + beta - log_likelihood)
    gamma /= np.maximum(gamma.sum(axis=1, keepdims=True), _EPS)
    if d > 1:
        log_xi = (alpha[:-1, :, None] + log_P[: d - 1]
                  + (log_emissions[1:] + beta[1:])[:, None, :])
        log_xi -= logsumexp(log_xi, axis=(1, 2), keepdims=True)
        xi_sum = np.exp(log_xi).sum(axis=0)
    else:
        xi_sum = np.zeros((n_states, n_states))
    return gamma, xi_sum, float(log_likelihood)


def _forward_backward(log_emissions, transition_matrices, pi):
    """Scaled forward-backward.

    Returns (gamma, xi_sum, log_likelihood). Emissions are rescaled per
    time step and alpha/beta normalised per step (Rabiner scaling), which is
    exact and avoids per-step ``logsumexp``. ``xi`` is accumulated with one
    vectorised expression. Falls back to log space if scaling underflows.
    """
    d, n_states = log_emissions.shape
    transition_matrices = np.asarray(transition_matrices, dtype=float)
    row_max = log_emissions.max(axis=1, keepdims=True)
    B = np.exp(log_emissions - row_max)

    alpha = np.empty((d, n_states))
    scale = np.empty(d)
    a = np.maximum(pi, 0.0) * B[0]
    scale[0] = a.sum()
    if not scale[0] > 0:
        return _forward_backward_log(log_emissions, transition_matrices, pi)
    alpha[0] = a / scale[0]
    for k in range(1, d):
        a = (alpha[k - 1] @ transition_matrices[k - 1]) * B[k]
        s = a.sum()
        if not (s > 0 and np.isfinite(s)):
            return _forward_backward_log(log_emissions, transition_matrices, pi)
        scale[k] = s
        alpha[k] = a / s

    beta = np.empty((d, n_states))
    beta[-1] = 1.0
    for k in range(d - 2, -1, -1):
        beta[k] = transition_matrices[k] @ (B[k + 1] * beta[k + 1]) / scale[k + 1]

    log_likelihood = float(np.log(scale).sum() + row_max.sum())
    if not np.isfinite(log_likelihood):
        raise FloatingPointError("nonfinite forward-backward likelihood")

    gamma = alpha * beta
    gamma /= np.maximum(gamma.sum(axis=1, keepdims=True), _EPS)

    if d > 1:
        right = (B[1:] * beta[1:]) / scale[1:, None]
        xi = alpha[:-1, :, None] * transition_matrices[: d - 1] * right[:, None, :]
        xi /= np.maximum(xi.sum(axis=(1, 2), keepdims=True), _EPS)
        xi_sum = xi.sum(axis=0)
    else:
        xi_sum = np.zeros((n_states, n_states))
    return gamma, xi_sum, log_likelihood


def _viterbi(log_emissions, transition_matrices, pi):
    d, n_states = log_emissions.shape
    log_P = np.log(np.maximum(np.asarray(transition_matrices), _TINY))
    delta = np.empty((d, n_states))
    psi = np.zeros((d, n_states), dtype=np.int64)
    columns = np.arange(n_states)

    delta[0] = np.log(np.maximum(pi, _TINY)) + log_emissions[0]
    for k in range(1, d):
        candidates = delta[k - 1][:, None] + log_P[k - 1]
        psi[k] = np.argmax(candidates, axis=0)
        delta[k] = candidates[psi[k], columns] + log_emissions[k]

    states = np.empty(d, dtype=np.int64)
    states[-1] = np.argmax(delta[-1])
    for k in range(d - 2, -1, -1):
        states[k] = psi[k + 1, states[k + 1]]
    return states


def update_generator(gamma, xi_sum, transition_times, epsilon=1e-8):
    """M-step for the CTMC generator Q - a first-order APPROXIMATION.

    Computes, for i != j::

        q_ij = (N_ij + eps) / (T_i + eps)
        N_ij = sum_k xi_k(i, j)              # expected i -> j between obs k, k+1
        T_i  = sum_k gamma_k(i) * Δt_k       # expected time spent in i
        q_ii = -sum_{j != i} q_ij

    This is the closed-form MLE of a fully observed CTMC (counts / dwell
    time) with two simplifications relative to exact CT-HMM EM
    (Metzner et al. 2007; Liu et al. 2015, which evaluate the end-point
    conditioned expectations with Van Loan's block-matrix integral of expm):

    1. **At most one jump per interval.** ``xi_k(i, j)`` is the probability
       of being in i at observation k and j at k + 1; it is used as the
       expected number of i -> j jumps, so multiple jumps or excursions
       through other states inside one Δt are ignored (i -> i "round trips"
       contribute nothing).
    2. **Dwell time is charged to the start state.** The whole interval Δt_k
       is attributed to the state at observation k, weighted by gamma_k(i),
       instead of E[time in i | state at both ends].

    Both are accurate when q_ij * Δt << 1 and biased (rates underestimated,
    dwell time misallocated) when transitions are likely within one interval.
    ``eps`` avoids division by zero and slightly shrinks rates of states with
    tiny occupancy. Rows of states with (near) zero dwell time are set to 0
    (absorbing) for that iteration.
    """
    n_states = gamma.shape[1]
    Q = np.zeros((n_states, n_states), dtype=float)
    d = gamma.shape[0]
    if d < 2 or n_states < 2:
        return Q
    times = np.asarray(transition_times[: d - 1], dtype=float)
    residence = gamma[: d - 1].T @ times
    for i in range(n_states):
        if residence[i] > epsilon:
            Q[i] = (xi_sum[i] + epsilon) / (residence[i] + epsilon)
            Q[i, i] = 0.0
            Q[i, i] = -Q[i].sum()
    return Q


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


def _n_parameters(k):
    # initial probabilities + off-diagonal rates + mean and variance per state
    return (k - 1) + k * (k - 1) + 2 * k


def _fit_feature(observations, transition_times, config, seed, n_states=None, floor=None):
    """EM fit with ``n_states`` states from one random initialisation."""
    d = len(observations)
    n_states = config["n_states"] if n_states is None else n_states
    floor = variance_floor(observations, config["variance_floor_ratio"]) if floor is None else floor
    rng = np.random.default_rng(seed)

    if n_states == 1:
        initial_means = np.asarray([np.mean(observations)])
    else:
        initial_means = np.quantile(observations, np.linspace(0.0, 1.0, n_states))
    noise_scale = max(float(np.std(observations)) * 0.01, math.sqrt(floor))
    means = initial_means + rng.normal(0.0, noise_scale, n_states)
    variances = np.full(n_states, max(float(np.var(observations)), floor))
    pi = np.full(n_states, 1.0 / n_states)
    Q = _initial_q(n_states, transition_times, seed)

    log_likelihood = -np.inf
    converged = False
    iterations = 0
    for _ in range(config["n_iter"]):
        iterations += 1
        P = transition_matrices(Q, transition_times)
        log_emissions = _emission_log_probabilities(observations, means, variances)
        gamma, xi_sum, new_log_likelihood = _forward_backward(log_emissions, P, pi)

        improvement = new_log_likelihood - log_likelihood
        log_likelihood = new_log_likelihood
        if abs(improvement) <= config["tolerance"] * max(1.0, abs(log_likelihood)):
            converged = True
            break

        pi = np.maximum(gamma[0], _EPS)
        pi /= pi.sum()
        occupancy = np.maximum(gamma.sum(axis=0), _EPS)
        means = (gamma.T @ observations) / occupancy
        residual = observations[:, None] - means[None, :]
        variances = np.maximum(
            (gamma * residual * residual).sum(axis=0) / occupancy, floor,
        )
        Q = update_generator(gamma, xi_sum, transition_times)

    P = transition_matrices(Q, transition_times)
    log_emissions = _emission_log_probabilities(observations, means, variances)
    _, _, log_likelihood = _forward_backward(log_emissions, P, pi)
    states = _viterbi(log_emissions, P, pi)
    return {
        "states": states,
        "means": means,
        "variances": variances,
        "Q": Q,
        "converged": converged,
        "log_likelihood": float(log_likelihood),
        "iterations": iterations,
        "seed": seed,
    }


def _fit_best(values, transition_times, settings):
    """Fit every candidate state count, keep the BIC-best model."""
    d = len(values)
    floor = variance_floor(values, settings["variance_floor_ratio"])
    if is_degenerate(values, floor):
        candidate_states = (1,)
    elif settings["state_selection"] == "bic":
        candidate_states = range(1, min(settings["n_states"], d) + 1)
    else:
        candidate_states = (settings["n_states"],)

    best = None
    for k in candidate_states:
        if k == 1:
            fit = single_state_fit(values, floor)
            fit.update(Q=np.zeros((1, 1)), converged=True, iterations=0,
                       seed=settings["random_seed"])
        else:
            fit = None
            for init_index in range(settings["n_init"]):
                candidate = _fit_feature(
                    values, transition_times, settings,
                    settings["random_seed"] + init_index, n_states=k, floor=floor,
                )
                if fit is None or candidate["log_likelihood"] > fit["log_likelihood"]:
                    fit = candidate
        fit["n_states"] = k
        fit["bic"] = bic(fit["log_likelihood"], _n_parameters(k), d)
        if best is None or fit["bic"] < best["bic"]:
            best = fit

    score, details = dominant_state_score(
        best["states"], best["means"], best["variances"], d=d, floor=floor,
    )
    best["details"] = details
    return score, best


def _transition_times_for(flow, feature_name, values):
    """Elapsed time between consecutive observations of ``feature_name``."""
    d = len(values)
    if feature_name == "time_deltas":
        return values[1:] if d > 1 else np.asarray([]), ""
    raw = flow.get("time_deltas", [])
    if not isinstance(raw, list) or len(raw) != d - 1:
        return None, "bytes_sent_time_deltas_length_mismatch"
    try:
        times = np.asarray(raw, dtype=float)
    except (TypeError, ValueError):
        return None, "invalid_transition_times"
    if not np.isfinite(times).all() or np.any(times < 0):
        return None, "invalid_transition_times"
    return times, ""


def score_flow(flow, config=None):
    settings = _cthmm_config(config)
    if not isinstance(flow, dict):
        raise ValueError("Each flow must be a JSON object.")
    if "flow_id" not in flow:
        raise ValueError("Flow is missing flow_id.")

    feature_scores = {}
    feature_details = {}
    skip_reasons = []
    fits = []

    for feature_name in ("time_deltas", "bytes_sent"):
        score = None
        fit = None
        values, skip_reason = _valid_vector(flow, feature_name)
        d = 0 if values is None else len(values)
        if values is not None:
            min_observations = settings["min_events"] - (
                1 if feature_name == "time_deltas" else 0
            )
            if d < min_observations:
                skip_reason = f"fewer_than_{min_observations}_observations"
            elif settings["state_selection"] == "fixed" and d < settings["n_states"]:
                skip_reason = (
                    f"not_enough_observations_for_{settings['n_states']}_states"
                )
            else:
                times, skip_reason = _transition_times_for(flow, feature_name, values)
                if not skip_reason:
                    try:
                        score, fit = _fit_best(values, times, settings)
                    except (FloatingPointError, ValueError, np.linalg.LinAlgError):
                        score, fit = None, None
                        skip_reason = "cthmm_numerical_fit_failed"

        feature_scores[feature_name] = score
        feature_details[feature_name] = {
            "d": d,
            "status": "ok" if score is not None else "skipped",
            "skip_reason": skip_reason,
        }
        if fit is not None:
            fits.append(fit)
            feature_details[feature_name].update(
                fit["details"],
                selected_states=fit["n_states"],
                em_iterations=fit["iterations"],
            )
        if skip_reason:
            skip_reasons.append(f"{feature_name}: {skip_reason}")

    valid_scores = [score for score in feature_scores.values() if score is not None]
    if valid_scores:
        status = "ok"
        overall_score = round(float(sum(valid_scores) / len(valid_scores)), 6)
    else:
        status = "skipped"
        overall_score = None

    skip_reason = "; ".join(skip_reasons)
    Q = fits[0]["Q"] if fits else None
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
            "state_selection": settings["state_selection"],
            "variance_floor_ratio": settings["variance_floor_ratio"],
            "random_seed": settings["random_seed"],
            "seed": fits[0]["seed"] if fits else settings["random_seed"],
            "converged": bool(fits) and all(fit["converged"] for fit in fits),
            "em_iterations": max((fit["iterations"] for fit in fits), default=0),
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
