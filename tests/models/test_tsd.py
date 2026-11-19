import unittest

from src.models.tsd import score_flow, score_residual


class TSDTests(unittest.TestCase):
    def test_sequence_shorter_than_two_cycles_is_skipped(self):
        flow = {
            "flow_id": "short",
            "event_count": 8,
            "time_deltas": [1.0] * 7,
            "bytes_sent": [100, 100, 100, 100, 100, 100, 100, 100],
        }
        record = score_flow(flow, {"tsd": {"mode": "event", "period": 6}})
        self.assertEqual(record["status"], "skipped")
        self.assertIsNone(record["score"])
        self.assertIn("insufficient_cycles", record["skip_reason"])

    def test_perfect_periodic_sequence_has_score_one(self):
        flow = {
            "flow_id": "periodic",
            "event_count": 24,
            "time_deltas": ([10.0, 20.0, 30.0] * 7)[:23],
            "bytes_sent": ([100, 200, 300] * 8),
        }
        record = score_flow(flow, {"tsd": {"mode": "event", "period": 3}})
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["score"], 1.0)

    def test_single_outlier_is_detected_and_reduces_score(self):
        residual = []
        for i in range(24):
            residual.append(0.0)
        residual[12] = 100.0

        score, d, reason = score_residual(residual, z_threshold=3.0)
        self.assertEqual(reason, "")
        self.assertEqual(d, 24)
        self.assertLess(score, 1.0)

        periodic_with_outlier = ([100, 200, 300] * 8)
        periodic_with_outlier[12] = 100000
        flow = {
            "flow_id": "outlier",
            "event_count": len(periodic_with_outlier),
            "time_deltas": ([1.0, 2.0, 3.0] * 8)[:len(periodic_with_outlier) - 1],
            "bytes_sent": periodic_with_outlier,
        }
        record = score_flow(flow, {"tsd": {"mode": "event", "period": 3}})
        self.assertEqual(record["status"], "ok")
        self.assertLess(record["feature_scores"]["bytes_sent"], 1.0)

    def test_clock_mode_records_period_and_bin_aggregation(self):
        flow = {
            "flow_id": "clock",
            "event_count": 12,
            "timestamps": [
                f"2026-01-01T00:00:{second:02d}Z"
                for second in range(12)
            ],
            "time_deltas": [1.0] * 11,
            "bytes_sent": [100] * 12,
        }
        record = score_flow(flow, {
            "tsd": {
                "mode": "clock",
                "bin_size_seconds": 10,
                "clock_period_seconds": 60,
                "clock_aggregation": "sum",
                "z_threshold": 3.0,
            }
        })
        self.assertEqual(record["metadata"]["mode"], "clock")
        self.assertEqual(record["metadata"]["period"], 6)
        self.assertIn(record["status"], ("ok", "skipped"))


if __name__ == "__main__":
    unittest.main()
