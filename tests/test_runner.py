import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.runner import PROJECT_ROOT, main


class RunnerTests(unittest.TestCase):
    def test_demo_creates_real_outputs_without_labels_or_mock_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "dataset_id": "sample",
                "input_csv": str(PROJECT_ROOT / "data/sample/connections.csv"),
                "processed_json": str(root / "flows.json"),
                "scores_json": str(root / "scores.json"),
                "baseline": {"min_events": 5},
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["demo", "--config", str(config_path)])
            self.assertEqual(code, 0)
            flows = json.loads((root / "flows.json").read_text(encoding="utf-8"))
            scores = json.loads((root / "scores.json").read_text(encoding="utf-8"))["scores"]
            self.assertEqual(len(flows["flows"]), 2)
            self.assertEqual(len(scores), 2)
            self.assertEqual(sum(row["status"] == "ok" for row in scores), 1)
            self.assertTrue(all("label" not in flow for flow in flows["flows"]))
            self.assertTrue(all("prediction" not in row for row in scores))

    def test_bad_input_returns_error_without_creating_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad_csv = root / "bad.csv"
            bad_csv.write_text("timestamp,src_ip\n", encoding="utf-8")
            config = {
                "dataset_id": "test", "input_csv": str(bad_csv),
                "processed_json": str(root / "flows.json"),
                "scores_json": str(root / "scores.json"),
                "baseline": {"min_events": 5},
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["demo", "--config", str(config_path)])
            self.assertEqual(code, 2)
            self.assertFalse((root / "flows.json").exists())
            self.assertFalse((root / "scores.json").exists())
