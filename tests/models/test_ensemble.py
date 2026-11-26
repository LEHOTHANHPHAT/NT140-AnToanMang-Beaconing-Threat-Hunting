import unittest

from src.models.ensemble import combine_scores


class EnsembleTests(unittest.TestCase):
    def test_max_is_applied_per_feature_before_mean(self):
        combined = combine_scores(
            {"time_deltas": 0.8, "bytes_sent": 0.5},
            {"time_deltas": 0.6, "bytes_sent": 0.9},
            {
                "ensemble": {
                    "state_model": "ct_hmm",
                    "features": ["time_deltas", "bytes_sent"],
                    "partial_policy": "strict",
                }
            },
        )
        self.assertEqual(combined["score"], 0.85)
        self.assertEqual(combined["feature_scores"], {
            "time_deltas": 0.8,
            "bytes_sent": 0.9,
        })

    def test_strict_policy_skips_flow_when_one_feature_is_missing(self):
        combined = combine_scores(
            {"time_deltas": 0.8, "bytes_sent": None},
            {"time_deltas": 0.6, "bytes_sent": 0.9},
            {"partial_policy": "strict"},
        )
        self.assertEqual(combined["status"], "skipped")
        self.assertIsNone(combined["score"])

    def test_fallback_policy_uses_available_branch_per_feature(self):
        combined = combine_scores(
            {"time_deltas": None, "bytes_sent": 0.5},
            {"time_deltas": 0.7, "bytes_sent": None},
            {
                "state_model": "hmm",
                "features": ["time_deltas", "bytes_sent"],
                "partial_policy": "fallback",
            },
        )
        self.assertEqual(combined["status"], "partial_scored")
        self.assertEqual(combined["feature_scores"]["time_deltas"], 0.7)
        self.assertEqual(combined["feature_scores"]["bytes_sent"], 0.5)
        self.assertEqual(combined["score"], 0.6)


if __name__ == "__main__":
    unittest.main()
