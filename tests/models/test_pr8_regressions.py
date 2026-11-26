"""Regression tests for the PR #8 review findings (issues 1-6).

Each class reproduces one reported defect. Sequences are generated the same
way as data/synthetic/evaluation-v1 (50 events, 60 s nominal period,
constant 500 bytes) so the tests track the evaluation behaviour.
"""

import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from scipy.special import logsumexp

from src.models import ct_hmm, ensemble, hmm, tsd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FAST_HMM = {"n_states": 2, "n_iter": 30, "n_init": 2, "random_seed": 42}


def _flow(flow_id, deltas, byte_value=500):
    deltas = [float(x) for x in deltas]
    return {
        "flow_id": flow_id,
        "event_count": len(deltas) + 1,
        "time_deltas": deltas,
        "bytes_sent": [byte_value] * (len(deltas) + 1),
    }


def _regular(seed):
    return _flow(f"regular-{seed}", [60.0] * 49)


def _jitter(seed):
    rng = np.random.default_rng(seed)
    return _flow(f"jitter-{seed}", rng.uniform(48, 72, 49))


def _random(seed):
    rng = np.random.default_rng(seed)
    return _flow(f"random-{seed}", rng.exponential(60, 49))


def _config(name):
    return {name: dict(FAST_HMM, min_events=5)}


class Issue1ZeroVarianceTests(unittest.TestCase):
    """Perfectly periodic sequences must be scored high, not skipped."""

    def test_hmm_scores_perfectly_periodic_flow_high(self):
        record = hmm.score_flow(_regular(0), _config("hmm"))
        self.assertEqual(record["status"], "ok")
        self.assertNotIn("zero_variance", record["skip_reason"])
        self.assertGreaterEqual(record["feature_scores"]["time_deltas"], 0.99)
        self.assertGreaterEqual(record["score"], 0.99)

    def test_ct_hmm_scores_perfectly_periodic_flow_high(self):
        record = ct_hmm.score_flow(_regular(0), _config("ct_hmm"))
        self.assertEqual(record["status"], "ok")
        self.assertNotIn("zero_variance", record["skip_reason"])
        self.assertGreaterEqual(record["feature_scores"]["time_deltas"], 0.99)
        self.assertGreaterEqual(record["score"], 0.99)

    def test_constant_feature_next_to_varying_feature_is_scored(self):
        # bytes_sent is constant in every evaluation-v1 group.
        for module, name in ((hmm, "hmm"), (ct_hmm, "ct_hmm")):
            record = module.score_flow(_jitter(1), _config(name))
            self.assertIsNotNone(record["feature_scores"]["bytes_sent"], name)
            self.assertEqual(record["feature_details"]["bytes_sent"]["status"], "ok")


class Issue2EnsembleDefaultPolicyTests(unittest.TestCase):
    """The default ensemble must score any group with at least one branch."""

    def test_default_config_scores_when_one_branch_feature_is_missing(self):
        combined = ensemble.combine_scores(
            {"time_deltas": 0.8, "bytes_sent": None},
            {"time_deltas": 0.6, "bytes_sent": 0.9},
        )
        self.assertIsNotNone(combined["score"])
        self.assertEqual(combined["feature_scores"]["bytes_sent"], 0.9)

    def test_default_config_drops_only_the_missing_feature(self):
        combined = ensemble.combine_scores(
            {"time_deltas": 0.8, "bytes_sent": None},
            {"time_deltas": 0.6, "bytes_sent": None},
        )
        self.assertEqual(combined["status"], "partial_scored")
        self.assertEqual(combined["score"], 0.8)
        self.assertIsNone(combined["feature_scores"]["bytes_sent"])

    def test_default_config_tolerates_a_missing_component_record(self):
        combined = ensemble.combine_scores(
            None, {"time_deltas": 0.6, "bytes_sent": 0.9},
        )
        self.assertEqual(combined["score"], 0.75)

    def test_group_is_skipped_only_when_every_component_is_missing(self):
        combined = ensemble.combine_scores(
            {"time_deltas": None, "bytes_sent": None},
            {"time_deltas": None, "bytes_sent": None},
        )
        self.assertEqual(combined["status"], "skipped")
        self.assertIsNone(combined["score"])

    def test_shipped_default_config_uses_the_same_policy(self):
        import json
        config = json.loads(
            (PROJECT_ROOT / "configs/default.json").read_text(encoding="utf-8")
        )
        combined = ensemble.combine_scores(
            {"time_deltas": 0.8, "bytes_sent": None},
            {"time_deltas": 0.6, "bytes_sent": 0.9},
            config,
        )
        self.assertIsNotNone(combined["score"])


class Issue3ScoreDirectionTests(unittest.TestCase):
    """High state-model score must mean beaconing-like timing."""

    def _time_score(self, module, name, flow):
        return module.score_flow(flow, _config(name))["feature_scores"]["time_deltas"]

    def test_hmm_ranks_regular_above_jitter_above_random(self):
        for seed in (1, 2, 3):
            regular = self._time_score(hmm, "hmm", _regular(seed))
            jitter = self._time_score(hmm, "hmm", _jitter(seed))
            random = self._time_score(hmm, "hmm", _random(seed))
            self.assertGreater(regular, jitter, seed)
            self.assertGreater(jitter, random, seed)

    def test_ct_hmm_ranks_regular_above_jitter_above_random(self):
        for seed in (1, 2, 3):
            regular = self._time_score(ct_hmm, "ct_hmm", _regular(seed))
            jitter = self._time_score(ct_hmm, "ct_hmm", _jitter(seed))
            random = self._time_score(ct_hmm, "ct_hmm", _random(seed))
            self.assertGreater(regular, jitter, seed)
            self.assertGreater(jitter, random, seed)

    def test_scores_stay_in_unit_interval(self):
        for module, name in ((hmm, "hmm"), (ct_hmm, "ct_hmm")):
            for flow in (_regular(4), _jitter(4), _random(4)):
                score = module.score_flow(flow, _config(name))["score"]
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 1.0)


class Issue4TSDDiscriminationTests(unittest.TestCase):
    """TSD must separate regular, jittered and random timing."""

    def _time_score(self, flow):
        return tsd.score_flow(flow, {"tsd": {"mode": "event", "period": 6}})[
            "feature_scores"]["time_deltas"]

    def test_tsd_ranks_regular_above_jitter_above_random(self):
        for seed in (1, 2, 3):
            regular = self._time_score(_regular(seed))
            jitter = self._time_score(_jitter(seed))
            random = self._time_score(_random(seed))
            self.assertGreaterEqual(regular, 0.99)
            self.assertGreater(regular, jitter, seed)
            self.assertGreater(jitter, random, seed)

    def test_tsd_random_arrivals_are_clearly_below_one(self):
        scores = [self._time_score(_random(seed)) for seed in range(5)]
        self.assertLess(max(scores), 0.8)


class Issue5QApproximationDocumentedTests(unittest.TestCase):
    def test_q_update_docstring_states_the_approximation(self):
        doc = ct_hmm.update_generator.__doc__ or ""
        self.assertIn("approximation", doc.lower())
        self.assertIn("at most one", doc.lower())

    def test_methodology_documents_q_approximation(self):
        text = (PROJECT_ROOT / "docs/methodology.md").read_text(encoding="utf-8")
        self.assertIn("update_generator", text)
        self.assertIn("Van Loan", text)


def _reference_forward_backward(log_emissions, transition_matrices, pi):
    """Original log-space implementation, kept as a numerical oracle."""
    d, n = log_emissions.shape
    alpha = np.full((d, n), -np.inf)
    beta = np.full((d, n), -np.inf)
    alpha[0] = np.log(pi) + log_emissions[0]
    for k in range(1, d):
        alpha[k] = log_emissions[k] + logsumexp(
            alpha[k - 1][:, None] + np.log(transition_matrices[k - 1]), axis=0)
    beta[-1] = 0.0
    for k in range(d - 2, -1, -1):
        beta[k] = logsumexp(
            np.log(transition_matrices[k]) + log_emissions[k + 1][None, :]
            + beta[k + 1][None, :], axis=1)
    ll = logsumexp(alpha[-1])
    gamma = np.exp(alpha + beta - ll)
    xi = np.zeros((n, n))
    for k in range(d - 1):
        log_xi = (alpha[k][:, None] + np.log(transition_matrices[k])
                  + log_emissions[k + 1][None, :] + beta[k + 1][None, :])
        xi += np.exp(log_xi - logsumexp(log_xi))
    return gamma, xi, ll


class Issue6PerformanceTests(unittest.TestCase):
    def test_expm_is_computed_once_per_distinct_elapsed_time(self):
        Q = np.array([[-0.2, 0.2], [0.05, -0.05]])
        times = np.array([60.0, 60.0, 30.0, 60.0, 30.0, 0.0, 60.0])
        with mock.patch.object(ct_hmm, "expm", wraps=ct_hmm.expm) as spy:
            matrices = ct_hmm.transition_matrices(Q, times)
        self.assertEqual(matrices.shape, (len(times), 2, 2))
        # Distinct positive Δt values: 30 and 60 (Δt = 0 is the identity).
        self.assertLessEqual(spy.call_count, 2)
        for k, elapsed in enumerate(times):
            np.testing.assert_allclose(
                matrices[k], ct_hmm.ctmc_transition_matrix(Q, elapsed), atol=1e-12)

    def test_vectorized_forward_backward_matches_log_space_reference(self):
        rng = np.random.default_rng(0)
        d, n = 40, 3
        log_emissions = rng.normal(-3, 2, (d, n))
        raw = rng.uniform(0.1, 1.0, (d - 1, n, n))
        transition_matrices = raw / raw.sum(axis=2, keepdims=True)
        pi = np.array([0.2, 0.5, 0.3])

        gamma, xi, ll = ct_hmm._forward_backward(log_emissions, transition_matrices, pi)
        ref_gamma, ref_xi, ref_ll = _reference_forward_backward(
            log_emissions, transition_matrices, pi)
        np.testing.assert_allclose(gamma, ref_gamma, atol=1e-9)
        np.testing.assert_allclose(xi, ref_xi, atol=1e-9)
        self.assertAlmostEqual(ll, ref_ll, places=8)

    def test_em_iterations_are_capped_by_n_iter(self):
        record = ct_hmm.score_flow(
            _random(7),
            {"ct_hmm": dict(FAST_HMM, n_iter=3, min_events=5)},
        )
        self.assertEqual(record["status"], "ok")
        self.assertLessEqual(record["metadata"]["em_iterations"], 3)


if __name__ == "__main__":
    unittest.main()
