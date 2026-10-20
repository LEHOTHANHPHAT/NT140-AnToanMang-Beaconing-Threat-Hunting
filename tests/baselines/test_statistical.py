import unittest

from src.baselines.statistical import score_flow


def make_flow(deltas):
    return {"flow_id": "test", "event_count": len(deltas) + 1, "time_deltas": deltas}


class BaselineTests(unittest.TestCase):
    def test_constant_positive_intervals_have_maximum_regularity(self):
        record = score_flow(make_flow([60, 60, 60, 60]))
        self.assertEqual(record["score"], 1)
        self.assertEqual(record["status"], "ok")

    def test_more_variable_intervals_score_lower(self):
        regular = score_flow(make_flow([60, 61, 59, 60]))
        variable = score_flow(make_flow([1, 120, 10, 109]))
        self.assertGreater(regular["score"], variable["score"])

    def test_short_group_is_not_given_a_fabricated_score(self):
        record = score_flow(make_flow([60, 60]))
        self.assertEqual(record["status"], "skipped")
        self.assertIsNone(record["score"])

    def test_all_simultaneous_events_are_skipped(self):
        record = score_flow(make_flow([0, 0, 0, 0]))
        self.assertEqual(record["reason"], "zero_mean_interval")
        self.assertIsNone(record["score"])

    def test_invalid_or_nonfinite_intervals_are_rejected(self):
        for value in (-1, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    score_flow(make_flow([60, value, 60, 60]))

    def test_sequence_length_must_match_event_count(self):
        flow = make_flow([60, 60, 60, 60])
        flow["event_count"] = 10
        with self.assertRaisesRegex(ValueError, "event_count - 1"):
            score_flow(flow)
