"""Checks for CTU-13 scoring, ranking, and label isolation."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.analysis.run_ctu13_baseline import run


class CTU13BaselineTests(unittest.TestCase):
    def test_scores_all_groups_before_label_join_and_ranks_ties_by_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            flows = [
                {"flow_id": "b", "event_count": 5, "time_deltas": [60, 60, 60, 60]},
                {"flow_id": "a", "event_count": 5, "time_deltas": [60, 60, 60, 60]},
                {"flow_id": "c", "event_count": 5, "time_deltas": [0, 0, 0, 0]},
            ]
            labels = [
                {"flow_id": "a", "category": "normal", "cc_annotated_rows": 0},
                {"flow_id": "b", "category": "botnet", "cc_annotated_rows": 5},
                {"flow_id": "c", "category": "background", "cc_annotated_rows": 0},
            ]
            (root / "flows.json").write_text(json.dumps({
                "schema_version": "1.1", "run_id": "fixture",
                "source": {"dataset_id": "fixture"}, "flows": flows,
            }), encoding="utf-8")
            (root / "labels.json").write_text(json.dumps({
                "schema_version": "1.0", "run_id": "fixture", "labels": labels,
            }), encoding="utf-8")
            scores_path = root / "scores.json"
            ranking_path = root / "ranking.csv"
            result, ranking = run(root, scores_path, ranking_path)
            self.assertEqual(result["counts"], {"ok": 2, "skipped": 1, "error": 0})
            self.assertEqual([item["flow_id"] for item in result["scores"]], ["b", "a", "c"])
            self.assertEqual([item["flow_id"] for item in ranking], ["a", "b", "c"])
            self.assertEqual([item["rank"] for item in ranking], [1, 2, ""])
            self.assertEqual(ranking[1]["category"], "botnet")
            self.assertIsNone(result["scores"][2]["score"])
            self.assertEqual(result["scores"][2]["reason"], "zero_mean_interval")
            self.assertNotIn("category", result["scores"][0])
            with ranking_path.open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 3)

            labels[0]["category"] = "botnet"
            (root / "labels.json").write_text(json.dumps({
                "schema_version": "1.0", "run_id": "fixture", "labels": labels,
            }), encoding="utf-8")
            rerun, _ = run(root, scores_path, ranking_path)
            self.assertEqual(result["scores"], rerun["scores"])

    def test_rejects_mismatched_labels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "flows.json").write_text(json.dumps({
                "schema_version": "1.1", "run_id": "first",
                "source": {"dataset_id": "fixture"},
                "flows": [{"flow_id": "a", "event_count": 5,
                           "time_deltas": [1, 1, 1, 1]}],
            }), encoding="utf-8")
            (root / "labels.json").write_text(json.dumps({
                "schema_version": "1.0", "run_id": "other", "labels": [],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "run_id"):
                run(root, root / "scores.json", root / "ranking.csv")
            self.assertFalse((root / "scores.json").exists())
