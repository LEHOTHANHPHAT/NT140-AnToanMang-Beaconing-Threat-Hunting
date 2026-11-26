"""Shared helpers for the HMM and CT-HMM beaconing scores.

Score definition (both state models)::

    S = (n_b / d) * 1 / (1 + CV_b)

* ``n_b`` is the number of observations Viterbi-decoded into the dominant
  hidden state ``b`` and ``d`` the number of observations.
* ``CV_b = sigma_b / |mu_b|`` is the coefficient of variation of the dominant
  state's Gaussian emission.

``n_b / d`` alone measures state *imbalance*, not regularity: exponential
inter-arrival times fit one large "short gap" state plus a small tail state
(high n_b / d), while a jittered beacon forced into two states splits about
50/50 (low n_b / d). That made random traffic outrank periodic traffic.
Weighting by ``1 / (1 + CV_b)`` requires the dominant state to also be
tight, and choosing the number of states by BIC (default) stops a single
regular regime from being split in two artificially. ``S`` is in [0, 1];
higher means more beaconing-like.

Variances are floored at ``(variance_floor_ratio * scale)**2`` so a
perfectly periodic (zero-variance) sequence yields a well-defined model with
``CV_b`` close to ``variance_floor_ratio`` and a score close to 1, instead
of being skipped.
"""

import math

import numpy as np


DEFAULT_VARIANCE_FLOOR_RATIO = 1e-3
_ABSOLUTE_VARIANCE_FLOOR = 1e-12


def variance_floor(values, ratio=DEFAULT_VARIANCE_FLOOR_RATIO):
    """Scale-aware lower bound for Gaussian emission variances."""
    values = np.asarray(values, dtype=float)
    scale = max(abs(float(np.mean(values))), float(np.std(values)))
    return max((ratio * scale) ** 2, _ABSOLUTE_VARIANCE_FLOOR)


def is_degenerate(values, floor):
    """True when the sequence variance does not exceed the variance floor."""
    return float(np.var(values)) <= floor


def single_state_fit(values, floor):
    """Closed-form one-state Gaussian 'HMM' (used for k = 1 and constants)."""
    values = np.asarray(values, dtype=float)
    mean = float(np.mean(values))
    variance = max(float(np.var(values)), floor)
    residual = values - mean
    log_likelihood = float(-0.5 * np.sum(
        np.log(2.0 * np.pi * variance) + residual * residual / variance
    ))
    return {
        "states": np.zeros(values.size, dtype=np.int64),
        "means": np.asarray([mean]),
        "variances": np.asarray([variance]),
        "log_likelihood": log_likelihood,
    }


def bic(log_likelihood, n_parameters, d):
    return -2.0 * log_likelihood + n_parameters * math.log(max(d, 1))


def dominant_state_score(states, means, variances, d=None, floor=None):
    """Return (score, details) for a decoded sequence and its emissions."""
    states = np.asarray(states, dtype=np.int64)
    if states.ndim != 1 or states.size == 0:
        raise ValueError("states must be a nonempty 1-D sequence.")
    d = states.size if d is None else d
    counts = np.bincount(states, minlength=len(means))
    dominant = int(np.argmax(counts))
    dominance = counts[dominant] / d

    mean = abs(float(means[dominant]))
    std = math.sqrt(max(float(variances[dominant]), 0.0))
    floor_std = math.sqrt(floor) if floor is not None else 0.0
    if mean > 0:
        cv = std / mean
    else:
        # A zero-mean constant (e.g. all-zero deltas) is perfectly regular.
        cv = 0.0 if std <= floor_std * (1 + 1e-9) else math.inf
    regularity = 1.0 / (1.0 + cv)
    score = round(float(dominance * regularity), 6)
    return score, {
        "dominant_state": dominant,
        "dominance": round(float(dominance), 6),
        "dominant_cv": round(float(cv), 6) if math.isfinite(cv) else None,
    }
