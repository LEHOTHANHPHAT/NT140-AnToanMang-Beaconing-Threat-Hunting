import json
import unittest
from pathlib import Path

from src.models.hmm import score_decoded_sequence, score_flow, score_flows


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class HMMTests(unittest.TestCase):
    def test_time_deltas_use_event_count_minus_one_minimum(self):
        flow = {
            "flow_id": "five-events",
            "event_count": 5,
            "time_deltas": [1.0, 3.0, 2.0, 5.0],
            "bytes_sent": [100, 120, 110, 150, 130],
        }
        record = score_flow(flow, {
            "hmm": {
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

    def test_short_sequence_is_skipped_without_fake_score(self):
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

    def test_dominant_state_score_is_invariant_to_state_label_permutation(self):
        original = [0, 0, 0, 1, 1]
        permuted = [2, 2, 2, 7, 7]
        self.assertEqual(
            score_decoded_sequence(original),
            score_decoded_sequence(permuted),
        )
        self.assertEqual(score_decoded_sequence(original), 0.6)

    def test_runs_on_processed_sample_data(self):
        payload = json.loads(
            (PROJECT_ROOT / "data/processed/flows.json").read_text(encoding="utf-8")
        ) if (PROJECT_ROOT / "data/processed/flows.json").exists() else None

        if payload is None:
            from src.data.prepare import prepare_csv
            payload = prepare_csv(
                PROJECT_ROOT / "data/sample/connections.csv",
                dataset_id="sample",
            )

        records = score_flows(payload, {
            "hmm": {
                "min_events": 5,
                "n_states": 2,
                "n_iter": 20,
                "random_seed": 42,
                "n_init": 2,
            }
        })

        self.assertEqual(len(records), 2)
        for record in records:
            self.assertIn("flow_id", record)
            self.assertIn("time_deltas", record["feature_scores"])
            self.assertIn("bytes_sent", record["feature_scores"])
            self.assertIn(record["status"], ("ok", "skipped"))
            self.assertNotIn("label", record)


if __name__ == "__main__":
    unittest.main()
