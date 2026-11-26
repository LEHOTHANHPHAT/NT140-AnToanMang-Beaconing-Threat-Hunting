import unittest

import numpy as np

from src.models.ct_hmm import ctmc_transition_matrix, score_flow


class CTHMMTests(unittest.TestCase):
    def test_time_deltas_use_event_count_minus_one_minimum(self):
        flow = {
            "flow_id": "five-events",
            "event_count": 5,
            "time_deltas": [1.0, 3.0, 2.0, 5.0],
            "bytes_sent": [100, 120, 110, 150, 130],
        }
        record = score_flow(flow, {
            "ct_hmm": {
                "min_events": 5,
                "n_states": 2,
                "n_iter": 20,
                "random_seed": 13,
                "n_init": 1,
            }
        })

        self.assertEqual(record["feature_details"]["time_deltas"]["d"], 4)
        self.assertEqual(record["feature_details"]["bytes_sent"]["d"], 5)
        self.assertIsNotNone(record["feature_scores"]["time_deltas"])
        self.assertIsNotNone(record["feature_scores"]["bytes_sent"])

    def test_q_row_sums_and_transition_matrix_row_sums(self):
        Q = np.array([
            [-0.25, 0.25],
            [0.10, -0.10],
        ])
        P = ctmc_transition_matrix(Q, 3.5)

        self.assertTrue(np.allclose(Q.sum(axis=1), 0.0))
        self.assertTrue(np.allclose(P.sum(axis=1), 1.0))
        self.assertTrue(np.all(P >= 0.0))

        P_zero = ctmc_transition_matrix(Q, 0)
        self.assertTrue(np.array_equal(P_zero, np.eye(2)))

    def test_short_sequence_is_skipped(self):
        flow = {
            "flow_id": "short",
            "event_count": 3,
            "time_deltas": [60, 155],
            "bytes_sent": [450, 780, 1300],
        }
        record = score_flow(flow)
        self.assertEqual(record["status"], "skipped")
        self.assertIsNone(record["score"])
        self.assertIn("fewer_than", record["skip_reason"])

    def test_q_is_saved_and_uses_no_labels(self):
        flow = {
            "flow_id": "synthetic",
            "event_count": 8,
            "time_deltas": [1.0, 1.0, 2.0, 20.0, 20.0, 2.0, 1.0],
            "bytes_sent": [100, 105, 110, 900, 920, 115, 108, 102],
        }
        record = score_flow(flow, {
            "ct_hmm": {
                "min_events": 5,
                "n_states": 2,
                "n_iter": 40,
                "n_init": 2,
                "random_seed": 7,
            }
        })

        self.assertIn(record["status"], ("ok", "skipped"))
        Q = record["metadata"]["Q"]
        if record["status"] == "ok":
            self.assertEqual(len(Q), 2)
            self.assertTrue(np.allclose(np.asarray(Q).sum(axis=1), 0.0))
        self.assertNotIn("label", record)
        self.assertNotIn("labels", record)

    def test_two_timing_modes_produce_different_feature_results(self):
        config = {
            "ct_hmm": {
                "min_events": 5,
                "n_states": 2,
                "n_iter": 60,
                "n_init": 3,
                "random_seed": 11,
            }
        }
        regular = {
            "flow_id": "regular",
            "event_count": 8,
            "time_deltas": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "bytes_sent": [100, 100, 100, 100, 100, 100, 100, 100],
        }
        jump = {
            "flow_id": "jump",
            "event_count": 8,
            "time_deltas": [1.0, 1.0, 1.0, 30.0, 30.0, 30.0, 1.0],
            "bytes_sent": [100, 100, 100, 900, 900, 900, 100, 100],
        }

        regular_record = score_flow(regular, config)
        jump_record = score_flow(jump, config)

        regular_time_score = regular_record["feature_scores"]["time_deltas"]
        jump_time_score = jump_record["feature_scores"]["time_deltas"]
        # PR #8 issue 1: a zero-variance (perfectly regular) sequence is the
        # strongest beaconing evidence, so it is scored high, not skipped.
        self.assertEqual(regular_record["status"], "ok")
        self.assertEqual(jump_record["status"], "ok")
        self.assertIsNotNone(regular_time_score)
        self.assertIsNotNone(jump_time_score)
        self.assertGreater(regular_time_score, jump_time_score)


if __name__ == "__main__":
    unittest.main()
